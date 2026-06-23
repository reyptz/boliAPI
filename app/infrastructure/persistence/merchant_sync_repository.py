"""
Repository d'upsert SQLAlchemy pour la synchronisation marketplace.
Implémente `MerchantSyncRepo` (voir `app/infrastructure/sync/merchant_sync.py`).
Idempotent : la clé d'upsert est `erp_merchant_id` / `erp_product_id`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.models import MerchantModel, ProductModel


class SqlAlchemyMerchantSyncRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def upsert_merchant(self, erp_merchant_id: str, fields: dict[str, Any]) -> str:
        result = await self.db.execute(
            select(MerchantModel).where(MerchantModel.erp_merchant_id == erp_merchant_id)
        )
        merchant = result.scalar_one_or_none()
        if merchant is None:
            merchant = MerchantModel(erp_merchant_id=erp_merchant_id)
            self.db.add(merchant)

        merchant.name = fields["name"]
        merchant.category = fields["category"]
        merchant.subcategory = fields.get("subcategory")
        merchant.is_open = fields["is_open"]
        merchant.is_published = fields["is_published"]
        merchant.location = fields["location_wkt"]

        await self.db.flush()
        return merchant.id

    async def upsert_product(self, erp_product_id: str, fields: dict[str, Any]) -> None:
        result = await self.db.execute(
            select(ProductModel).where(ProductModel.erp_product_id == erp_product_id)
        )
        product = result.scalar_one_or_none()
        if product is None:
            product = ProductModel(erp_product_id=erp_product_id)
            self.db.add(product)

        product.merchant_id = fields["merchant_id"]
        product.name = fields["name"]
        product.description = fields.get("description")
        product.price = fields["price"]
        product.stock = fields.get("stock")
        product.is_available = fields["is_available"]

        await self.db.flush()
