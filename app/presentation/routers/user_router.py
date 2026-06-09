"""
Router CRUD utilisateur — endpoints /users/*.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.application.dto.user_dto import (
    AdminUpdateUserRequest,
    UpdateUserRequest,
    UserListResponse,
    UserResponse,
)
from app.application.dto.auth_dto import MessageResponse
from app.application.use_cases.user_crud import (
    DeleteUserUseCase,
    GetUserUseCase,
    ListUsersUseCase,
    UpdateUserUseCase,
)
from app.domain.exceptions import DomainException
from app.presentation.dependencies import AdminPayload, CurrentUserPayload, UserRepo

router = APIRouter(prefix="/users", tags=["Users"])


# ── Helper ───────────────────────────────────────────────────
def _handle(exc: DomainException):
    raise HTTPException(status_code=exc.status_code, detail=exc.detail)


# ─────────────────────────────────────────────────────────────
# GET /users/me — Profil de l'utilisateur connecté
# ─────────────────────────────────────────────────────────────
@router.get(
    "/me",
    response_model=UserResponse,
    summary="Mon profil",
)
async def get_my_profile(payload: CurrentUserPayload, repo: UserRepo):
    """Retourne le profil de l'utilisateur connecté."""
    try:
        uc = GetUserUseCase(repo)
        return await uc.execute(user_id=payload["sub"])
    except DomainException as e:
        _handle(e)


# ─────────────────────────────────────────────────────────────
# PUT /users/me — Modifier son profil
# ─────────────────────────────────────────────────────────────
@router.put(
    "/me",
    response_model=UserResponse,
    summary="Modifier mon profil",
)
async def update_my_profile(
    body: UpdateUserRequest,
    payload: CurrentUserPayload,
    repo: UserRepo,
):
    """Mise à jour partielle du profil de l'utilisateur connecté."""
    try:
        uc = UpdateUserUseCase(repo)
        return await uc.execute(
            user_id=payload["sub"],
            phone=body.phone,
            email=body.email,
            username=body.username,
            password=body.password,
            pin=body.pin,
            role=body.role.value if body.role else None,
            vehicle_type=body.vehicle_type,
        )
    except DomainException as e:
        _handle(e)


# ─────────────────────────────────────────────────────────────
# GET /users — Lister les utilisateurs (Admin)
# ─────────────────────────────────────────────────────────────
@router.get(
    "",
    response_model=UserListResponse,
    summary="Lister les utilisateurs (admin)",
)
async def list_users(
    _admin: AdminPayload,
    repo: UserRepo,
    role: str | None = Query(None, description="Filtrer par rôle"),
    page: int = Query(1, ge=1, description="Numéro de page"),
    page_size: int = Query(50, ge=1, le=100, description="Taille de page"),
):
    """Liste paginée de tous les utilisateurs. Réservé aux admins."""
    try:
        uc = ListUsersUseCase(repo)
        return await uc.execute(role=role, page=page, page_size=page_size)
    except DomainException as e:
        _handle(e)


# ─────────────────────────────────────────────────────────────
# GET /users/{user_id} — Voir un utilisateur (Admin)
# ─────────────────────────────────────────────────────────────
@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Voir un utilisateur (admin)",
)
async def get_user(
    user_id: str,
    _admin: AdminPayload,
    repo: UserRepo,
):
    """Récupère un utilisateur par son ID. Réservé aux admins."""
    try:
        uc = GetUserUseCase(repo)
        return await uc.execute(user_id=user_id)
    except DomainException as e:
        _handle(e)


# ─────────────────────────────────────────────────────────────
# PUT /users/{user_id} — Modifier un utilisateur (Admin)
# ─────────────────────────────────────────────────────────────
@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Modifier un utilisateur (admin)",
)
async def update_user(
    user_id: str,
    body: AdminUpdateUserRequest,
    _admin: AdminPayload,
    repo: UserRepo,
):
    """Mise à jour admin d'un utilisateur (peut changer rôle et statut)."""
    try:
        uc = UpdateUserUseCase(repo)
        return await uc.execute(
            user_id=user_id,
            phone=body.phone,
            email=body.email,
            username=body.username,
            password=body.password,
            pin=body.pin,
            role=body.role.value if body.role else None,
            vehicle_type=body.vehicle_type,
            is_active=body.is_active,
        )
    except DomainException as e:
        _handle(e)


# ─────────────────────────────────────────────────────────────
# DELETE /users/{user_id} — Supprimer un utilisateur (Admin)
# ─────────────────────────────────────────────────────────────
@router.delete(
    "/{user_id}",
    response_model=MessageResponse,
    summary="Supprimer un utilisateur (admin)",
)
async def delete_user(
    user_id: str,
    _admin: AdminPayload,
    repo: UserRepo,
):
    """Supprime un utilisateur. Réservé aux admins."""
    try:
        uc = DeleteUserUseCase(repo)
        return await uc.execute(user_id=user_id)
    except DomainException as e:
        _handle(e)
