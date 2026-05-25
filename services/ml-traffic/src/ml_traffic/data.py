"""Chargement et préparation des données depuis Supabase.

Cette couche est volontairement séparée de `features.py` :
    * `data.py`     : requête SQL, nettoyage des outliers, filtre lignes éligibles
    * `features.py` : construction des features ML et de la target

Implémentation à venir dans la PR `feat/ml-traffic-baseline`.
"""
from __future__ import annotations

import pandas as pd
from sqlalchemy import Engine


def load_stop_visits(engine: Engine) -> pd.DataFrame:
    """Charge tous les passages avec retard non-null depuis stop_visits.

    À implémenter dans la PR baseline.
    """
    raise NotImplementedError("À implémenter dans feat/ml-traffic-baseline")


def filter_eligible_lines(
    df: pd.DataFrame,
    min_passages: int,
) -> pd.DataFrame:
    """Filtre les lignes avec moins de `min_passages` observations.

    À implémenter dans la PR baseline.
    """
    raise NotImplementedError("À implémenter dans feat/ml-traffic-baseline")


def clean_outliers(
    df: pd.DataFrame,
    min_s: int,
    max_s: int,
) -> pd.DataFrame:
    """Supprime les retards hors de [min_s, max_s].

    À implémenter dans la PR baseline.
    """
    raise NotImplementedError("À implémenter dans feat/ml-traffic-baseline")
