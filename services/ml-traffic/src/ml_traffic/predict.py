"""Inférence du modèle de perturbation pour une ligne et un timestamp donnés.

Utilisé par :
    * le coach IA (futur tool "predict_disruption")
    * la page Dashboard "Prévision retards" (Phase 9)
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import cast

import joblib
import pandas as pd
from sklearn.pipeline import Pipeline

from ml_traffic.train import ALL_FEATURE_COLS


def load_model(path: Path) -> Pipeline:
    """Charge un modèle entraîné depuis disque."""
    if not path.exists():
        raise FileNotFoundError(f"Modèle introuvable : {path}")
    return cast(Pipeline, joblib.load(path))


def predict_disruption_proba(
    model: Pipeline,
    line_id: str,
    mode: str,
    when: datetime,
) -> float:
    """Retourne la probabilité de perturbation pour (ligne, mode, instant).

    Parameters
    ----------
    model : pipeline scikit-learn chargé.
    line_id : identifiant IDFM de la ligne.
    mode : 'bus' ou 'rail'.
    when : instant cible (timezone-aware si possible).

    Returns
    -------
    Probabilité de perturbation à H+1 (entre 0 et 1).
    """
    x_input = pd.DataFrame(
        [
            {
                "line_id": line_id,
                "mode": mode,
                "hour": when.hour,
                "dow": when.weekday(),
            }
        ]
    )
    proba = model.predict_proba(x_input[ALL_FEATURE_COLS])[0, 1]
    return float(proba)
