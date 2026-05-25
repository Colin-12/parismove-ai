"""Entraînement et évaluation du modèle de perturbation.

Pipeline :
    1. Chargement data.load_stop_visits()
    2. clean_outliers + filter_eligible_lines
    3. aggregate_hourly_by_line
    4. build_target + build_features
    5. Split chronologique 70/15/15
    6. Entraînement (logistic baseline ou XGBoost)
    7. Évaluation : accuracy, F1, AUC, matrice de confusion
    8. Sauvegarde du modèle dans settings.models_dir
"""
from __future__ import annotations

import pandas as pd
from sklearn.base import ClassifierMixin


def split_chronological(
    df: pd.DataFrame,
    train_ratio: float,
    val_ratio: float,
    time_col: str = "hour_slot",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split chronologique en 3 ensembles.

    À implémenter dans la PR baseline.
    """
    raise NotImplementedError("À implémenter dans feat/ml-traffic-baseline")


def train_baseline(
    X_train: pd.DataFrame,
    y_train: pd.Series,
) -> ClassifierMixin:
    """Entraîne le baseline (régression logistique).

    À implémenter dans la PR baseline.
    """
    raise NotImplementedError("À implémenter dans feat/ml-traffic-baseline")


def evaluate(
    model: ClassifierMixin,
    X: pd.DataFrame,
    y: pd.Series,
) -> dict[str, float]:
    """Calcule les métriques de classification.

    Retourne : accuracy, precision, recall, f1, roc_auc.

    À implémenter dans la PR baseline.
    """
    raise NotImplementedError("À implémenter dans feat/ml-traffic-baseline")
