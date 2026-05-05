"""Entraînement du modèle XGBoost de prédiction PM2.5.

Le modèle est global (un seul fichier .joblib) avec station_id comme
feature catégorielle. Cela permet d'utiliser tout le volume de données
disponible (toutes stations confondues) tout en laissant le modèle
apprendre des spécificités locales via l'encodage de la station.

Métriques calculées sur un split chronologique (les 20% les plus récents
forment le test set).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import structlog
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sqlalchemy import Engine
from xgboost import XGBRegressor

from ml_pollution.data_access import fetch_training_data
from ml_pollution.features import (
    CATEGORICAL_FEATURES,
    FEATURE_COLUMNS,
    TARGET_COLUMN,
    build_features,
)

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class TrainingMetrics:
    """Métriques d'évaluation du modèle sur le set de test."""

    mae: float
    rmse: float
    n_train: int
    n_test: int
    n_stations: int


@dataclass
class TrainingResult:
    """Résultat complet d'un entraînement."""

    model: XGBRegressor
    metrics: TrainingMetrics
    metadata: dict[str, Any]


def chronological_split(
    df: pd.DataFrame, test_ratio: float = 0.2
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split chronologique : les 20% les plus récents = test set.

    On NE fait PAS de split aléatoire : on veut éviter la fuite temporelle
    (le modèle prédirait le passé à partir du futur si on faisait un random
    split sur des séries temporelles).
    """
    if df.empty:
        return df, df
    n_test = max(1, int(len(df) * test_ratio))
    n_train = len(df) - n_test
    return df.iloc[:n_train].copy(), df.iloc[n_train:].copy()


def train_model(
    engine: Engine,
    days: int = 30,
    test_ratio: float = 0.2,
    n_estimators: int = 200,
    max_depth: int = 5,
    learning_rate: float = 0.1,
) -> TrainingResult:
    """Charge la data, construit les features, entraîne, évalue.

    Args:
        engine: SQLAlchemy engine pour Supabase
        days: fenêtre temporelle d'entraînement
        test_ratio: proportion gardée pour le test (chronologique)
        n_estimators, max_depth, learning_rate: hyperparamètres XGBoost

    Returns:
        TrainingResult avec le modèle entraîné et les métriques
    """
    logger.info("training_started", days=days)

    raw = fetch_training_data(engine, days=days)
    if raw.empty:
        raise ValueError(
            f"Pas de données d'air sur les {days} derniers jours. "
            "Vérifie que l'ingestion AQICN tourne bien."
        )

    features_df = build_features(raw, for_training=True)
    if len(features_df) < 30:
        raise ValueError(
            f"Pas assez d'échantillons exploitables ({len(features_df)} < 30). "
            "Le pipeline d'ingestion a besoin de plus de temps pour "
            "accumuler des paires (mesure, mesure +1h)."
        )

    logger.info(
        "features_built",
        n_samples=len(features_df),
        n_stations=features_df["station_id"].nunique(),
    )

    df_train, df_test = chronological_split(features_df, test_ratio)
    x_train = df_train[FEATURE_COLUMNS]
    y_train = df_train[TARGET_COLUMN]
    x_test = df_test[FEATURE_COLUMNS]
    y_test = df_test[TARGET_COLUMN]

    # XGBoost avec support natif des features catégorielles
    model = XGBRegressor(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        enable_categorical=True,
        tree_method="hist",
        random_state=42,
    )
    model.fit(x_train, y_train)

    # Évaluation
    y_pred = model.predict(x_test)
    mae = float(mean_absolute_error(y_test, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))

    metrics = TrainingMetrics(
        mae=mae,
        rmse=rmse,
        n_train=len(df_train),
        n_test=len(df_test),
        n_stations=int(features_df["station_id"].nunique()),
    )

    logger.info(
        "training_done",
        mae=round(mae, 2),
        rmse=round(rmse, 2),
        n_train=metrics.n_train,
        n_test=metrics.n_test,
    )

    metadata: dict[str, Any] = {
        "feature_columns": FEATURE_COLUMNS,
        "categorical_features": CATEGORICAL_FEATURES,
        "target_column": TARGET_COLUMN,
        "metrics": {
            "mae": metrics.mae,
            "rmse": metrics.rmse,
            "n_train": metrics.n_train,
            "n_test": metrics.n_test,
            "n_stations": metrics.n_stations,
        },
        "hyperparameters": {
            "n_estimators": n_estimators,
            "max_depth": max_depth,
            "learning_rate": learning_rate,
        },
        "data_window_days": days,
    }

    return TrainingResult(model=model, metrics=metrics, metadata=metadata)
