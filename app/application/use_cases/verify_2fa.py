"""
Use Case — Vérification du code 2FA TOTP.
Utilisé pour :
  1. Confirmer l'activation du 2FA (première vérification après enable).
  2. Compléter le sign-in quand le 2FA est actif.
"""

from __future__ import annotations

import uuid

from app.domain.exceptions import (
    Invalid2FACodeError,
    TwoFANotEnabledError,
    UserNotFoundError,
)
from app.domain.repositories.user_repository import UserRepository
from app.infrastructure.security.jwt_handler import create_access_token, create_refresh_token
from app.infrastructure.security.totp_handler import verify_code


class Verify2FAUseCase:
    """Vérifie un code TOTP et finalise l'action (activation ou login)."""

    def __init__(self, repo: UserRepository):
        self._repo = repo

    async def execute(self, *, user_id: str, code: str) -> dict:
        """
        Vérifie le code TOTP.

        Si c'est la première vérification → active le 2FA sur le compte.
        Dans tous les cas → retourne les tokens JWT finaux.
        """
        user = await self._repo.get_by_id(uuid.UUID(user_id))
        if not user:
            raise UserNotFoundError()

        if not user.totp_secret:
            raise TwoFANotEnabledError(
                "Aucun secret 2FA configuré. Activez d'abord le 2FA."
            )

        # Vérifier le code TOTP
        if not verify_code(user.totp_secret, code):
            raise Invalid2FACodeError()

        # Si le 2FA n'était pas encore activé → l'activer maintenant
        if not user.is_2fa_enabled:
            user.is_2fa_enabled = True
            await self._repo.update(user)

        # Générer les tokens finaux
        access_token = create_access_token(str(user.id), user.role.value)
        refresh_token = create_refresh_token(str(user.id))

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user_id": str(user.id),
            "role": user.role.value,
            "requires_2fa": False,
        }
