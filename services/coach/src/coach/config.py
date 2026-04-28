"""Configuration du service coach.

Lit les variables depuis `.env` à la racine du projet.
"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Paramètres chargés depuis l'environnement."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Groq (LLM)
    groq_api_key: str = Field(default="", description="Clé API Groq")
    groq_model: str = Field(
        default="llama-3.3-70b-versatile",
        description="Modèle Groq à utiliser",
    )
    groq_model_small: str = Field(
        default="llama-3.1-8b-instant",
        description="Modèle plus léger pour les tâches simples (intent)",
    )

    # Base de données (lecture seule pour le coach)
    database_url: str = Field(default="", description="URL PostgreSQL")

    # Comportement
    log_level: str = Field(default="WARNING")
    max_tokens: int = Field(default=800, description="Longueur max de la réponse LLM")
    temperature: float = Field(
        default=0.3,
        description="Faible = plus factuel et déterministe (anti-hallucination)",
    )


def get_settings() -> Settings:
    return Settings()
