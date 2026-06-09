"""
Use Cases — CRUD utilisateur.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.domain.exceptions import UserAlreadyExistsError, UserNotFoundError
from app.domain.repositories.user_repository import UserRepository
from app.infrastructure.security.password_hasher import hash_password, hash_pin


class GetUserUseCase:
    """Récupère un utilisateur par son ID."""

    def __init__(self, repo: UserRepository):
        self._repo = repo

    async def execute(self, *, user_id: str) -> dict:
        user = await self._repo.get_by_id(uuid.UUID(user_id))
        if not user:
            raise UserNotFoundError()
        return {
            "id": str(user.id),
            "phone": user.phone,
            "email": user.email,
            "username": user.username,
            "role": user.role.value,
            "vehicle_type": user.vehicle_type,
            "is_active": user.is_active,
            "is_2fa_enabled": user.is_2fa_enabled,
            "subscription_status": user.subscription_status,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        }


class UpdateUserUseCase:
    """Met à jour partiellement un utilisateur."""

    def __init__(self, repo: UserRepository):
        self._repo = repo

    async def execute(
        self,
        *,
        user_id: str,
        phone: str | None = None,
        email: str | None = None,
        username: str | None = None,
        password: str | None = None,
        pin: str | None = None,
        role: str | None = None,
        vehicle_type: str | None = None,
        is_active: bool | None = None,
    ) -> dict:
        user = await self._repo.get_by_id(uuid.UUID(user_id))
        if not user:
            raise UserNotFoundError()

        # Vérifier l'unicité des identifiants modifiés
        if phone and phone != user.phone:
            if await self._repo.exists_by_phone(phone):
                raise UserAlreadyExistsError("Ce numéro de téléphone est déjà utilisé.")
            user.phone = phone

        if email and email != user.email:
            if await self._repo.exists_by_email(email):
                raise UserAlreadyExistsError("Cet email est déjà utilisé.")
            user.email = email

        if username and username != user.username:
            if await self._repo.exists_by_username(username):
                raise UserAlreadyExistsError("Ce nom d'utilisateur est déjà pris.")
            user.username = username

        if password:
            user.password_hash = hash_password(password)

        if pin:
            user.pin_hash = hash_pin(pin)

        if role is not None:
            user.role = role

        if vehicle_type is not None:
            user.vehicle_type = vehicle_type

        if is_active is not None:
            user.is_active = is_active

        user.updated_at = datetime.now(timezone.utc)
        updated = await self._repo.update(user)

        return {
            "id": str(updated.id),
            "phone": updated.phone,
            "email": updated.email,
            "username": updated.username,
            "role": updated.role.value if hasattr(updated.role, "value") else updated.role,
            "vehicle_type": updated.vehicle_type,
            "is_active": updated.is_active,
            "is_2fa_enabled": updated.is_2fa_enabled,
            "subscription_status": updated.subscription_status,
            "created_at": updated.created_at,
            "updated_at": updated.updated_at,
        }


class DeleteUserUseCase:
    """Supprime un utilisateur (hard delete)."""

    def __init__(self, repo: UserRepository):
        self._repo = repo

    async def execute(self, *, user_id: str) -> dict:
        deleted = await self._repo.delete(uuid.UUID(user_id))
        if not deleted:
            raise UserNotFoundError()
        return {"message": "Utilisateur supprimé avec succès."}


class ListUsersUseCase:
    """Liste les utilisateurs avec pagination et filtre par rôle."""

    def __init__(self, repo: UserRepository):
        self._repo = repo

    async def execute(
        self,
        *,
        role: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        offset = (page - 1) * page_size
        users, total = await self._repo.list_all(
            role=role, offset=offset, limit=page_size
        )

        return {
            "users": [
                {
                    "id": str(u.id),
                    "phone": u.phone,
                    "email": u.email,
                    "username": u.username,
                    "role": u.role.value,
                    "vehicle_type": u.vehicle_type,
                    "is_active": u.is_active,
                    "is_2fa_enabled": u.is_2fa_enabled,
                    "subscription_status": u.subscription_status,
                    "created_at": u.created_at,
                    "updated_at": u.updated_at,
                }
                for u in users
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
