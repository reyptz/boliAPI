"""
Hashing de mots de passe et codes PIN avec bcrypt (direct).
"""

import bcrypt


def hash_password(plain: str) -> str:
    """Hashe un mot de passe en clair avec bcrypt."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Vérifie un mot de passe en clair contre son hash bcrypt."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# Les mêmes fonctions servent pour le PIN — c'est juste une chaîne plus courte.
hash_pin = hash_password
verify_pin = verify_password
