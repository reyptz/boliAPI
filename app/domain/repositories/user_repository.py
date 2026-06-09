"""
Interface abstraite du repository User.
Contrat que l'infrastructure doit respecter.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from app.domain.entities.user import UserEntity


class UserRepository(ABC):
    """Port de persistance pour les entités User."""

    # ── Création ─────────────────────────────────────────────
    @abstractmethod
    async def create(self, user: UserEntity) -> UserEntity:
        """Persister un nouvel utilisateur."""
        ...

    # ── Lecture ───────────────────────────────────────────────
    @abstractmethod
    async def get_by_id(self, user_id: uuid.UUID) -> UserEntity | None:
        """Récupérer un utilisateur par son UUID."""
        ...

    @abstractmethod
    async def get_by_phone(self, phone: str) -> UserEntity | None:
        """Récupérer un utilisateur par numéro de téléphone."""
        ...

    @abstractmethod
    async def get_by_email(self, email: str) -> UserEntity | None:
        """Récupérer un utilisateur par email."""
        ...

    @abstractmethod
    async def get_by_username(self, username: str) -> UserEntity | None:
        """Récupérer un utilisateur par nom d'utilisateur."""
        ...

    async def get_by_identifier(self, identifier: str) -> UserEntity | None:
        """
        Résout un identifiant flexible (phone, email ou username).
        Essaye dans l'ordre : phone → email → username.
        """
        user = await self.get_by_phone(identifier)
        if user:
            return user
        user = await self.get_by_email(identifier)
        if user:
            return user
        return await self.get_by_username(identifier)

    @abstractmethod
    async def get_by_reset_token(self, token: str) -> UserEntity | None:
        """Récupérer un utilisateur par son token de reset."""
        ...

    # ── Liste ────────────────────────────────────────────────
    @abstractmethod
    async def list_all(
        self,
        *,
        role: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[UserEntity], int]:
        """Lister les utilisateurs avec pagination et filtre optionnel par rôle.
        Retourne (liste, total_count)."""
        ...

    # ── Mise à jour ──────────────────────────────────────────
    @abstractmethod
    async def update(self, user: UserEntity) -> UserEntity:
        """Mettre à jour un utilisateur existant."""
        ...

    # ── Suppression ──────────────────────────────────────────
    @abstractmethod
    async def delete(self, user_id: uuid.UUID) -> bool:
        """Supprimer un utilisateur. Retourne True si supprimé."""
        ...

    # ── Vérification d'unicité ───────────────────────────────
    @abstractmethod
    async def exists_by_phone(self, phone: str) -> bool:
        ...

    @abstractmethod
    async def exists_by_email(self, email: str) -> bool:
        ...

    @abstractmethod
    async def exists_by_username(self, username: str) -> bool:
        ...
