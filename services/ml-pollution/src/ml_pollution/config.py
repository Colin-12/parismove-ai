"""Configuration du service ml-pollution.

Charge depuis `.env` à la racine du projet.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Emplacement par défaut où le modèle entraîné est persisté.
# Dans le repo monorepo : services/ml-pollution/models/
DEFAULT_MODEL_DIR = (
    Path(__file__).resolve().parent.parent.parent / "models"
)


class Settings(BaseSettings):
    """Paramètres du service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(default="", description="URL PostgreSQL")
    log_level: str = Field(default="INFO")


def get_settings() -> Settings:
    """Retourne les settings."""
    return Settings()


def get_model_dir() -> Path:
    """Retourne le répertoire où sauvegarder/charger le modèle."""
    DEFAULT_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    return DEFAULT_MODEL_DIR
