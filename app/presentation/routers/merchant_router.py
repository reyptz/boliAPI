from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Annotated
from sqlalchemy import select, cast
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2 import Geography
from geoalchemy2.functions import ST_DWithin
from geoalchemy2.shape import to_shape

from app.presentation.dependencies import get_db
from app.infrastructure.persistence.models import MerchantModel, ProductModel, UserModel

merchant_router = APIRouter(prefix="/merchants", tags=["Marketplace"])

class ProductOut(BaseModel):
    id: str
    name: str
    description: str | None
    price: float
    is_available: bool

class MerchantOut(BaseModel):
    id: str
    name: str
    category: str
    latitude: float
    longitude: float
    is_open: bool

@merchant_router.get("/nearby", response_model=List[MerchantOut])
async def get_nearby_merchants(
    latitude: float,
    longitude: float,
    radius_km: float = 5.0,
    db: AsyncSession = Depends(get_db)
):
    """
    Retourne les marchands à proximité en utilisant une requête spatiale PostGIS.
    """
    radius_meters = radius_km * 1000.0
    stmt = select(MerchantModel).where(
        ST_DWithin(
            cast(MerchantModel.location, Geography),
            cast(f"SRID=4326;POINT({longitude} {latitude})", Geography),
            radius_meters
        )
    )
    result = await db.execute(stmt)
    merchants = result.scalars().all()
    
    out = []
    for m in merchants:
        shape = to_shape(m.location)
        out.append(MerchantOut(
            id=m.id,
            name=m.name,
            category=m.category,
            latitude=shape.y,
            longitude=shape.x,
            is_open=m.is_open
        ))
    return out

@merchant_router.get("/{merchant_id}/products", response_model=List[ProductOut])
async def get_merchant_products(merchant_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(ProductModel).where(ProductModel.merchant_id == merchant_id)
    result = await db.execute(stmt)
    products = result.scalars().all()
    return [
        ProductOut(
            id=p.id,
            name=p.name,
            description=p.description,
            price=float(p.price),
            is_available=p.is_available
        ) for p in products
    ]

@merchant_router.post("/seed")
async def seed_merchants(db: AsyncSession = Depends(get_db)):
    """
    Seeder de test : crée des marchands et produits factices autour de Bamako.
    """
    # 1. Vérifier si des marchands existent déjà
    check = await db.execute(select(MerchantModel).limit(1))
    if check.scalar_one_or_none():
        return {"message": "La base contient déjà des marchands. Pas de seeding nécessaire."}

    try:
        # Créer des utilisateurs associés aux marchands
        merchants_data = [
            {"name": "Restaurant Saveurs du Mali", "cat": "restaurant", "lat": 12.6392, "lng": -8.0029, "erp": "ERP_REST_01"},
            {"name": "Pharmacie du Progrès", "cat": "pharmacy", "lat": 12.6450, "lng": -7.9950, "erp": "ERP_PHAR_02"},
            {"name": "Supermarché Bamako Central", "cat": "supermarket", "lat": 12.6300, "lng": -8.0100, "erp": "ERP_SUP_03"}
        ]
        
        for idx, m_data in enumerate(merchants_data):
            user = UserModel(
                id=f"merchant_user_id_{idx}",
                phone=f"+2237000000{idx}",
                email=f"merchant{idx}@boli.ml",
                role="merchant",
                password_hash="seeded_password"
            )
            db.add(user)
            await db.flush()
            
            merchant = MerchantModel(
                id=user.id,
                erp_merchant_id=m_data["erp"],
                name=m_data["name"],
                category=m_data["cat"],
                location=f"SRID=4326;POINT({m_data['lng']} {m_data['lat']})",
                is_open=True
            )
            db.add(merchant)
            await db.flush()
            
            # Ajouter des produits
            if m_data["cat"] == "restaurant":
                db.add(ProductModel(merchant_id=merchant.id, name="Plat de Thiéboudienne", price=2500, description="Riz au poisson traditionnel sénégalais."))
                db.add(ProductModel(merchant_id=merchant.id, name="Bissap Glacé", price=500, description="Jus de fleur d'hibiscus frais."))
            elif m_data["cat"] == "pharmacy":
                db.add(ProductModel(merchant_id=merchant.id, name="Boîte de Paracétamol", price=1200, description="500mg - 20 comprimés."))
                db.add(ProductModel(merchant_id=merchant.id, name="Gel Hydroalcoolique", price=1500, description="Flacon de 250ml."))
            else:
                db.add(ProductModel(merchant_id=merchant.id, name="Sac de Riz 5kg", price=4500, description="Riz brisé parfumé."))
                db.add(ProductModel(merchant_id=merchant.id, name="Bouteille d'Huile 1L", price=1800, description="Huile végétale de cuisson."))
        
        await db.commit()
        return {"status": "success", "message": "Marchands et produits seedés avec succès !"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur de seeding : {e}")
