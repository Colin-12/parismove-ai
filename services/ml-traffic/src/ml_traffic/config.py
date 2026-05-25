"""Configuration du service ml-traffic.

Centralise les seuils, hyperparamètres et chemins via Pydantic Settings.
Les valeurs peuvent être surchargées par variables d'environnement.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings du service ml-traffic.

    Tous les seuils numériques sont issus de l'EDA v2 et documentés
    dans l'ADR-010.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Connexion base ---
    database_url: str = Field(
        default="",
        description="URL Postgres Supabase (préfixe postgresql+psycopg://)",
    )

    # --- Définition de la target ---
    # Une heure est dite "perturbée" si l'une de ces conditions est vraie :
    #   * au moins 1 passage avec retard > severe_delay_threshold_s
    #   * au moins severe_count_threshold passages avec retard > delay_threshold_s
    delay_threshold_s: int = Field(
        default=60,
        description="Seuil de retard considéré comme tardif (s)",
    )
    severe_delay_threshold_s: int = Field(
        default=120,
        description="Seuil de retard sévère (s)",
    )
    severe_count_threshold: int = Field(
        default=2,
        description="Nb min de passages tardifs pour considérer l'heure perturbée",
    )

    # --- Filtrage des lignes ---
    min_passages_per_line: int = Field(
        default=200,
        description="Nb min de passages pour qu'une ligne soit éligible au modèle",
    )

    # --- Nettoyage ---
    outlier_min_s: int = Field(default=-1800, description="Borne basse retard accepté (s)")
    outlier_max_s: int = Field(default=3600, description="Borne haute retard accepté (s)")

    # --- Split chronologique ---
    train_ratio: float = Field(default=0.70, description="Proportion train")
    val_ratio: float = Field(default=0.15, description="Proportion validation")
    # test_ratio = 1 - train_ratio - val_ratio

    # --- Horizon de prédiction ---
    prediction_horizon_hours: int = Field(
        default=1,
        description="Horizon de prédiction en heures",
    )

    # --- XGBoost hyperparamètres par défaut ---
    xgb_max_depth: int = Field(default=6)
    xgb_n_estimators: int = Field(default=200)
    xgb_learning_rate: float = Field(default=0.1)
    xgb_random_state: int = Field(default=42)

    # --- Chemins ---
    models_dir: Path = Field(
        default=Path("services/ml-traffic/models"),
        description="Dossier de sauvegarde des modèles entraînés",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retourne l'instance unique de Settings (cache process-wide)."""
    return Settings()
