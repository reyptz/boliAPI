"""
Exceptions métier du domaine Auth.
Chaque exception porte un message clair et un code HTTP suggéré.
"""


class DomainException(Exception):
    """Classe de base pour toutes les exceptions domaine."""

    status_code: int = 400
    detail: str = "Erreur métier"

    def __init__(self, detail: str | None = None):
        self.detail = detail or self.__class__.detail
        super().__init__(self.detail)


# ── Auth ─────────────────────────────────────────────────────


class UserAlreadyExistsError(DomainException):
    status_code = 409
    detail = "Un utilisateur avec cet identifiant existe déjà."


class UserNotFoundError(DomainException):
    status_code = 404
    detail = "Utilisateur introuvable."


class InvalidCredentialsError(DomainException):
    status_code = 401
    detail = "Identifiants invalides."


class AccountDisabledError(DomainException):
    status_code = 403
    detail = "Ce compte est désactivé."


class Invalid2FACodeError(DomainException):
    status_code = 401
    detail = "Code 2FA invalide."


class TwoFANotEnabledError(DomainException):
    status_code = 400
    detail = "L'authentification 2FA n'est pas activée sur ce compte."


class TwoFAAlreadyEnabledError(DomainException):
    status_code = 400
    detail = "L'authentification 2FA est déjà activée."


class InvalidResetTokenError(DomainException):
    status_code = 400
    detail = "Token de réinitialisation invalide ou expiré."


class MissingIdentifierError(DomainException):
    status_code = 400
    detail = "Au moins un identifiant (téléphone, email ou username) est requis."


class MissingCredentialError(DomainException):
    status_code = 400
    detail = "Un mot de passe ou un code PIN est requis."


# ── Wallet / Paiements ───────────────────────────────────────


class InsufficientBalanceError(DomainException):
    status_code = 402  # Payment Required
    detail = "Solde insuffisant pour effectuer cette opération."


class InvalidAmountError(DomainException):
    status_code = 400
    detail = "Montant invalide."


class WebhookSignatureError(DomainException):
    status_code = 401
    detail = "Signature du webhook invalide."
