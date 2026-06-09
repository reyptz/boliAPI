"""
Use Case — Demande de réinitialisation de mot de passe.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.domain.repositories.user_repository import UserRepository


class ForgotPasswordUseCase:
    """Génère un token de reset et le log en console (simulé)."""

    def __init__(self, repo: UserRepository):
        self._repo = repo

    async def execute(self, *, identifier: str) -> dict:
        """
        Recherche l'utilisateur et génère un token de reset.
        Ne révèle pas si le compte existe ou non (sécurité).
        """
        generic_message = (
            "Si un compte existe avec cet identifiant, "
            "un code de réinitialisation a été envoyé."
        )

        user = await self._repo.get_by_identifier(identifier)
        if not user:
            # Ne pas révéler l'inexistence du compte
            return {"message": generic_message, "debug_token": None}

        # Générer un token de reset (UUID + expire en 15 min)
        reset_token = str(uuid.uuid4())
        user.reset_token = reset_token
        user.reset_token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

        await self._repo.update(user)

        # En mode dev : afficher le token en console
        debug_token = None
        if settings.DEBUG:
            print(f"\n{'='*50}")
            print(f"[RESET TOKEN] for {user.display_identifier}")
            print(f"  Token : {reset_token}")
            print(f"  Expires in 15 minutes")
            print(f"{'='*50}\n")
            debug_token = reset_token

        return {"message": generic_message, "debug_token": debug_token}
