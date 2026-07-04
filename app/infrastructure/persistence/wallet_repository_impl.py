from decimal import Decimal
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.domain.repositories.wallet_repository import IWalletRepository, Wallet
from app.domain.exceptions import InsufficientBalanceError
from app.infrastructure.persistence.models import WalletModel, TransactionModel


class SQLAlchemyWalletRepository(IWalletRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _to_entity(model: WalletModel) -> Wallet:
        return Wallet(
            id=model.id,
            user_id=model.user_id,
            balance=Decimal(model.balance),
            currency=model.currency,
            updated_at=model.updated_at,
        )

    async def get_by_user_id(self, user_id: str) -> Optional[Wallet]:
        stmt = select(WalletModel).where(WalletModel.user_id == user_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return None
        return self._to_entity(model)

    async def create(self, user_id: str) -> Wallet:
        model = WalletModel(
            id=str(uuid.uuid4()),
            user_id=user_id,
            balance=Decimal("0.00"),
            currency="XOF",
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return self._to_entity(model)

    async def update_balance(
        self,
        user_id: str,
        amount: Decimal | float,
        tx_type: str = "deposit",
        description: str = "Recharge Mobile Money",
        *,
        allow_negative: bool = False,
    ) -> Wallet:
        """
        Met à jour le solde de façon **atomique** avec un verrou de ligne
        (`SELECT ... FOR UPDATE`) afin d'éviter les race conditions de
        crédit/débit concurrents. Refuse de passer le solde sous 0 pour un
        débit sauf si `allow_negative=True`.
        """
        amount = Decimal(str(amount))

        # Verrou de ligne : sérialise les mises à jour concurrentes du même wallet.
        stmt = (
            select(WalletModel)
            .where(WalletModel.user_id == user_id)
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            # Créer automatiquement si introuvable
            model = WalletModel(
                id=str(uuid.uuid4()),
                user_id=user_id,
                balance=Decimal("0.00"),
                currency="XOF",
            )
            self.session.add(model)
            await self.session.flush()

        new_balance = Decimal(model.balance) + amount
        if new_balance < 0 and not allow_negative:
            raise InsufficientBalanceError()

        model.balance = new_balance

        # Enregistrer la transaction (piste d'audit)
        tx = TransactionModel(
            id=str(uuid.uuid4()),
            user_id=user_id,
            amount=amount,
            type=tx_type,
            description=description,
        )
        self.session.add(tx)

        await self.session.commit()
        await self.session.refresh(model)
        return self._to_entity(model)
