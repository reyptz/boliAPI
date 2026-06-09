from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession

from app.presentation.dependencies import CurrentUserId, get_db
from app.infrastructure.persistence.wallet_repository_impl import SQLAlchemyWalletRepository

wallet_router = APIRouter(prefix="/wallet", tags=["Wallet"])

class DepositRequest(BaseModel):
    amount: float
    phone: str

async def get_wallet_repo(db: AsyncSession = Depends(get_db)) -> SQLAlchemyWalletRepository:
    return SQLAlchemyWalletRepository(db)

WalletRepo = Annotated[SQLAlchemyWalletRepository, Depends(get_wallet_repo)]

@wallet_router.get("/balance")
async def get_balance(user_id: CurrentUserId, repo: WalletRepo):
    wallet = await repo.get_by_user_id(user_id)
    if not wallet:
        # Auto-create wallet if not exists
        wallet = await repo.create(user_id)
    return {"balance": wallet.balance, "currency": wallet.currency}

@wallet_router.post("/deposit")
async def deposit(payload: DepositRequest, user_id: CurrentUserId, repo: WalletRepo):
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Le montant doit être supérieur à 0.")
    # Simuler un dépôt Mobile Money réussi
    wallet = await repo.update_balance(
        user_id, 
        payload.amount, 
        tx_type="deposit", 
        description="Recharge Mobile Money"
    )
    return {
        "status": "success",
        "message": f"Dépôt de {payload.amount} XOF effectué avec succès !",
        "balance": wallet.balance
    }

@wallet_router.get("/transactions")
async def get_transactions(user_id: CurrentUserId, db: AsyncSession = Depends(get_db)):
    from app.infrastructure.persistence.models import TransactionModel
    from sqlalchemy import select
    stmt = select(TransactionModel).where(TransactionModel.user_id == user_id).order_by(TransactionModel.created_at.desc())
    result = await db.execute(stmt)
    txs = result.scalars().all()
    return [
        {
            "id": tx.id,
            "amount": float(tx.amount),
            "type": tx.type,
            "description": tx.description,
            "created_at": tx.created_at.isoformat() if tx.created_at else None
        }
        for tx in txs
    ]
