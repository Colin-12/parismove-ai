"""Entraînement et évaluation du modèle baseline de perturbation.

Pipeline complet :
    1. Chargement Supabase
    2. Nettoyage + filtre lignes éligibles
    3. Agrégation horaire + construction target/features
    4. Split chronologique 70/15/15
    5. Entraînement régression logistique (avec encodage catégoriel)
    6. Évaluation accuracy / precision / recall / f1 / AUC
    7. Sauvegarde modèle joblib
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

FEATURE_COLS_CAT = ["mode", "line_id"]
FEATURE_COLS_NUM = ["hour", "dow"]
ALL_FEATURE_COLS = FEATURE_COLS_CAT + FEATURE_COLS_NUM


@dataclass
class EvaluationMetrics:
    """Container pour les métriques d'évaluation."""

    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float
    confusion: list[list[int]]
    n_samples: int
    pct_positive: float

    def to_dict(self) -> dict[str, Any]:
        """Sérialise en dict pour export Markdown / JSON."""
        return {
            "accuracy": round(self.accuracy, 4),
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "roc_auc": round(self.roc_auc, 4),
            "confusion": self.confusion,
            "n_samples": self.n_samples,
            "pct_positive": round(self.pct_positive, 4),
        }


def split_chronological(
    df: pd.DataFrame,
    train_ratio: float,
    val_ratio: float,
    time_col: str = "hour_slot",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split chronologique en train/val/test.

    Les données sont triées par `time_col` puis découpées proportionnellement.
    Pas de mélange aléatoire : on respecte la temporalité pour éviter la
    fuite de données.

    Parameters
    ----------
    df : DataFrame trié ou non.
    train_ratio : proportion train (ex. 0.70).
    val_ratio : proportion validation (ex. 0.15).
    time_col : colonne temporelle de référence.

    Returns
    -------
    (train, val, test) DataFrames.
    """
    if train_ratio + val_ratio >= 1.0:
        raise ValueError("train_ratio + val_ratio doit être < 1.0")

    df_sorted = df.sort_values(time_col).reset_index(drop=True)
    n = len(df_sorted)
    n_train = int(n * train_ratio)
    n_val = int(n * val_ratio)

    train = df_sorted.iloc[:n_train].copy()
    val = df_sorted.iloc[n_train : n_train + n_val].copy()
    test = df_sorted.iloc[n_train + n_val :].copy()
    return train, val, test


def build_pipeline(random_state: int = 42) -> Pipeline:
    """Construit le pipeline scikit-learn baseline.

    OneHotEncoder pour les catégoriels (mode, line_id) + StandardScaler
    pour les numériques (hour, dow) + LogisticRegression L2.
    """
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                FEATURE_COLS_CAT,
            ),
            ("num", StandardScaler(), FEATURE_COLS_NUM),
        ]
    )
    pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            (
                "classifier",
                LogisticRegression(
                    max_iter=1000,
                    class_weight="balanced",
                    random_state=random_state,
                ),
            ),
        ]
    )
    return pipeline


def train_baseline(
    x_train: pd.DataFrame,
    y_train: pd.Series,
    random_state: int = 42,
) -> Pipeline:
    """Entraîne le pipeline baseline sur x_train / y_train.

    Le pipeline encode automatiquement les catégoriels et standardise
    les numériques avant la régression logistique.
    """
    pipeline = build_pipeline(random_state=random_state)
    pipeline.fit(x_train[ALL_FEATURE_COLS], y_train)
    return pipeline


def evaluate(
    model: Pipeline,
    x_data: pd.DataFrame,
    y: pd.Series,
) -> EvaluationMetrics:
    """Calcule les métriques de classification sur (x_data, y).

    Returns
    -------
    EvaluationMetrics avec accuracy, precision, recall, f1, AUC,
    matrice de confusion et taille d'échantillon.
    """
    y_pred = model.predict(x_data[ALL_FEATURE_COLS])
    y_proba = model.predict_proba(x_data[ALL_FEATURE_COLS])[:, 1]

    return EvaluationMetrics(
        accuracy=accuracy_score(y, y_pred),
        precision=precision_score(y, y_pred, zero_division=0),
        recall=recall_score(y, y_pred, zero_division=0),
        f1=f1_score(y, y_pred, zero_division=0),
        roc_auc=roc_auc_score(y, y_proba) if y.nunique() > 1 else float("nan"),
        confusion=confusion_matrix(y, y_pred).tolist(),
        n_samples=len(y),
        pct_positive=float(y.mean()),
    )


def save_model(model: Pipeline, path: Path) -> None:
    """Sauvegarde le pipeline entraîné via joblib."""
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)
