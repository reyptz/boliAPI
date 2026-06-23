"""
Client Firebase Admin (lecture seule de Firestore) + source d'espaces.

L'initialisation est paresseuse et tolérante : si le service-account n'est pas
configuré, `get_firestore_client()` retourne `None` et la sync est simplement
désactivée (pas d'erreur fatale au démarrage).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.config import settings

logger = logging.getLogger("boli-api.sync")

_client = None
_init_attempted = False


def get_firestore_client():
    """Retourne un client Firestore (ou None si Firebase n'est pas configuré)."""
    global _client, _init_attempted
    if _init_attempted:
        return _client
    _init_attempted = True

    if not settings.FIREBASE_CREDENTIALS_PATH:
        logger.warning(
            "FIREBASE_CREDENTIALS_PATH absent — synchronisation marketplace désactivée."
        )
        return None

    try:
        import firebase_admin
        from firebase_admin import credentials, firestore

        if not firebase_admin._apps:
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
            options = {"projectId": settings.FIREBASE_PROJECT_ID} if settings.FIREBASE_PROJECT_ID else None
            firebase_admin.initialize_app(cred, options)
        _client = firestore.client()
        logger.info("Client Firestore initialisé.")
    except Exception as exc:  # pragma: no cover - dépend de l'environnement
        logger.error("Échec d'initialisation Firebase Admin : %s", exc)
        _client = None
    return _client


class FirestoreSource:
    """Implémente `SpaceSource` en lisant les collections Firestore de SuguJate."""

    def __init__(self, client):
        self._client = client

    async def fetch_published_stores(self) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._fetch_published_stores_sync)

    async def fetch_store_products(self, store_id: str) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._fetch_store_products_sync, store_id)

    # ── Appels Firestore synchrones (exécutés dans un thread) ──
    def _fetch_published_stores_sync(self) -> list[dict[str, Any]]:
        docs = (
            self._client.collection("stores")
            .where("publishedToMarketplace", "==", True)
            .stream()
        )
        out: list[dict[str, Any]] = []
        for doc in docs:
            data = doc.to_dict() or {}
            data["id"] = doc.id
            out.append(data)
        return out

    def _fetch_store_products_sync(self, store_id: str) -> list[dict[str, Any]]:
        docs = (
            self._client.collection("products")
            .where("storeId", "==", store_id)
            .where("enabled", "==", True)
            .stream()
        )
        out: list[dict[str, Any]] = []
        for doc in docs:
            data = doc.to_dict() or {}
            data["id"] = doc.id
            out.append(data)
        return out
