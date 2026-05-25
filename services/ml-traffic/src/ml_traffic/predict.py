"""Inférence du modèle de perturbation pour une ligne et un timestamp donnés.

Sera utilisé par :
    * le coach IA (tool data-aware "predict_disruption")
    * la page Dashboard "Prévision retards" (Phase 9)
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sklearn.base import ClassifierMixin


def load_model(path: Path) -> ClassifierMixin:
    """Charge un modèle entraîné depuis disque.

    À implémenter dans la PR baseline.
    """
    raise NotImplementedError("À implémenter dans feat/ml-traffic-baseline")


def predict_disruption_proba(
    model: ClassifierMixin,
    line_id: str,
    mode: str,
    when: datetime,
) -> float:
    """Retourne la probabilité de perturbation pour (ligne, mode, horodatage).

    À implémenter dans la PR baseline.
    """
    raise NotImplementedError("À implémenter dans feat/ml-traffic-baseline")
