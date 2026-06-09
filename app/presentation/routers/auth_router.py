"""
Router d'authentification — tous les endpoints /auth/*.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.application.dto.auth_dto import (
    Disable2FARequest,
    Enable2FAResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    MessageResponse,
    RefreshTokenRequest,
    ResetPasswordRequest,
    SignInRequest,
    SignInResponse,
    SignUpRequest,
    TwoFAPendingResponse,
    Verify2FARequest,
)
from app.application.use_cases.enable_2fa import Enable2FAUseCase
from app.application.use_cases.forgot_password import ForgotPasswordUseCase
from app.application.use_cases.logout import LogoutUseCase
from app.application.use_cases.reset_password import ResetPasswordUseCase
from app.application.use_cases.signin import SignInUseCase
from app.application.use_cases.signup import SignUpUseCase
from app.application.use_cases.verify_2fa import Verify2FAUseCase
from app.domain.exceptions import DomainException
from app.infrastructure.security.jwt_handler import (
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.infrastructure.security.totp_handler import verify_code
from app.presentation.dependencies import (
    CurrentUserPayload,
    RawToken,
    UserRepo,
    get_current_user_payload,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ── Helper pour gérer les exceptions domaine ─────────────────
def _handle_domain_error(exc: DomainException):
    raise HTTPException(status_code=exc.status_code, detail=exc.detail)


# ─────────────────────────────────────────────────────────────
# POST /auth/signup
# ─────────────────────────────────────────────────────────────
@router.post(
    "/signup",
    response_model=SignInResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Inscription d'un nouvel utilisateur",
)
async def signup(body: SignUpRequest, repo: UserRepo):
    """
    Crée un nouveau compte utilisateur.

    - Au moins un identifiant requis : **phone**, **email** ou **username**
    - Au moins un secret requis : **password** ou **pin**
    """
    try:
        uc = SignUpUseCase(repo)
        result = await uc.execute(
            phone=body.phone,
            email=body.email,
            username=body.username,
            password=body.password,
            pin=body.pin,
            role=body.role.value,
        )
        return result
    except DomainException as e:
        _handle_domain_error(e)


# ─────────────────────────────────────────────────────────────
# POST /auth/signin
# ─────────────────────────────────────────────────────────────
@router.post(
    "/signin",
    response_model=SignInResponse | TwoFAPendingResponse,
    summary="Connexion utilisateur",
)
async def signin(body: SignInRequest, repo: UserRepo):
    """
    Connecte un utilisateur avec identifiant flexible + password ou PIN.

    Si le 2FA est activé, retourne un `temp_token` et `requires_2fa: true`.
    """
    try:
        uc = SignInUseCase(repo)
        result = await uc.execute(
            identifier=body.identifier,
            password=body.password,
            pin=body.pin,
        )
        return result
    except DomainException as e:
        _handle_domain_error(e)


# ─────────────────────────────────────────────────────────────
# POST /auth/logout
# ─────────────────────────────────────────────────────────────
@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Déconnexion",
)
async def logout(token: RawToken):
    """Invalide le token JWT courant."""
    uc = LogoutUseCase()
    result = await uc.execute(token=token)
    return result


# ─────────────────────────────────────────────────────────────
# POST /auth/forgot-password
# ─────────────────────────────────────────────────────────────
@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    summary="Demander un reset de mot de passe",
)
async def forgot_password(body: ForgotPasswordRequest, repo: UserRepo):
    """
    Envoie un token de réinitialisation.
    En mode debug, le token est retourné dans la réponse.
    """
    try:
        uc = ForgotPasswordUseCase(repo)
        result = await uc.execute(identifier=body.identifier)
        return result
    except DomainException as e:
        _handle_domain_error(e)


# ─────────────────────────────────────────────────────────────
# POST /auth/reset-password
# ─────────────────────────────────────────────────────────────
@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Réinitialiser le mot de passe",
)
async def reset_password(body: ResetPasswordRequest, repo: UserRepo):
    """Réinitialise le mot de passe avec le token reçu."""
    try:
        uc = ResetPasswordUseCase(repo)
        result = await uc.execute(token=body.token, new_password=body.new_password)
        return result
    except DomainException as e:
        _handle_domain_error(e)


# ─────────────────────────────────────────────────────────────
# POST /auth/2fa/enable
# ─────────────────────────────────────────────────────────────
@router.post(
    "/2fa/enable",
    response_model=Enable2FAResponse,
    summary="Activer le 2FA",
)
async def enable_2fa(payload: CurrentUserPayload, repo: UserRepo):
    """
    Génère un secret TOTP et retourne le provisioning URI pour QR code.
    L'utilisateur doit ensuite vérifier avec un code pour confirmer l'activation.
    """
    try:
        uc = Enable2FAUseCase(repo)
        result = await uc.execute(user_id=payload["sub"])
        return result
    except DomainException as e:
        _handle_domain_error(e)


# ─────────────────────────────────────────────────────────────
# POST /auth/2fa/verify
# ─────────────────────────────────────────────────────────────
@router.post(
    "/2fa/verify",
    response_model=SignInResponse,
    summary="Vérifier le code 2FA",
)
async def verify_2fa(
    body: Verify2FARequest,
    payload: dict = Depends(get_current_user_payload),
    repo: UserRepo = None,
):
    """
    Vérifie un code TOTP.

    - Après **enable** : confirme l'activation du 2FA.
    - Après **signin** avec 2FA : complète la connexion.
    """
    try:
        uc = Verify2FAUseCase(repo)
        result = await uc.execute(user_id=payload["sub"], code=body.code)
        return result
    except DomainException as e:
        _handle_domain_error(e)


# ─────────────────────────────────────────────────────────────
# POST /auth/2fa/disable
# ─────────────────────────────────────────────────────────────
@router.post(
    "/2fa/disable",
    response_model=MessageResponse,
    summary="Désactiver le 2FA",
)
async def disable_2fa(
    body: Disable2FARequest,
    payload: CurrentUserPayload,
    repo: UserRepo,
):
    """Désactive le 2FA après vérification du code actuel."""
    import uuid

    from app.domain.exceptions import Invalid2FACodeError, TwoFANotEnabledError, UserNotFoundError

    user = await repo.get_by_id(uuid.UUID(payload["sub"]))
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    if not user.is_2fa_enabled:
        raise HTTPException(status_code=400, detail="Le 2FA n'est pas activé.")
    if not user.totp_secret or not verify_code(user.totp_secret, body.code):
        raise HTTPException(status_code=401, detail="Code 2FA invalide.")

    user.is_2fa_enabled = False
    user.totp_secret = None
    await repo.update(user)

    return {"message": "Authentification 2FA désactivée."}


# ─────────────────────────────────────────────────────────────
# POST /auth/refresh
# ─────────────────────────────────────────────────────────────
@router.post(
    "/refresh",
    response_model=SignInResponse,
    summary="Rafraîchir le token",
)
async def refresh_token(body: RefreshTokenRequest, repo: UserRepo):
    """Échange un refresh token contre un nouveau couple access + refresh."""
    payload = decode_token(body.refresh_token)

    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token invalide ou expiré.",
        )

    user_id = payload["sub"]

    # Vérifier que l'utilisateur existe encore
    import uuid

    user = await repo.get_by_id(uuid.UUID(user_id))
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Compte inexistant ou désactivé.",
        )

    # Générer de nouveaux tokens
    new_access = create_access_token(user_id, user.role.value)
    new_refresh = create_refresh_token(user_id)

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "user_id": user_id,
        "role": user.role.value,
        "requires_2fa": False,
    }
