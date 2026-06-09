"""
Gestion des tokens JWT — access, refresh, et blacklist.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config import settings

# ── Blacklist en mémoire (MVP — passer à Redis en prod) ─────
_token_blacklist: set[str] = set()


# ── Création de tokens ───────────────────────────────────────


def create_access_token(
    user_id: str,
    role: str,
    *,
    is_temp_2fa: bool = False,
) -> str:
    """
    Crée un JWT access token.

    Args:
        user_id: UUID de l'utilisateur.
        role: Rôle de l'utilisateur.
        is_temp_2fa: Si True, crée un token temporaire (5 min) pour le flow 2FA.
    """
    expire_delta = (
        timedelta(minutes=5)
        if is_temp_2fa
        else timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    expire = datetime.now(timezone.utc) + expire_delta

    payload = {
        "sub": user_id,
        "role": role,
        "type": "2fa_pending" if is_temp_2fa else "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    """Crée un JWT refresh token (longue durée)."""
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload = {
        "sub": user_id,
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


# ── Décodage & validation ────────────────────────────────────


def decode_token(token: str) -> dict | None:
    """
    Décode et valide un JWT.
    Retourne le payload ou None si le token est invalide/expiré/blacklisté.
    """
    if token in _token_blacklist:
        return None

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError:
        return None


# ── Blacklist ────────────────────────────────────────────────


def blacklist_token(token: str) -> None:
    """Ajoute un token à la blacklist (logout)."""
    _token_blacklist.add(token)


def is_token_blacklisted(token: str) -> bool:
    """Vérifie si un token est blacklisté."""
    return token in _token_blacklist
