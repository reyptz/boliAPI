"""
DTOs pour le CRUD utilisateur.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.enums.user_role import UserRole


# ── Réponse utilisateur ──────────────────────────────────────


class UserResponse(BaseModel):
    """Représentation publique d'un utilisateur (sans secrets)."""

    id: str
    phone: str | None = None
    email: str | None = None
    username: str | None = None
    role: UserRole
    vehicle_type: str | None = None
    is_active: bool
    is_2fa_enabled: bool
    subscription_status: str
    created_at: datetime
    updated_at: datetime


# ── Mise à jour ──────────────────────────────────────────────


class UpdateUserRequest(BaseModel):
    """Requête de mise à jour partielle du profil."""

    phone: str | None = Field(None, min_length=8, max_length=20)
    email: str | None = None
    username: str | None = Field(None, min_length=3, max_length=50)
    password: str | None = Field(None, min_length=6, max_length=128)
    pin: str | None = Field(None, min_length=4, max_length=6, pattern=r"^\d{4,6}$")
    role: UserRole | None = None
    vehicle_type: str | None = Field(None, examples=["moto", "car", "bicycle"])


class AdminUpdateUserRequest(UpdateUserRequest):
    """Requête admin — peut aussi changer le statut."""

    is_active: bool | None = None


# ── Liste paginée ────────────────────────────────────────────


class UserListResponse(BaseModel):
    """Réponse paginée pour la liste des utilisateurs."""

    users: list[UserResponse]
    total: int
    page: int
    page_size: int
