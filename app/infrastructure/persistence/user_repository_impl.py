"""
Implémentation concrète du UserRepository avec SQLAlchemy async.
"""

from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.user import UserEntity
from app.domain.enums.user_role import UserRole
from app.domain.repositories.user_repository import UserRepository
from app.infrastructure.persistence.models import UserModel


class SQLAlchemyUserRepository(UserRepository):
    """Accès aux données utilisateur via SQLAlchemy."""

    def __init__(self, session: AsyncSession):
        self._session = session

    # ── Mapping ORM ↔ Entity ─────────────────────────────────

    @staticmethod
    def _to_entity(model: UserModel) -> UserEntity:
        """Convertit un modèle ORM en entité domaine."""
        return UserEntity(
            id=uuid.UUID(model.id),
            phone=model.phone,
            email=model.email,
            username=model.username,
            password_hash=model.password_hash,
            pin_hash=model.pin_hash,
            role=UserRole(model.role),
            is_active=model.is_active,
            vehicle_type=model.vehicle_type,
            is_2fa_enabled=model.is_2fa_enabled,
            totp_secret=model.totp_secret,
            subscription_status=model.subscription_status,
            subscription_expires_at=model.subscription_expires_at,
            reset_token=model.reset_token,
            reset_token_expires_at=model.reset_token_expires_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _to_model(entity: UserEntity) -> UserModel:
        """Convertit une entité domaine en modèle ORM."""
        return UserModel(
            id=str(entity.id),
            phone=entity.phone,
            email=entity.email,
            username=entity.username,
            password_hash=entity.password_hash,
            pin_hash=entity.pin_hash,
            role=entity.role.value if hasattr(entity.role, "value") else entity.role,
            is_active=entity.is_active,
            vehicle_type=entity.vehicle_type,
            is_2fa_enabled=entity.is_2fa_enabled,
            totp_secret=entity.totp_secret,
            subscription_status=entity.subscription_status,
            subscription_expires_at=entity.subscription_expires_at,
            reset_token=entity.reset_token,
            reset_token_expires_at=entity.reset_token_expires_at,
        )

    # ── Création ─────────────────────────────────────────────

    async def create(self, user: UserEntity) -> UserEntity:
        model = self._to_model(user)
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return self._to_entity(model)

    # ── Lecture ───────────────────────────────────────────────

    async def get_by_id(self, user_id: uuid.UUID) -> UserEntity | None:
        stmt = select(UserModel).where(UserModel.id == str(user_id))
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_phone(self, phone: str) -> UserEntity | None:
        stmt = select(UserModel).where(UserModel.phone == phone)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_email(self, email: str) -> UserEntity | None:
        stmt = select(UserModel).where(UserModel.email == email)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_username(self, username: str) -> UserEntity | None:
        stmt = select(UserModel).where(UserModel.username == username)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_reset_token(self, token: str) -> UserEntity | None:
        stmt = select(UserModel).where(UserModel.reset_token == token)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    # ── Liste ────────────────────────────────────────────────

    async def list_all(
        self,
        *,
        role: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[UserEntity], int]:
        # Query de base
        stmt = select(UserModel)
        count_stmt = select(func.count()).select_from(UserModel)

        if role:
            stmt = stmt.where(UserModel.role == role)
            count_stmt = count_stmt.where(UserModel.role == role)

        # Total
        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar() or 0

        # Liste paginée
        stmt = stmt.offset(offset).limit(limit).order_by(UserModel.created_at.desc())
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._to_entity(m) for m in models], total

    # ── Mise à jour ──────────────────────────────────────────

    async def update(self, user: UserEntity) -> UserEntity:
        stmt = select(UserModel).where(UserModel.id == str(user.id))
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            raise ValueError(f"User {user.id} not found for update")

        # Mettre à jour tous les champs depuis l'entité
        model.phone = user.phone
        model.email = user.email
        model.username = user.username
        model.password_hash = user.password_hash
        model.pin_hash = user.pin_hash
        model.role = user.role.value if hasattr(user.role, "value") else user.role
        model.is_active = user.is_active
        model.vehicle_type = user.vehicle_type
        model.is_2fa_enabled = user.is_2fa_enabled
        model.totp_secret = user.totp_secret
        model.subscription_status = user.subscription_status
        model.subscription_expires_at = user.subscription_expires_at
        model.reset_token = user.reset_token
        model.reset_token_expires_at = user.reset_token_expires_at

        await self._session.commit()
        await self._session.refresh(model)
        return self._to_entity(model)

    # ── Suppression ──────────────────────────────────────────

    async def delete(self, user_id: uuid.UUID) -> bool:
        stmt = delete(UserModel).where(UserModel.id == str(user_id))
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount > 0

    # ── Vérification d'unicité ───────────────────────────────

    async def exists_by_phone(self, phone: str) -> bool:
        stmt = select(func.count()).select_from(UserModel).where(UserModel.phone == phone)
        result = await self._session.execute(stmt)
        return (result.scalar() or 0) > 0

    async def exists_by_email(self, email: str) -> bool:
        stmt = select(func.count()).select_from(UserModel).where(UserModel.email == email)
        result = await self._session.execute(stmt)
        return (result.scalar() or 0) > 0

    async def exists_by_username(self, username: str) -> bool:
        stmt = (
            select(func.count()).select_from(UserModel).where(UserModel.username == username)
        )
        result = await self._session.execute(stmt)
        return (result.scalar() or 0) > 0
