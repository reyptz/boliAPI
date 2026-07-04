"""
Injection de dépendances FastAPI — DB session, utilisateur courant, rôles.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.domain.enums.user_role import UserRole
from app.infrastructure.persistence.user_repository_impl import SQLAlchemyUserRepository
from app.infrastructure.security.jwt_handler import decode_token, is_token_blacklisted

# ── Schéma de sécurité ───────────────────────────────────────
_bearer_scheme = HTTPBearer(auto_error=False)


# ── DB Session ───────────────────────────────────────────────
async def get_db(
    session: AsyncSession = Depends(get_async_session),
) -> AsyncSession:
    """Retourne la session de base de données."""
    return session


# ── Repository ───────────────────────────────────────────────
async def get_user_repository(
    db: AsyncSession = Depends(get_db),
) -> SQLAlchemyUserRepository:
    """Injecte le repository utilisateur."""
    return SQLAlchemyUserRepository(db)


# ── Utilisateur courant (via JWT) ────────────────────────────


async def get_current_user_payload(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict:
    """
    Extrait et valide le JWT Bearer token.
    Retourne le payload décodé.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token d'authentification manquant.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(credentials.credentials)
    if payload is None or await is_token_blacklisted(credentials.credentials):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Vérifier que c'est un access token (pas un refresh ou 2fa_pending)
    token_type = payload.get("type", "")
    if token_type not in ("access", "2fa_pending"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Type de token invalide.",
        )

    return payload


async def get_current_user_id(
    payload: dict = Depends(get_current_user_payload),
) -> str:
    """Retourne l'ID de l'utilisateur connecté."""
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token malformé.",
        )
    return user_id


async def get_current_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    """Retourne le token brut (pour le logout)."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token d'authentification manquant.",
        )
    return credentials.credentials


# ── Guards ───────────────────────────────────────────────────


async def require_access_token(
    payload: dict = Depends(get_current_user_payload),
) -> dict:
    """Vérifie que le token est un access token complet (pas 2fa_pending)."""
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé. Veuillez compléter l'authentification 2FA.",
        )
    return payload


async def require_admin(
    payload: dict = Depends(require_access_token),
) -> dict:
    """Vérifie que l'utilisateur est admin."""
    if payload.get("role") != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs.",
        )
    return payload


# ── Type aliases pour Depends ────────────────────────────────
CurrentUserPayload = Annotated[dict, Depends(require_access_token)]
CurrentUserId = Annotated[str, Depends(get_current_user_id)]
AdminPayload = Annotated[dict, Depends(require_admin)]
RawToken = Annotated[str, Depends(get_current_token)]
UserRepo = Annotated[SQLAlchemyUserRepository, Depends(get_user_repository)]

from app.infrastructure.persistence.ride_repository_impl import SQLAlchemyRideRepository

async def get_ride_repository(
    db: AsyncSession = Depends(get_db),
) -> SQLAlchemyRideRepository:
    """Injecte le repository de course."""
    return SQLAlchemyRideRepository(db)

RideRepo = Annotated[SQLAlchemyRideRepository, Depends(get_ride_repository)]

