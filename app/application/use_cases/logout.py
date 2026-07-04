"""
Use Case — Déconnexion (blacklist du token courant).
"""

from __future__ import annotations

from app.infrastructure.security.jwt_handler import blacklist_token


class LogoutUseCase:
    """Invalide le token JWT courant."""

    async def execute(self, *, token: str) -> dict:
        """
        Blackliste le token pour empêcher sa réutilisation.

        Args:
            token: Le JWT access token à invalider.
        """
        await blacklist_token(token)
        return {"message": "Déconnexion réussie."}
