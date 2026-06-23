"""
Synchronisation des marchands SuguJate (Firestore) → marketplace Boli (Postgres).

Conçu autour de deux interfaces (`SpaceSource`, `MerchantSyncRepo`) pour rester
découplé de Firebase et de SQLAlchemy : les fonctions de mapping sont pures et
l'orchestration `run_sync` est testable avec des doublures en mémoire.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

logger = logging.getLogger("boli-api.sync")


# ── Interfaces ───────────────────────────────────────────────
class SpaceSource(Protocol):
    """Source des espaces publiés (implémentée par `FirestoreSource`)."""

    async def fetch_published_stores(self) -> list[dict[str, Any]]: ...
    async def fetch_store_products(self, store_id: str) -> list[dict[str, Any]]: ...


class MerchantSyncRepo(Protocol):
    """Cible d'upsert (implémentée par `SqlAlchemyMerchantSyncRepository`)."""

    async def upsert_merchant(self, erp_merchant_id: str, fields: dict[str, Any]) -> str:
        """Crée ou met à jour un marchand ; retourne sa clé primaire interne."""
        ...

    async def upsert_product(self, erp_product_id: str, fields: dict[str, Any]) -> None: ...


# ── Mapping pur (Firestore → champs marchand/produit) ────────
def store_to_merchant_fields(store: dict[str, Any]) -> dict[str, Any] | None:
    """
    Convertit un document `stores` Firestore en champs marchand.
    Retourne `None` si l'espace n'a pas de géolocalisation (non livrable,
    donc non exposable au marketplace géospatial).
    """
    geo = store.get("geo") or {}
    lat, lng = geo.get("lat"), geo.get("lng")
    if lat is None or lng is None:
        return None

    return {
        "name": store.get("name") or "Espace sans nom",
        "category": store.get("category") or "vendeur",
        "subcategory": store.get("subcategory"),
        "is_open": bool(store.get("isOpen", True)),
        "is_published": bool(store.get("publishedToMarketplace", True)),
        # EWKT consommé directement par GeoAlchemy2.
        "location_wkt": f"SRID=4326;POINT({lng} {lat})",
        "lat": float(lat),
        "lng": float(lng),
    }


def product_to_fields(product: dict[str, Any], merchant_pk: str) -> dict[str, Any]:
    """Convertit un document `products` Firestore en champs produit."""
    raw_price = product.get("price", 0) or 0
    return {
        "merchant_id": merchant_pk,
        "name": product.get("name") or "Produit sans nom",
        "description": product.get("description"),
        "price": float(raw_price),
        "stock": product.get("stock"),
        "is_available": bool(product.get("enabled", True)),
    }


# ── Orchestration ────────────────────────────────────────────
async def run_sync(source: SpaceSource, repo: MerchantSyncRepo) -> dict[str, int]:
    """
    Exécute une passe de synchronisation idempotente.
    Retourne le décompte {merchants, products, skipped}.
    """
    stores = await source.fetch_published_stores()
    merchants = products = skipped = 0

    for store in stores:
        store_id = store.get("id")
        if not store_id:
            skipped += 1
            continue

        fields = store_to_merchant_fields(store)
        if fields is None:
            logger.info("Store %s ignoré (pas de géolocalisation).", store_id)
            skipped += 1
            continue

        merchant_pk = await repo.upsert_merchant(store_id, fields)
        merchants += 1

        for product in await source.fetch_store_products(store_id):
            product_id = product.get("id")
            if not product_id:
                continue
            await repo.upsert_product(product_id, product_to_fields(product, merchant_pk))
            products += 1

    result = {"merchants": merchants, "products": products, "skipped": skipped}
    logger.info("Sync terminée : %s", result)
    return result
