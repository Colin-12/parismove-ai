"""Configuration du service d'ingestion.

Lit les variables depuis `.env` à la racine du projet.
"""
from __future__ import annotations

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Paramètres chargés depuis l'environnement."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # PRIM IDFM
    prim_api_key: str = Field(default="", description="Clé API PRIM IDFM")
    prim_base_url: HttpUrl = Field(
        default=HttpUrl("https://prim.iledefrance-mobilites.fr/marketplace"),
        description="URL de base de l'API PRIM",
    )

    # Base de données
    database_url: str = Field(
        default="", description="URL PostgreSQL (Supabase)"
    )

    # Paramètres généraux
    log_level: str = Field(default="INFO")
    environment: str = Field(default="development")


def get_settings() -> Settings:
    """Retourne une instance Settings. Centraliser permet les tests."""
    return Settings()
