from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional

from app.domain.entities.ride import Location
from app.infrastructure.rides.mock_ride_infrastructure import (
    ws_manager
)
from app.infrastructure.rides.rabbitmq_service import RabbitMQService
from app.infrastructure.rides.redis_geo_repository import RedisGeoRepository
from app.infrastructure.payment.mobile_money_service import MobileMoneyService
from app.application.use_cases.request_ride import RequestRideUseCase
from app.application.use_cases.accept_ride import AcceptRideUseCase
from app.application.use_cases.payment_webhook import PaymentWebhookUseCase
from app.application.use_cases.update_ride_status import UpdateRideStatusUseCase
from app.presentation.dependencies import RideRepo, CurrentUserId, get_db
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

ride_router = APIRouter(prefix="/rides", tags=["Rides"])

# Injection (Global instances)
redis_geo_repo = RedisGeoRepository(redis_url=settings.REDIS_URL)
rabbitmq_service = RabbitMQService(amqp_url=settings.RABBITMQ_URL)
mobile_money_service = MobileMoneyService(api_base_url="mock://mobilemoney", api_key="test_key")

class RequestRidePayload(BaseModel):
    client_id: str
    pickup: Location
    dropoff: Location
    type: str = "vtc"
    package_description: Optional[str] = None

class AcceptRidePayload(BaseModel):
    driver_id: str

class PaymentWebhookPayload(BaseModel):
    ride_id: str
    success: bool
    transaction_id: str

class UpdateStatusPayload(BaseModel):
    status: str
    driver_id: Optional[str] = None

class SyncMissionPayload(BaseModel):
    ride_id: str
    client_id: str
    driver_id: Optional[str] = None
    merchant_id: Optional[str] = None
    type: str  # 'vtc', 'food', 'delivery', 'package'
    status: str
    price: float
    package_description: Optional[str] = None
    pickup_lat: Optional[float] = None
    pickup_lng: Optional[float] = None
    dropoff_lat: Optional[float] = None
    dropoff_lng: Optional[float] = None

@ride_router.post("/request")
async def request_ride(payload: RequestRidePayload, ride_repo: RideRepo):
    use_case = RequestRideUseCase(ride_repo, redis_geo_repo, ws_manager)
    try:
        mission = await use_case.execute(payload.client_id, payload.pickup, payload.dropoff, payload.type, payload.package_description)
        return {
            "status": "success",
            "mission": {
                "id": str(mission.id),
                "client_id": mission.client_id,
                "driver_id": mission.driver_id,
                "type": mission.type,
                "status": mission.status.value,
                "pickup": {"latitude": mission.pickup.latitude, "longitude": mission.pickup.longitude},
                "dropoff": {"latitude": mission.dropoff.latitude, "longitude": mission.dropoff.longitude},
                "price": mission.price,
                "package_description": mission.package_description,
                "created_at": mission.created_at.isoformat() if mission.created_at else None,
                "updated_at": mission.updated_at.isoformat() if mission.updated_at else None,
            }
        }
    except Exception as e:
        import traceback
        print(f"[/rides/request ERROR] {type(e).__name__}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))

@ride_router.post("/{ride_id}/accept")
async def accept_ride(ride_id: str, payload: AcceptRidePayload, ride_repo: RideRepo):
    use_case = AcceptRideUseCase(ride_repo, rabbitmq_service)
    try:
        mission = await use_case.execute(ride_id, payload.driver_id)
        return {"status": "success", "mission": mission}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@ride_router.post("/{ride_id}/status")
async def update_status(ride_id: str, payload: UpdateStatusPayload, ride_repo: RideRepo):
    use_case = UpdateRideStatusUseCase(ride_repo, ws_manager)
    try:
        mission = await use_case.execute(ride_id, payload.status, payload.driver_id)
        return {"status": "success", "mission": mission}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@ride_router.post("/webhooks/payment")
async def payment_webhook(payload: PaymentWebhookPayload, ride_repo: RideRepo):
    use_case = PaymentWebhookUseCase(ride_repo, ws_manager)
    try:
        mission = await use_case.execute(payload.ride_id, payload.success, payload.transaction_id)
        return {"status": "success", "mission": mission}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@ride_router.post("/sync")
async def sync_mission(payload: SyncMissionPayload, db: AsyncSession = Depends(get_db)):
    from app.infrastructure.persistence.models import MissionModel, DriverModel, MerchantModel
    from app.infrastructure.persistence.wallet_repository_impl import SQLAlchemyWalletRepository
    from sqlalchemy import select
    import uuid

    # Assurer que le chauffeur existe dans la table 'drivers' pour éviter les violations de clé étrangère
    if payload.driver_id:
        stmt_driver = select(DriverModel).where(DriverModel.id == payload.driver_id)
        res_driver = await db.execute(stmt_driver)
        driver_exists = res_driver.scalar_one_or_none()
        if not driver_exists:
            # Créer automatiquement un profil de chauffeur par défaut si manquant
            new_driver = DriverModel(
                id=payload.driver_id,
                vehicle_type="moto",
                plate_number=f"BOLI-{payload.driver_id[:6].toUpperCase() if hasattr(payload.driver_id, 'toUpperCase') else payload.driver_id[:6].upper()}",
                is_online=True,
                is_available=True
            )
            db.add(new_driver)
            await db.flush()

    # Valider le merchant_id par rapport à la base de données
    db_merchant_id = None
    if payload.merchant_id:
        stmt_merchant = select(MerchantModel).where(MerchantModel.id == payload.merchant_id)
        res_merchant = await db.execute(stmt_merchant)
        merchant_exists = res_merchant.scalar_one_or_none()
        if merchant_exists:
            db_merchant_id = payload.merchant_id
        else:
            # Essayer de chercher par nom (ex. "Restaurant Saveurs du Mali")
            stmt_m_by_name = select(MerchantModel).where(MerchantModel.name == payload.merchant_id)
            res_m_by_name = await db.execute(stmt_m_by_name)
            merchant_by_name = res_m_by_name.scalar_one_or_none()
            if merchant_by_name:
                db_merchant_id = merchant_by_name.id

    # 1. Vérifier si la mission existe déjà en base
    stmt = select(MissionModel).where(MissionModel.id == payload.ride_id)
    result = await db.execute(stmt)
    model = result.scalar_one_or_none()

    if not model:
        # Création de la mission
        lat_p = payload.pickup_lat or 12.6392
        lng_p = payload.pickup_lng or -8.0029
        lat_d = payload.dropoff_lat or 12.6392
        lng_d = payload.dropoff_lng or -8.0029
        
        model = MissionModel(
            id=payload.ride_id,
            client_id=payload.client_id,
            driver_id=payload.driver_id,
            merchant_id=db_merchant_id,
            type=payload.type,
            status=payload.status,
            package_description=payload.package_description,
            pickup_location=f"SRID=4326;POINT({lng_p} {lat_p})",
            dropoff_location=f"SRID=4326;POINT({lng_d} {lat_d})",
            price_total=payload.price
        )
        db.add(model)
        await db.flush()
    else:
        # Mise à jour
        model.status = payload.status
        if payload.driver_id:
            model.driver_id = payload.driver_id
        model.merchant_id = db_merchant_id
        if payload.package_description is not None:
            model.package_description = payload.package_description

    # 2. Gestion des paiements automatiques lors de la finalisation
    wallet_repo = SQLAlchemyWalletRepository(db)
    
    # Si course VTC terminée
    if payload.status == "completed" and payload.type == "vtc":
        # Débiter le client
        await wallet_repo.update_balance(
            user_id=model.client_id,
            amount=-payload.price,
            tx_type="payment",
            description=f"Paiement trajet VTC {payload.ride_id[:8].upper()}"
        )
        # Créditer le chauffeur
        if model.driver_id:
            await wallet_repo.update_balance(
                user_id=model.driver_id,
                amount=payload.price,
                tx_type="earning",
                description=f"Gain trajet VTC {payload.ride_id[:8].upper()}"
            )
            
    # Si livraison de nourriture terminée
    elif payload.status == "delivered" and (payload.type == "food" or payload.type == "delivery"):
        if model.driver_id:
            delivery_fee = 1500.0
            await wallet_repo.update_balance(
                user_id=model.driver_id,
                amount=delivery_fee,
                tx_type="earning",
                description=f"Gain livraison {payload.ride_id[:8].upper()}"
            )

    # Si envoi de colis terminé
    elif payload.status == "completed" and payload.type == "package":
        await wallet_repo.update_balance(
            user_id=model.client_id,
            amount=-payload.price,
            tx_type="payment",
            description=f"Paiement envoi colis {payload.ride_id[:8].upper()}"
        )
        if model.driver_id:
            await wallet_repo.update_balance(
                user_id=model.driver_id,
                amount=payload.price,
                tx_type="earning",
                description=f"Gain livraison colis {payload.ride_id[:8].upper()}"
            )

    await db.commit()
    return {"status": "success", "ride_id": model.id, "mission_status": model.status}

@ride_router.get("/history")
async def get_ride_history(user_id: CurrentUserId, db: AsyncSession = Depends(get_db)):
    from app.infrastructure.persistence.models import MissionModel
    from sqlalchemy import select, or_
    from geoalchemy2.shape import to_shape

    stmt = select(MissionModel).where(
        or_(
            MissionModel.client_id == user_id,
            MissionModel.driver_id == user_id
        )
    ).order_by(MissionModel.created_at.desc())
    
    result = await db.execute(stmt)
    missions = result.scalars().all()
    
    out = []
    for m in missions:
        p_shape = to_shape(m.pickup_location)
        d_shape = to_shape(m.dropoff_location)
        out.append({
            "id": m.id,
            "client_id": m.client_id,
            "driver_id": m.driver_id,
            "merchant_id": m.merchant_id,
            "type": m.type,
            "status": m.status,
            "package_description": m.package_description,
            "price": float(m.price_total),
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "updated_at": m.updated_at.isoformat() if m.updated_at else None,
            "pickup": {"lat": p_shape.y, "lng": p_shape.x},
            "dropoff": {"lat": d_shape.y, "lng": d_shape.x}
        })
    return out


ws_router = APIRouter(tags=["WebSockets"])

@ws_router.websocket("/ws/notifications")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await ws_manager.connect(client_id, websocket)
    try:
        while True:
            # Pour maintenir la connexion active et recevoir d'éventuels messages du client
            data = await websocket.receive_text()
            # Traiter la mise à jour de la position GPS du chauffeur
            if data.startswith("GPS:"):
                coords = data.replace("GPS:", "").split(",")
                if len(coords) == 2:
                    loc = Location(latitude=float(coords[0]), longitude=float(coords[1]))
                    await redis_geo_repo.update_driver_location(client_id, loc)
                    
                    # Notifier également le client associé de la nouvelle position du chauffeur si applicable
                    # Pour simplifier, on peut diffuser la position à toutes les connexions actives,
                    # ou cibler le client de la course en cours. Diffusons un event de localisation :
                    await ws_manager.notify_client(client_id, {
                        "type": "DRIVER_LOCATION_UPDATED",
                        "driver_id": client_id,
                        "latitude": loc.latitude,
                        "longitude": loc.longitude
                    })
    except WebSocketDisconnect:
        ws_manager.disconnect(client_id)
