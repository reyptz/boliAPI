"""
Moteur de base de données async SQLAlchemy + session factory.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# ── Engine ───────────────────────────────────────────────────
_connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}
elif "ssl=require" in settings.DATABASE_URL:
    _connect_args = {"ssl": "require"}

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    connect_args=_connect_args,
)

# ── Session factory ──────────────────────────────────────────
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Base déclarative ─────────────────────────────────────────
class Base(DeclarativeBase):
    """Classe de base pour tous les modèles ORM."""
    pass


# ── Helpers ──────────────────────────────────────────────────
async def create_tables() -> None:
    """Crée toutes les tables en base."""
    async with engine.begin() as conn:
        if settings.DATABASE_URL.startswith("postgresql"):
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis CASCADE;"))
        await conn.run_sync(Base.metadata.create_all)



async def get_async_session() -> AsyncSession:
    """Génère une session async pour l'injection de dépendances."""
    async with async_session_factory() as session:
        yield session

