"""
Tests de la synchronisation marketplace SuguJate → Boli.

Vérifie (sans dépendance Firebase ni Postgres/PostGIS) :
  - le mapping Firestore → champs marchand/produit pour chaque catégorie,
  - l'exclusion des espaces sans géolocalisation,
  - l'idempotence de la sync (2 passes ⇒ pas de doublon),
  - que chaque marchand synchronisé porte bien sa catégorie (consommée par
    l'endpoint /merchants/nearby).
"""

import pytest

from app.infrastructure.sync.merchant_sync import (
    product_to_fields,
    run_sync,
    store_to_merchant_fields,
)

# ── Données de test : un store publié par catégorie + un sans géoloc ──
SAMPLE_STORES = [
    {"id": "s_vendeur", "name": "Boutique Horizon", "category": "vendeur",
     "subcategory": "alimentation", "isOpen": True, "publishedToMarketplace": True,
     "geo": {"lat": 12.63, "lng": -8.00}},
    {"id": "s_resto", "name": "Maquis du Fleuve", "category": "restaurant",
     "subcategory": "maquis", "isOpen": True, "publishedToMarketplace": True,
     "geo": {"lat": 12.64, "lng": -7.99}},
    {"id": "s_atelier", "name": "Atelier Couture Diarra", "category": "atelier",
     "subcategory": "couture", "isOpen": False, "publishedToMarketplace": True,
     "geo": {"lat": 12.62, "lng": -8.01}},
    {"id": "s_salon", "name": "Salon Belle Vie", "category": "salon",
     "subcategory": "coiffure", "isOpen": True, "publishedToMarketplace": True,
     "geo": {"lat": 12.65, "lng": -8.02}},
    {"id": "s_ferme", "name": "Ferme Niono", "category": "ferme",
     "subcategory": "maraichage", "isOpen": True, "publishedToMarketplace": True,
     "geo": {"lat": 12.61, "lng": -7.98}},
    # Sans géolocalisation → doit être ignoré.
    {"id": "s_nogeo", "name": "Espace sans adresse", "category": "vendeur",
     "isOpen": True, "publishedToMarketplace": True},
]

PRODUCTS_BY_STORE = {
    "s_vendeur": [
        {"id": "p1", "name": "Sac de riz 5kg", "price": 4500, "stock": 30, "enabled": True},
        {"id": "p2", "name": "Huile 1L", "price": 1800, "stock": 0, "enabled": False},
    ],
    "s_resto": [
        {"id": "p3", "name": "Thiéboudienne", "price": 2500, "enabled": True},
    ],
}


class FakeSource:
    def __init__(self, stores, products_by_store):
        self._stores = stores
        self._products = products_by_store

    async def fetch_published_stores(self):
        return list(self._stores)

    async def fetch_store_products(self, store_id):
        return list(self._products.get(store_id, []))


class InMemoryRepo:
    def __init__(self):
        self.merchants = {}  # erp_merchant_id -> fields (+pk)
        self.products = {}   # erp_product_id -> fields
        self._counter = 0

    async def upsert_merchant(self, erp_merchant_id, fields):
        existing = self.merchants.get(erp_merchant_id)
        pk = existing["pk"] if existing else f"m{(self._inc())}"
        self.merchants[erp_merchant_id] = {**fields, "pk": pk}
        return pk

    async def upsert_product(self, erp_product_id, fields):
        self.products[erp_product_id] = fields

    def _inc(self):
        self._counter += 1
        return self._counter


# ── Mapping pur ──────────────────────────────────────────────
@pytest.mark.parametrize(
    "store",
    [s for s in SAMPLE_STORES if "geo" in s],
)
def test_store_mapping_per_category(store):
    fields = store_to_merchant_fields(store)
    assert fields is not None
    assert fields["category"] == store["category"]
    assert fields["subcategory"] == store["subcategory"]
    assert fields["is_open"] == store["isOpen"]
    assert fields["is_published"] is True
    # EWKT bien formé (lng avant lat).
    assert fields["location_wkt"] == f"SRID=4326;POINT({store['geo']['lng']} {store['geo']['lat']})"


def test_store_without_geo_is_skipped():
    nogeo = next(s for s in SAMPLE_STORES if s["id"] == "s_nogeo")
    assert store_to_merchant_fields(nogeo) is None


def test_product_mapping():
    fields = product_to_fields(
        {"id": "p1", "name": "Sac de riz", "price": "4500", "stock": 30, "enabled": True},
        merchant_pk="m1",
    )
    assert fields["merchant_id"] == "m1"
    assert fields["price"] == 4500.0
    assert isinstance(fields["price"], float)
    assert fields["stock"] == 30
    assert fields["is_available"] is True


# ── Orchestration ────────────────────────────────────────────
@pytest.mark.asyncio
async def test_run_sync_maps_all_categories():
    source = FakeSource(SAMPLE_STORES, PRODUCTS_BY_STORE)
    repo = InMemoryRepo()
    result = await run_sync(source, repo)

    # 5 catégories publiées avec géoloc + 1 ignorée (sans géoloc)
    assert result["merchants"] == 5
    assert result["skipped"] == 1
    assert result["products"] == 3  # 2 (vendeur) + 1 (resto)

    # Les 5 catégories sont bien présentes côté marchand.
    categories = {m["category"] for m in repo.merchants.values()}
    assert categories == {"vendeur", "restaurant", "atelier", "salon", "ferme"}


@pytest.mark.asyncio
async def test_run_sync_is_idempotent():
    source = FakeSource(SAMPLE_STORES, PRODUCTS_BY_STORE)
    repo = InMemoryRepo()

    await run_sync(source, repo)
    first_pks = {erp: m["pk"] for erp, m in repo.merchants.items()}

    await run_sync(source, repo)  # 2e passe
    second_pks = {erp: m["pk"] for erp, m in repo.merchants.items()}

    # Pas de doublon : mêmes clés ERP et mêmes PK conservés.
    assert len(repo.merchants) == 5
    assert len(repo.products) == 3
    assert first_pks == second_pks
