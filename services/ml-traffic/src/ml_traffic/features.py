"""Construction des features et de la target pour ml-traffic.

Features finales (validées par EDA v2) :
    * mode           — bus vs rail (le signal le plus fort)
    * line_id        — identifiant ligne (catégoriel)
    * hour           — heure de la journée (0-23)
    * dow            — jour de la semaine (0=lundi, 6=dimanche)
    * lag_h1         — retard moyen de la ligne à H-1 (optionnel, à valider)

Target :
    is_disrupted_h1 — bool, perturbation à H+1
"""
from __future__ import annotations

import pandas as pd


def aggregate_hourly_by_line(df: pd.DataFrame) -> pd.DataFrame:
    """Agrège stop_visits au pas horaire par ligne.

    À implémenter dans la PR baseline.
    """
    raise NotImplementedError("À implémenter dans feat/ml-traffic-baseline")


def build_target(
    df: pd.DataFrame,
    delay_threshold_s: int,
    severe_delay_threshold_s: int,
    severe_count_threshold: int,
    horizon_hours: int,
) -> pd.DataFrame:
    """Construit la target `is_disrupted_h{horizon_hours}`.

    Une heure est dite perturbée si :
        * au moins 1 passage avec retard > severe_delay_threshold_s, OU
        * au moins severe_count_threshold passages avec retard > delay_threshold_s

    À implémenter dans la PR baseline.
    """
    raise NotImplementedError("À implémenter dans feat/ml-traffic-baseline")


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Construit les features finales pour le modèle.

    À implémenter dans la PR baseline.
    """
    raise NotImplementedError("À implémenter dans feat/ml-traffic-baseline")
