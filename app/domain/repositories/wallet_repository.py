from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel
from datetime import datetime

class Wallet(BaseModel):
    id: str
    user_id: str
    balance: Decimal
    currency: str
    updated_at: datetime

class IWalletRepository(ABC):
    @abstractmethod
    async def get_by_user_id(self, user_id: str) -> Optional[Wallet]:
        pass

    @abstractmethod
    async def create(self, user_id: str) -> Wallet:
        pass

    @abstractmethod
    async def update_balance(
        self,
        user_id: str,
        amount: Decimal | float,
        tx_type: str = "deposit",
        description: str = "Recharge Mobile Money",
        *,
        allow_negative: bool = False,
    ) -> Wallet:
        pass
