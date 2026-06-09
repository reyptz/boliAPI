"""
DTOs pour l'authentification — validation des entrées/sorties API.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.domain.enums.user_role import UserRole


# ── Sign Up ──────────────────────────────────────────────────


class SignUpRequest(BaseModel):
    """Requête d'inscription."""

    # Au moins un identifiant requis
    phone: str | None = Field(None, min_length=8, max_length=20, examples=["+22370000000"])
    email: str | None = Field(None, examples=["user@boli.ml"])
    username: str | None = Field(None, min_length=3, max_length=50, examples=["moussa"])

    # Au moins un secret requis
    password: str | None = Field(None, min_length=6, max_length=128)
    pin: str | None = Field(None, min_length=4, max_length=6, pattern=r"^\d{4,6}$")

    role: UserRole = UserRole.CLIENT

    @field_validator("phone", "email", "username", mode="after")
    @classmethod
    def at_least_one_identifier(cls, v, info):
        """Validation faite au niveau du use case (besoin de tous les champs)."""
        return v


# ── Sign In ──────────────────────────────────────────────────


class SignInRequest(BaseModel):
    """Requête de connexion — identifiant flexible + password ou PIN."""

    identifier: str = Field(
        ...,
        min_length=3,
        description="Numéro de téléphone, email ou username",
        examples=["+22370000000", "user@boli.ml", "moussa"],
    )
    password: str | None = Field(None, min_length=4, max_length=128)
    pin: str | None = Field(None, min_length=4, max_length=6, pattern=r"^\d{4,6}$")

    @field_validator("pin", mode="after")
    @classmethod
    def need_password_or_pin(cls, v, info):
        """Au moins un secret doit être fourni."""
        if not v and not info.data.get("password"):
            raise ValueError("Un mot de passe ou un code PIN est requis.")
        return v


class SignInResponse(BaseModel):
    """Réponse de connexion réussie."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    role: str
    requires_2fa: bool = False


class TwoFAPendingResponse(BaseModel):
    """Réponse quand le 2FA est requis avant connexion complète."""

    temp_token: str
    token_type: str = "bearer"
    requires_2fa: bool = True
    message: str = "Veuillez entrer votre code 2FA."


# ── Forgot / Reset Password ─────────────────────────────────


class ForgotPasswordRequest(BaseModel):
    """Requête de demande de réinitialisation."""

    identifier: str = Field(
        ...,
        min_length=3,
        description="Numéro de téléphone, email ou username",
    )


class ForgotPasswordResponse(BaseModel):
    """Réponse de demande de reset (token affiché en dev, envoyé par SMS/email en prod)."""

    message: str = "Si un compte existe avec cet identifiant, un code de réinitialisation a été envoyé."
    # En mode dev uniquement :
    debug_token: str | None = None


class ResetPasswordRequest(BaseModel):
    """Requête de réinitialisation avec le token reçu."""

    token: str = Field(..., min_length=10)
    new_password: str = Field(..., min_length=6, max_length=128)


# ── 2FA ──────────────────────────────────────────────────────


class Enable2FAResponse(BaseModel):
    """Réponse lors de l'activation du 2FA — contient le QR code URI."""

    secret: str
    provisioning_uri: str
    message: str = "Scannez le QR code avec Google Authenticator ou Authy, puis vérifiez avec un code."


class Verify2FARequest(BaseModel):
    """Requête de vérification du code TOTP."""

    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class Disable2FARequest(BaseModel):
    """Requête de désactivation du 2FA (nécessite le code actuel)."""

    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


# ── Refresh Token ────────────────────────────────────────────


class RefreshTokenRequest(BaseModel):
    """Requête de rafraîchissement du token."""

    refresh_token: str


# ── Réponse générique ────────────────────────────────────────


class MessageResponse(BaseModel):
    """Réponse simple avec message."""

    message: str
