from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.domain.repositories.wallet_repository import IWalletRepository, Wallet
from app.infrastructure.persistence.models import WalletModel, TransactionModel

class SQLAlchemyWalletRepository(IWalletRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _to_entity(model: WalletModel) -> Wallet:
        return Wallet(
            id=model.id,
            user_id=model.user_id,
            balance=float(model.balance),
            currency=model.currency,
            updated_at=model.updated_at
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
            balance=0.0,
            currency="XOF"
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return self._to_entity(model)

    async def update_balance(self, user_id: str, amount: float, tx_type: str = "deposit", description: str = "Recharge Mobile Money") -> Wallet:
        stmt = select(WalletModel).where(WalletModel.user_id == user_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            # Créer automatiquement si introuvable
            model_wallet = WalletModel(
                id=str(uuid.uuid4()),
                user_id=user_id,
                balance=0.0,
                currency="XOF"
            )
            self.session.add(model_wallet)
            await self.session.flush()
            model = model_wallet
            
        model.balance = float(model.balance) + amount
        
        # Enregistrer la transaction
        tx = TransactionModel(
            id=str(uuid.uuid4()),
            user_id=user_id,
            amount=amount,
            type=tx_type,
            description=description
        )
        self.session.add(tx)
        
        await self.session.commit()
        await self.session.refresh(model)
        return self._to_entity(model)
