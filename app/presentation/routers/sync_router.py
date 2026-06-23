"""
Router de synchronisation marketplace (SuguJate → Boli).
Déclenche manuellement une passe de sync (réservé aux administrateurs).
Remplace l'ancien seeder factice `/merchants/seed`.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.merchant_sync_repository import SqlAlchemyMerchantSyncRepository
from app.infrastructure.sync.firestore_client import FirestoreSource, get_firestore_client
from app.infrastructure.sync.merchant_sync import run_sync
from app.presentation.dependencies import AdminPayload, get_db

sync_router = APIRouter(prefix="/sync", tags=["Sync"])


@sync_router.post("/run")
async def run_merchant_sync(_admin: AdminPayload, db: AsyncSession = Depends(get_db)):
    """Synchronise les marchands SuguJate publiés vers le marketplace Boli."""
    client = get_firestore_client()
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="Firebase non configuré (FIREBASE_CREDENTIALS_PATH).",
        )
    repo = SqlAlchemyMerchantSyncRepository(db)
    result = await run_sync(FirestoreSource(client), repo)
    await db.commit()
    return {"status": "ok", **result}
