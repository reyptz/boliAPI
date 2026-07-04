"""
Use Case — Synchronisation d'une mission + règlement financier.

Extrait de `ride_router.sync_mission` (qui mélangeait ORM, validation et
paiements directement dans la couche présentation) pour respecter la Clean
Architecture déjà en place ailleurs dans le projet.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dto.ride_dto import SyncMissionDTO
from app.domain.services.pricing_service import PricingService
from app.infrastructure.persistence.models import DriverModel, MerchantModel, MissionModel
from app.infrastructure.persistence.wallet_repository_impl import SQLAlchemyWalletRepository

# Coordonnées par défaut (centre de Bamako) si aucune position n'est fournie.
_DEFAULT_LAT = 12.6392
_DEFAULT_LNG = -8.0029


class SyncMissionUseCase:
    """Upsert d'une mission + déclenchement du règlement financier associé."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.wallet_repo = SQLAlchemyWalletRepository(db)

    async def _ensure_driver_exists(self, driver_id: str) -> None:
        res = await self.db.execute(select(DriverModel).where(DriverModel.id == driver_id))
        if res.scalar_one_or_none() is not None:
            return
        # Créer automatiquement un profil chauffeur par défaut si manquant
        # (évite une violation de clé étrangère lors de l'upsert de la mission).
        self.db.add(
            DriverModel(
                id=driver_id,
                vehicle_type="moto",
                plate_number=f"BOLI-{driver_id[:6].upper()}",
                is_online=True,
                is_available=True,
            )
        )
        await self.db.flush()

    async def _resolve_merchant_id(self, merchant_ref: str) -> str | None:
        res = await self.db.execute(select(MerchantModel).where(MerchantModel.id == merchant_ref))
        if res.scalar_one_or_none() is not None:
            return merchant_ref

        # Fallback : recherche par nom (ex. "Restaurant Saveurs du Mali")
        res_by_name = await self.db.execute(select(MerchantModel).where(MerchantModel.name == merchant_ref))
        merchant_by_name = res_by_name.scalar_one_or_none()
        return merchant_by_name.id if merchant_by_name else None

    async def _upsert_mission(self, dto: SyncMissionDTO, db_merchant_id: str | None) -> MissionModel:
        result = await self.db.execute(select(MissionModel).where(MissionModel.id == dto.ride_id))
        model = result.scalar_one_or_none()

        if not model:
            lat_p = dto.pickup_lat or _DEFAULT_LAT
            lng_p = dto.pickup_lng or _DEFAULT_LNG
            lat_d = dto.dropoff_lat or _DEFAULT_LAT
            lng_d = dto.dropoff_lng or _DEFAULT_LNG
            model = MissionModel(
                id=dto.ride_id,
                client_id=dto.client_id,
                driver_id=dto.driver_id,
                merchant_id=db_merchant_id,
                type=dto.type,
                status=dto.status,
                package_description=dto.package_description,
                pickup_location=f"SRID=4326;POINT({lng_p} {lat_p})",
                dropoff_location=f"SRID=4326;POINT({lng_d} {lat_d})",
                price_total=dto.price,
            )
            self.db.add(model)
            await self.db.flush()
        else:
            model.status = dto.status
            if dto.driver_id:
                model.driver_id = dto.driver_id
            model.merchant_id = db_merchant_id
            if dto.package_description is not None:
                model.package_description = dto.package_description

        return model

    async def _settle_payment(self, dto: SyncMissionDTO, model: MissionModel) -> None:
        """Débit client / crédit chauffeur, selon le type et le statut final de la mission."""
        ref = dto.ride_id[:8].upper()

        if dto.status == "completed" and dto.type == "vtc":
            await self.wallet_repo.update_balance(
                model.client_id, -dto.price, tx_type="payment",
                description=f"Paiement trajet VTC {ref}",
            )
            if model.driver_id:
                await self.wallet_repo.update_balance(
                    model.driver_id, dto.price, tx_type="earning",
                    description=f"Gain trajet VTC {ref}",
                )
        elif dto.status == "delivered" and dto.type in ("food", "delivery"):
            if model.driver_id:
                await self.wallet_repo.update_balance(
                    model.driver_id, PricingService.DELIVERY_DRIVER_FEE, tx_type="earning",
                    description=f"Gain livraison {ref}",
                )
        elif dto.status == "completed" and dto.type == "package":
            await self.wallet_repo.update_balance(
                model.client_id, -dto.price, tx_type="payment",
                description=f"Paiement envoi colis {ref}",
            )
            if model.driver_id:
                await self.wallet_repo.update_balance(
                    model.driver_id, dto.price, tx_type="earning",
                    description=f"Gain livraison colis {ref}",
                )

    async def execute(self, dto: SyncMissionDTO) -> dict:
        if dto.driver_id:
            await self._ensure_driver_exists(dto.driver_id)

        db_merchant_id = await self._resolve_merchant_id(dto.merchant_id) if dto.merchant_id else None
        model = await self._upsert_mission(dto, db_merchant_id)
        await self._settle_payment(dto, model)

        await self.db.commit()
        return {"ride_id": model.id, "mission_status": model.status}
