"""Entraînement et évaluation des modèles de perturbation.

Deux modèles disponibles :
    * baseline   : régression logistique (PR feat/ml-traffic-baseline)
    * xgboost    : XGBoostClassifier (PR feat/ml-traffic-xgboost)

Le pipeline est identique pour les deux (même préprocessing, même split)
afin de garantir une comparaison équitable.
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
from xgboost import XGBClassifier

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


def _build_preprocessor() -> ColumnTransformer:
    """Préprocesseur commun baseline et XGBoost."""
    return ColumnTransformer(
        transformers=[
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                FEATURE_COLS_CAT,
            ),
            ("num", StandardScaler(), FEATURE_COLS_NUM),
        ]
    )


def build_pipeline(random_state: int = 42) -> Pipeline:
    """Construit le pipeline scikit-learn baseline (régression logistique)."""
    return Pipeline(
        steps=[
            ("preprocessor", _build_preprocessor()),
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


def build_xgb_pipeline(
    n_estimators: int = 200,
    max_depth: int = 6,
    learning_rate: float = 0.1,
    random_state: int = 42,
) -> Pipeline:
    """Construit le pipeline XGBoost.

    Notes
    -----
    `scale_pos_weight` compense le déséquilibre de classes : si 33% de positifs,
    scale_pos_weight = (1 - 0.33) / 0.33 ≈ 2.0. Équivalent au `class_weight='balanced'`
    de la régression logistique.

    `eval_metric='logloss'` supprime le warning XGBoost sur le choix de métrique.
    """
    scale_pos_weight = 2.0  # Calibré sur les 33% de positifs observés en EDA v2

    return Pipeline(
        steps=[
            ("preprocessor", _build_preprocessor()),
            (
                "classifier",
                XGBClassifier(
                    n_estimators=n_estimators,
                    max_depth=max_depth,
                    learning_rate=learning_rate,
                    scale_pos_weight=scale_pos_weight,
                    eval_metric="logloss",
                    random_state=random_state,
                    verbosity=0,
                ),
            ),
        ]
    )


def train_baseline(
    x_train: pd.DataFrame,
    y_train: pd.Series,
    random_state: int = 42,
) -> Pipeline:
    """Entraîne le pipeline baseline (régression logistique)."""
    pipeline = build_pipeline(random_state=random_state)
    pipeline.fit(x_train[ALL_FEATURE_COLS], y_train)
    return pipeline


def train_xgboost(
    x_train: pd.DataFrame,
    y_train: pd.Series,
    x_val: pd.DataFrame,
    y_val: pd.Series,
    n_estimators: int = 200,
    max_depth: int = 6,
    learning_rate: float = 0.1,
    random_state: int = 42,
) -> Pipeline:
    """Entraîne le pipeline XGBoost avec early stopping sur le val set.

    L'early stopping arrête l'entraînement si l'AUC sur le val set ne
    s'améliore pas pendant 20 rounds consécutifs. Cela évite le surapprentissage
    sans avoir à fixer `n_estimators` à la main.

    Parameters
    ----------
    x_train, y_train : données d'entraînement.
    x_val, y_val : données de validation pour l'early stopping.
    """
    pipeline = build_xgb_pipeline(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        random_state=random_state,
    )

    # Préprocesser les données de validation pour l'early stopping
    preprocessor = pipeline.named_steps["preprocessor"]
    preprocessor.fit(x_train[ALL_FEATURE_COLS])
    x_train_t = preprocessor.transform(x_train[ALL_FEATURE_COLS])
    x_val_t = preprocessor.transform(x_val[ALL_FEATURE_COLS])

    clf = pipeline.named_steps["classifier"]
    clf.fit(
        x_train_t,
        y_train,
        eval_set=[(x_val_t, y_val)],
        verbose=False,
    )

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
