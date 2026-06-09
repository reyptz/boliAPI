"""
Entité User — objet métier pur, sans dépendance infrastructure.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.domain.enums.user_role import UserRole


@dataclass
class UserEntity:
    """Représentation métier d'un utilisateur Boli."""

    # ── Identité ─────────────────────────────────────────────
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    phone: str | None = None
    email: str | None = None
    username: str | None = None

    # ── Secrets ──────────────────────────────────────────────
    password_hash: str | None = None
    pin_hash: str | None = None

    # ── Rôle & statut ────────────────────────────────────────
    role: UserRole = UserRole.CLIENT
    is_active: bool = True
    vehicle_type: str | None = None  # moto, voiture, velo

    # ── 2FA ──────────────────────────────────────────────────
    is_2fa_enabled: bool = False
    totp_secret: str | None = None

    # ── Abonnement ───────────────────────────────────────────
    subscription_status: str = "none"
    subscription_expires_at: datetime | None = None

    # ── Reset password ───────────────────────────────────────
    reset_token: str | None = None
    reset_token_expires_at: datetime | None = None

    # ── Timestamps ───────────────────────────────────────────
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    # ── Helpers ──────────────────────────────────────────────
    @property
    def display_identifier(self) -> str:
        """Retourne l'identifiant le plus pertinent pour l'affichage."""
        return self.username or self.phone or self.email or str(self.id)

    def has_identifier(self) -> bool:
        """Vérifie qu'au moins un identifiant est renseigné."""
        return bool(self.phone or self.email or self.username)
