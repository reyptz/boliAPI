"""
Boucle de synchronisation périodique marketplace (SuguJate → Postgres).
Lancée comme tâche de fond dans le `lifespan` de l'application.
"""

from __future__ import annotations

import asyncio
import logging

from app.config import settings
from app.database import async_session_factory
from app.infrastructure.persistence.merchant_sync_repository import SqlAlchemyMerchantSyncRepository
from app.infrastructure.sync.firestore_client import FirestoreSource, get_firestore_client
from app.infrastructure.sync.merchant_sync import run_sync

logger = logging.getLogger("boli-api.sync")


async def run_once() -> dict | None:
    """Exécute une passe de sync ; retourne le décompte ou None si désactivée."""
    client = get_firestore_client()
    if client is None:
        return None
    async with async_session_factory() as db:
        repo = SqlAlchemyMerchantSyncRepository(db)
        result = await run_sync(FirestoreSource(client), repo)
        await db.commit()
        return result


async def start_sync_loop() -> None:
    """Boucle infinie de sync (no-op si SYNC_ENABLED est faux)."""
    if not settings.SYNC_ENABLED:
        logger.info("Sync périodique désactivée (SYNC_ENABLED=False).")
        return

    logger.info("Sync périodique active (intervalle: %ss).", settings.SYNC_INTERVAL_SECONDS)
    while True:
        try:
            result = await run_once()
            if result is None:
                logger.warning("Sync ignorée : Firebase non configuré.")
        except Exception as exc:  # pragma: no cover
            logger.error("Erreur durant la sync périodique : %s", exc)
        await asyncio.sleep(settings.SYNC_INTERVAL_SECONDS)
