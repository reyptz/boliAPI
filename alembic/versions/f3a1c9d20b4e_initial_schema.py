"""Schéma initial — baseline générée depuis les modèles ORM existants.

Remplace le `create_tables()` exécuté implicitement au démarrage (non
déterministe en production) par une migration versionnée et explicite.

Revision ID: f3a1c9d20b4e
Revises:
Create Date: 2026-07-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.database import Base

# Importer tous les modèles pour peupler Base.metadata.
from app.infrastructure.persistence import models  # noqa: F401

# revision identifiers, used by Alembic.
revision: str = "f3a1c9d20b4e"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS postgis CASCADE;")
    # Baseline : délègue à SQLAlchemy la création de toutes les tables
    # connues de `Base.metadata` (schéma identique à l'ancien `create_tables()`).
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
