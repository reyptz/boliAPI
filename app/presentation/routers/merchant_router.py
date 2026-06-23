from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional, Annotated
from sqlalchemy import select, cast, func
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2 import Geography
from geoalchemy2.functions import ST_DWithin, ST_Distance
from geoalchemy2.shape import to_shape

from app.presentation.dependencies import get_db
from app.infrastructure.persistence.models import MerchantModel, ProductModel

merchant_router = APIRouter(prefix="/merchants", tags=["Marketplace"])

VALID_CATEGORIES = {"vendeur", "restaurant", "atelier", "salon", "ferme"}


class ProductOut(BaseModel):
    id: str
    erp_product_id: str | None
    name: str
    description: str | None
    price: float
    stock: int | None
    is_available: bool


class MerchantOut(BaseModel):
    id: str
    name: str
    category: str
    subcategory: str | None
    latitude: float
    longitude: float
    is_open: bool
    is_published: bool
    erp_merchant_id: str | None


class MerchantDetailOut(MerchantOut):
    products: List[ProductOut] = []


class CategoryCountOut(BaseModel):
    category: str
    count: int


def _merchant_to_out(m: MerchantModel) -> MerchantOut:
    shape = to_shape(m.location)
    return MerchantOut(
        id=m.id,
        name=m.name,
        category=m.category,
        subcategory=m.subcategory,
        latitude=shape.y,
        longitude=shape.x,
        is_open=m.is_open,
        is_published=m.is_published,
        erp_merchant_id=m.erp_merchant_id,
    )


@merchant_router.get("/nearby", response_model=List[MerchantOut])
async def get_nearby_merchants(
    latitude: float,
    longitude: float,
    radius_km: float = 5.0,
    category: Optional[str] = Query(None, description="Filtrer par catégorie (vendeur|restaurant|atelier|salon|ferme)"),
    is_open: Optional[bool] = Query(None, description="Filtrer par statut ouvert"),
    db: AsyncSession = Depends(get_db),
):
    """Marchands publiés à proximité — triés par distance croissante."""
    if category and category not in VALID_CATEGORIES:
        raise HTTPException(status_code=422, detail=f"Catégorie invalide. Valeurs acceptées : {', '.join(VALID_CATEGORIES)}")

    point_wkt = f"SRID=4326;POINT({longitude} {latitude})"
    geo_col = cast(MerchantModel.location, Geography)
    point_geo = cast(point_wkt, Geography)

    stmt = (
        select(MerchantModel)
        .where(
            MerchantModel.is_published == True,
            ST_DWithin(geo_col, point_geo, radius_km * 1000.0),
        )
        .order_by(ST_Distance(geo_col, point_geo))
    )

    if category:
        stmt = stmt.where(MerchantModel.category == category)
    if is_open is not None:
        stmt = stmt.where(MerchantModel.is_open == is_open)

    result = await db.execute(stmt)
    return [_merchant_to_out(m) for m in result.scalars().all()]


@merchant_router.get("/categories", response_model=List[CategoryCountOut])
async def get_merchant_categories(db: AsyncSession = Depends(get_db)):
    """Nombre de marchands publiés par catégorie."""
    stmt = (
        select(MerchantModel.category, func.count().label("count"))
        .where(MerchantModel.is_published == True)
        .group_by(MerchantModel.category)
        .order_by(func.count().desc())
    )
    result = await db.execute(stmt)
    return [CategoryCountOut(category=row.category, count=row.count) for row in result.all()]


@merchant_router.get("", response_model=List[MerchantOut])
async def list_merchants(
    category: Optional[str] = Query(None),
    is_open: Optional[bool] = Query(None),
    search: Optional[str] = Query(None, description="Recherche par nom (insensible à la casse)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Liste paginée des marchands publiés avec filtres optionnels."""
    if category and category not in VALID_CATEGORIES:
        raise HTTPException(status_code=422, detail=f"Catégorie invalide. Valeurs acceptées : {', '.join(VALID_CATEGORIES)}")

    stmt = select(MerchantModel).where(MerchantModel.is_published == True)

    if category:
        stmt = stmt.where(MerchantModel.category == category)
    if is_open is not None:
        stmt = stmt.where(MerchantModel.is_open == is_open)
    if search:
        stmt = stmt.where(MerchantModel.name.ilike(f"%{search}%"))

    stmt = stmt.order_by(MerchantModel.name).limit(limit).offset(offset)

    result = await db.execute(stmt)
    return [_merchant_to_out(m) for m in result.scalars().all()]


@merchant_router.get("/{merchant_id}", response_model=MerchantDetailOut)
async def get_merchant(merchant_id: str, db: AsyncSession = Depends(get_db)):
    """Détail d'un marchand avec ses produits disponibles."""
    m = await db.get(MerchantModel, merchant_id)
    if not m:
        raise HTTPException(status_code=404, detail="Marchand introuvable.")

    products_stmt = (
        select(ProductModel)
        .where(ProductModel.merchant_id == merchant_id, ProductModel.is_available == True)
        .order_by(ProductModel.name)
    )
    result = await db.execute(products_stmt)
    products = result.scalars().all()

    shape = to_shape(m.location)
    return MerchantDetailOut(
        id=m.id,
        name=m.name,
        category=m.category,
        subcategory=m.subcategory,
        latitude=shape.y,
        longitude=shape.x,
        is_open=m.is_open,
        is_published=m.is_published,
        erp_merchant_id=m.erp_merchant_id,
        products=[
            ProductOut(
                id=p.id,
                erp_product_id=p.erp_product_id,
                name=p.name,
                description=p.description,
                price=float(p.price),
                stock=p.stock,
                is_available=p.is_available,
            )
            for p in products
        ],
    )


@merchant_router.get("/{merchant_id}/products", response_model=List[ProductOut])
async def get_merchant_products(
    merchant_id: str,
    available_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(ProductModel).where(ProductModel.merchant_id == merchant_id)
    if available_only:
        stmt = stmt.where(ProductModel.is_available == True)
    result = await db.execute(stmt)
    return [
        ProductOut(
            id=p.id,
            erp_product_id=p.erp_product_id,
            name=p.name,
            description=p.description,
            price=float(p.price),
            stock=p.stock,
            is_available=p.is_available,
        )
        for p in result.scalars().all()
    ]
