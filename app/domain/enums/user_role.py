"""
Rôles utilisateurs — alignés sur le schéma SQL de Boli.md.
"""

from enum import Enum


class UserRole(str, Enum):
    """Rôles disponibles dans la Super-App Boli."""

    CLIENT = "client"
    DRIVER = "driver"
    DELIVERY = "delivery"
    MERCHANT = "merchant"
    ADMIN = "admin"
