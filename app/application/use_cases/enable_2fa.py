"""
Use Case — Activation du 2FA TOTP.
"""

from __future__ import annotations

import uuid

from app.domain.exceptions import TwoFAAlreadyEnabledError, UserNotFoundError
from app.domain.repositories.user_repository import UserRepository
from app.infrastructure.security.totp_handler import generate_secret, get_provisioning_uri


class Enable2FAUseCase:
    """Génère un secret TOTP et retourne le provisioning URI."""

    def __init__(self, repo: UserRepository):
        self._repo = repo

    async def execute(self, *, user_id: str) -> dict:
        """
        Active le 2FA pour un utilisateur.

        Returns:
            dict avec secret et provisioning_uri pour QR code.
        """
        user = await self._repo.get_by_id(uuid.UUID(user_id))
        if not user:
            raise UserNotFoundError()

        if user.is_2fa_enabled:
            raise TwoFAAlreadyEnabledError()

        # Générer le secret TOTP
        secret = generate_secret()
        user.totp_secret = secret
        # NOTE: on n'active pas encore is_2fa_enabled — on attend la vérification
        await self._repo.update(user)

        # Générer le provisioning URI
        identifier = user.display_identifier
        uri = get_provisioning_uri(secret, identifier)

        return {
            "secret": secret,
            "provisioning_uri": uri,
            "message": (
                "Scannez le QR code avec Google Authenticator ou Authy, "
                "puis vérifiez avec un code."
            ),
        }
