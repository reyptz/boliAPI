"""
Configuration de l'application — chargement des variables d'environnement.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Paramètres globaux chargés depuis le fichier .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Base de données ──────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./boli_dev.db"

    # ── JWT ──────────────────────────────────────────────────
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Application ─────────────────────────────────────────
    APP_NAME: str = "BoliAPI"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True


settings = Settings()

