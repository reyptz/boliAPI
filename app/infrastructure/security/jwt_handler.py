"""
Gestion des tokens JWT — access, refresh, et blacklist (Redis).

La blacklist est stockée dans Redis afin d'être **partagée entre tous les
workers/instances** et de survivre à un redémarrage. Un TTL égal à la durée de
vie restante du token évite d'accumuler des entrées inutiles. En l'absence de
Redis (tests locaux), un fallback en mémoire est utilisé.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import redis.asyncio as redis
from jose import JWTError, jwt

from app.config import settings

logger = logging.getLogger("boli-api.jwt")

_BLACKLIST_PREFIX = "jwt:blacklist:"

# Fallback en mémoire si Redis est indisponible.
_memory_blacklist: set[str] = set()

# Client Redis paresseux (partagé).
_redis_client: redis.Redis | None = None


def _get_redis() -> redis.Redis | None:
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        except Exception as exc:  # pragma: no cover
            logger.warning("Redis indisponible pour la blacklist JWT: %s", exc)
            return None
    return _redis_client


# ── Création de tokens ───────────────────────────────────────


def create_access_token(user_id: str, role: str, *, is_temp_2fa: bool = False) -> str:
    """Crée un JWT access token (ou un token temporaire 2FA de 5 min)."""
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
    expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
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
    Décode et valide la signature/expiration d'un JWT.
    Retourne le payload ou None si le token est invalide/expiré.
    NB : la vérification de blacklist est asynchrone (voir `is_token_blacklisted`).
    """
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


# ── Blacklist ────────────────────────────────────────────────


def _remaining_ttl(token: str) -> int:
    """Durée de vie restante (secondes) du token, pour caler le TTL Redis."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_exp": False},
        )
        exp = payload.get("exp")
        if exp:
            remaining = int(exp - datetime.now(timezone.utc).timestamp())
            return max(remaining, 1)
    except JWTError:
        pass
    # Par défaut : durée de vie max d'un refresh token.
    return settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400


async def blacklist_token(token: str) -> None:
    """Ajoute un token à la blacklist (logout) avec TTL = expiration du token."""
    client = _get_redis()
    if client is None:
        _memory_blacklist.add(token)
        return
    try:
        await client.set(_BLACKLIST_PREFIX + token, "1", ex=_remaining_ttl(token))
    except Exception as exc:
        logger.warning("Échec blacklist Redis, fallback mémoire: %s", exc)
        _memory_blacklist.add(token)


async def is_token_blacklisted(token: str) -> bool:
    """Vérifie si un token est blacklisté (Redis puis fallback mémoire)."""
    if token in _memory_blacklist:
        return True
    client = _get_redis()
    if client is None:
        return False
    try:
        return await client.exists(_BLACKLIST_PREFIX + token) == 1
    except Exception as exc:
        logger.warning("Échec lecture blacklist Redis: %s", exc)
        return False
