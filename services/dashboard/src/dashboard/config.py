"""Configuration du dashboard.

Charge depuis `.env` à la racine du projet (en local) ou depuis les
secrets Streamlit (en production sur Streamlit Cloud).
"""
from __future__ import annotations

import os
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Paramètres du dashboard."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Base de données (lecture seule pour le dashboard)
    database_url: str = Field(default="", description="URL PostgreSQL")

    # Coach (utilisé par la page chat — PR 3)
    groq_api_key: str = Field(default="")
    groq_model: str = Field(default="llama-3.3-70b-versatile")
    groq_model_small: str = Field(default="llama-3.1-8b-instant")

    # Affichage
    log_level: str = Field(default="WARNING")


def get_settings() -> Settings:
    """Récupère les settings, en priorisant les secrets Streamlit si présents.

    Sur Streamlit Cloud, `st.secrets` contient les variables. Localement,
    on lit `.env` via Pydantic.
    """
    # Détection de l'environnement Streamlit
    streamlit_secrets = _try_load_streamlit_secrets()
    if streamlit_secrets:
        # Priorité aux secrets Streamlit (production)
        for key, value in streamlit_secrets.items():
            os.environ.setdefault(key.upper(), str(value))

    return Settings()


def _try_load_streamlit_secrets() -> dict[str, Any] | None:
    """Charge les secrets Streamlit si on est dans cet environnement."""
    try:
        import streamlit as st
        if hasattr(st, "secrets") and st.secrets:
            return dict(st.secrets)
    except (ImportError, AttributeError, Exception):
        pass
    return None
