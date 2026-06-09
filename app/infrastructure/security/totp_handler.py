"""
Gestion du 2FA TOTP — compatible Google Authenticator / Authy.
"""

import pyotp


def generate_secret() -> str:
    """Génère un secret TOTP aléatoire (base32)."""
    return pyotp.random_base32()


def get_provisioning_uri(
    secret: str,
    identifier: str,
    issuer: str = "Boli",
) -> str:
    """
    Génère l'URI de provisioning pour scanner avec une app 2FA.

    Args:
        secret: Secret TOTP base32.
        identifier: Identifiant affiché dans l'app (email, phone, etc.).
        issuer: Nom de l'application affiché.
    """
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=identifier, issuer_name=issuer)


def verify_code(secret: str, code: str) -> bool:
    """
    Vérifie un code TOTP.
    Accepte le code courant et le précédent (tolérance de 30s).
    """
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)
