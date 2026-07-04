from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.domain.exceptions import InvalidAmountError
from app.infrastructure.payment.mobile_money_service import MobileMoneyService
from app.infrastructure.persistence.models import TransactionModel
from app.infrastructure.persistence.wallet_repository_impl import SQLAlchemyWalletRepository
from app.presentation.dependencies import CurrentUserId, get_db

wallet_router = APIRouter(prefix="/wallet", tags=["Wallet"])

# Service Mobile Money (config-driven, plus de clé en dur).
_mobile_money = MobileMoneyService(
    api_base_url=settings.MOBILE_MONEY_API_URL,
    api_key=settings.MOBILE_MONEY_API_KEY,
)


class DepositRequest(BaseModel):
    amount: Decimal
    phone: str

    @field_validator("amount")
    @classmethod
    def _amount_positive(cls, v: Decimal) -> Decimal:
        # Une recharge doit être strictement positive. Les débits/paiements
        # passent par les flux dédiés (course, commande), jamais par /deposit.
        if v <= 0:
            raise ValueError("Le montant d'une recharge doit être positif.")
        return v


async def get_wallet_repo(db: AsyncSession = Depends(get_db)) -> SQLAlchemyWalletRepository:
    return SQLAlchemyWalletRepository(db)


WalletRepo = Annotated[SQLAlchemyWalletRepository, Depends(get_wallet_repo)]


@wallet_router.get("/balance")
async def get_balance(user_id: CurrentUserId, repo: WalletRepo):
    wallet = await repo.get_by_user_id(user_id)
    if not wallet:
        # Auto-création du wallet si absent
        wallet = await repo.create(user_id)
    return {"balance": wallet.balance, "currency": wallet.currency}


@wallet_router.post("/deposit")
async def deposit(payload: DepositRequest, user_id: CurrentUserId, repo: WalletRepo):
    """
    Initie une recharge Mobile Money.

    ⚠️ Sécurité : le solde n'est **jamais** crédité directement par cet appel
    client (ce qui permettrait de se créditer un montant arbitraire). On déclenche
    une demande de paiement (USSD push) ; le crédit réel n'a lieu qu'à la réception
    du webhook signé du fournisseur Mobile Money.
    En mode DEBUG uniquement, on simule le crédit immédiat pour faciliter les tests.
    """
    if payload.amount <= 0:
        raise InvalidAmountError()

    reference = f"TOPUP-{user_id[:8]}"
    tx = await _mobile_money.request_mobile_payment(
        phone_number=payload.phone,
        amount=float(payload.amount),
        reference=reference,
    )

    # En développement, on simule la confirmation immédiate du fournisseur.
    if settings.DEBUG:
        wallet = await repo.update_balance(
            user_id,
            payload.amount,
            tx_type="deposit",
            description="Recharge Mobile Money (simulée - DEBUG)",
        )
        return {
            "status": "success",
            "message": f"Dépôt de {payload.amount} XOF effectué (simulation DEBUG).",
            "balance": wallet.balance,
            "transaction_id": tx.get("transaction_id"),
        }

    # En production : en attente de la confirmation via webhook signé.
    return {
        "status": "pending",
        "message": "Demande de paiement envoyée. Validez sur votre téléphone.",
        "transaction_id": tx.get("transaction_id"),
        "payment_status": tx.get("status"),
    }


@wallet_router.get("/transactions")
async def get_transactions(user_id: CurrentUserId, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(TransactionModel)
        .where(TransactionModel.user_id == user_id)
        .order_by(TransactionModel.created_at.desc())
        .limit(100)
    )
    result = await db.execute(stmt)
    txs = result.scalars().all()
    return [
        {
            "id": tx.id,
            "amount": tx.amount,
            "type": tx.type,
            "description": tx.description,
            "created_at": tx.created_at.isoformat() if tx.created_at else None,
        }
        for tx in txs
    ]
