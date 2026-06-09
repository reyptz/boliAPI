"""
Use Case — Réinitialisation du mot de passe avec le token.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.domain.exceptions import InvalidResetTokenError
from app.domain.repositories.user_repository import UserRepository
from app.infrastructure.security.password_hasher import hash_password


class ResetPasswordUseCase:
    """Valide le token de reset et met à jour le mot de passe."""

    def __init__(self, repo: UserRepository):
        self._repo = repo

    async def execute(self, *, token: str, new_password: str) -> dict:
        """
        Réinitialise le mot de passe.

        Args:
            token: Token de reset reçu par l'utilisateur.
            new_password: Nouveau mot de passe en clair.
        """
        # 1. Trouver l'utilisateur par le token
        user = await self._repo.get_by_reset_token(token)
        if not user:
            raise InvalidResetTokenError()

        # 2. Vérifier l'expiration
        if (
            user.reset_token != token
            or user.reset_token_expires_at is None
            or user.reset_token_expires_at < datetime.now(timezone.utc).replace(tzinfo=None)
        ):
            raise InvalidResetTokenError("Le token de réinitialisation a expiré.")

        # 3. Mettre à jour le mot de passe
        user.password_hash = hash_password(new_password)
        user.reset_token = None
        user.reset_token_expires_at = None

        await self._repo.update(user)

        return {"message": "Mot de passe réinitialisé avec succès."}
