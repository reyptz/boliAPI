"""
Use Case — Inscription d'un nouvel utilisateur.
"""

from __future__ import annotations

from app.domain.entities.user import UserEntity
from app.domain.exceptions import (
    MissingCredentialError,
    MissingIdentifierError,
    UserAlreadyExistsError,
)
from app.domain.repositories.user_repository import UserRepository
from app.infrastructure.security.jwt_handler import create_access_token, create_refresh_token
from app.infrastructure.security.password_hasher import hash_password, hash_pin


class SignUpUseCase:
    """Orchestrateur de l'inscription utilisateur."""

    def __init__(self, repo: UserRepository):
        self._repo = repo

    async def execute(
        self,
        *,
        phone: str | None = None,
        email: str | None = None,
        username: str | None = None,
        password: str | None = None,
        pin: str | None = None,
        role: str = "client",
    ) -> dict:
        """
        Inscrit un utilisateur.

        Returns:
            dict avec access_token, refresh_token, user_id, role.
        """
        # 1. Vérifier qu'au moins un identifiant est fourni
        if not any([phone, email, username]):
            raise MissingIdentifierError()

        # 2. Vérifier qu'au moins un secret est fourni
        if not password and not pin:
            raise MissingCredentialError()

        # 3. Vérifier l'unicité de chaque identifiant fourni
        if phone and await self._repo.exists_by_phone(phone):
            raise UserAlreadyExistsError("Ce numéro de téléphone est déjà utilisé.")
        if email and await self._repo.exists_by_email(email):
            raise UserAlreadyExistsError("Cet email est déjà utilisé.")
        if username and await self._repo.exists_by_username(username):
            raise UserAlreadyExistsError("Ce nom d'utilisateur est déjà pris.")

        # 4. Créer l'entité
        user = UserEntity(
            phone=phone,
            email=email,
            username=username,
            password_hash=hash_password(password) if password else None,
            pin_hash=hash_pin(pin) if pin else None,
            role=role,
        )

        # 5. Persister
        created_user = await self._repo.create(user)

        # 6. Générer les tokens
        access_token = create_access_token(str(created_user.id), created_user.role.value)
        refresh_token = create_refresh_token(str(created_user.id))

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user_id": str(created_user.id),
            "role": created_user.role.value,
            "requires_2fa": False,
        }
