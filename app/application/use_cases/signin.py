"""
Use Case — Connexion utilisateur (Sign In).
"""

from __future__ import annotations

from app.domain.exceptions import (
    AccountDisabledError,
    InvalidCredentialsError,
    UserNotFoundError,
)
from app.domain.repositories.user_repository import UserRepository
from app.infrastructure.security.jwt_handler import create_access_token, create_refresh_token
from app.infrastructure.security.password_hasher import verify_password, verify_pin


class SignInUseCase:
    """Orchestrateur de la connexion utilisateur."""

    def __init__(self, repo: UserRepository):
        self._repo = repo

    async def execute(
        self,
        *,
        identifier: str,
        password: str | None = None,
        pin: str | None = None,
    ) -> dict:
        """
        Connecte un utilisateur.

        Returns:
            dict avec tokens ou indication que le 2FA est requis.
        """
        # 1. Résoudre l'identifiant (phone/email/username)
        user = await self._repo.get_by_identifier(identifier)
        if not user:
            raise UserNotFoundError("Aucun compte trouvé avec cet identifiant.")

        # 2. Vérifier que le compte est actif
        if not user.is_active:
            raise AccountDisabledError()

        # 3. Vérifier le secret (password ou PIN)
        authenticated = False

        if password and user.password_hash:
            authenticated = verify_password(password, user.password_hash)
        elif pin and user.pin_hash:
            authenticated = verify_pin(pin, user.pin_hash)

        if not authenticated:
            raise InvalidCredentialsError()

        # 4. Si 2FA est activé → retourner un token temporaire
        if user.is_2fa_enabled:
            temp_token = create_access_token(
                str(user.id), user.role.value, is_temp_2fa=True
            )
            return {
                "temp_token": temp_token,
                "token_type": "bearer",
                "requires_2fa": True,
                "message": "Veuillez entrer votre code 2FA.",
            }

        # 5. Sinon → connexion complète
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
