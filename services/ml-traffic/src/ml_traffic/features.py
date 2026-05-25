"""Construction des features et de la target pour ml-traffic.

Features (validées par EDA v2) :
    * mode    — bus vs rail (signal le plus fort)
    * line_id — identifiant ligne (catégoriel)
    * hour    — heure de la journée (0-23)
    * dow     — jour de la semaine (0=lundi, 6=dimanche)

Target :
    is_disrupted_h1 — bool, perturbation à H+1

Définition d'une heure perturbée (cf. ADR-010) :
    * au moins 1 passage avec retard > severe_delay_threshold_s, OU
    * au moins severe_count_threshold passages avec retard > delay_threshold_s
"""
from __future__ import annotations

import pandas as pd


def aggregate_hourly_by_line(df: pd.DataFrame) -> pd.DataFrame:
    """Agrège stop_visits au pas horaire par ligne.

    Pour chaque couple (ligne, heure), calcule les statistiques nécessaires
    à la construction de la target.

    Parameters
    ----------
    df : DataFrame avec colonnes line_id, mode, delay_seconds, recorded_at.

    Returns
    -------
    DataFrame avec colonnes line_id, mode, hour_slot, n_passages,
    n_late (>delay_threshold), n_severe (>severe_delay_threshold), etc.
    Triée par (line_id, hour_slot).
    """
    df = df.copy()
    df["hour_slot"] = df["recorded_at"].dt.floor("h")

    agg = (
        df.groupby(["line_id", "mode", "hour_slot"])
        .agg(
            n_passages=("delay_seconds", "size"),
            delay_mean=("delay_seconds", "mean"),
            delay_max=("delay_seconds", "max"),
        )
        .reset_index()
        .sort_values(["line_id", "hour_slot"])
        .reset_index(drop=True)
    )
    return agg



def build_target(
    df_visits: pd.DataFrame,
    df_agg: pd.DataFrame,
    delay_threshold_s: int,
    severe_delay_threshold_s: int,
    severe_count_threshold: int,
    horizon_hours: int,
) -> pd.DataFrame:
    """Construit la target perturbation à horizon H+`horizon_hours`.

    Parameters
    ----------
    df_visits : DataFrame brut (sortie de data.load_stop_visits + nettoyage).
    df_agg : DataFrame agrégé horaire (sortie aggregate_hourly_by_line).
    delay_threshold_s, severe_delay_threshold_s, severe_count_threshold :
        seuils de définition de perturbation (cf. ADR-010).
    horizon_hours : horizon de prédiction (1 par défaut).

    Returns
    -------
    df_agg enrichi d'une colonne `target` (bool) pour l'heure H+horizon.
    """
    df_visits = df_visits.copy()
    df_visits["hour_slot"] = df_visits["recorded_at"].dt.floor("h")

    # Calcul de is_disrupted pour chaque couple (line, hour_slot)
    # Agrégation explicite pour compatibilité mypy strict (pas de .apply multi-return)
    grp = df_visits.groupby(["line_id", "hour_slot"])["delay_seconds"]
    n_severe = grp.apply(lambda s: int((s > severe_delay_threshold_s).sum()))
    n_late = grp.apply(lambda s: int((s > delay_threshold_s).sum()))
    disruption = n_severe.rename("n_severe").to_frame()
    disruption["n_late"] = n_late
    disruption["is_disrupted"] = (disruption["n_severe"] >= 1) | (
        disruption["n_late"] >= severe_count_threshold
    )
    disruption = disruption.reset_index()

    # Décalage horaire pour obtenir la target à H+horizon
    disruption = disruption.sort_values(["line_id", "hour_slot"])
    disruption["target"] = (
        disruption.groupby("line_id")["is_disrupted"].shift(-horizon_hours)
    )

    # Merge dans df_agg sur (line_id, hour_slot)
    merged = df_agg.merge(
        disruption[["line_id", "hour_slot", "target"]],
        on=["line_id", "hour_slot"],
        how="left",
    )

    # Drop des lignes sans target (fin de fenêtre temporelle)
    merged = merged.dropna(subset=["target"]).copy()
    merged["target"] = merged["target"].astype(bool)
    return merged


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute les features temporelles hour et dow.

    Parameters
    ----------
    df : DataFrame avec colonne `hour_slot`.

    Returns
    -------
    df enrichi des colonnes `hour` (0-23) et `dow` (0-6).
    """
    df = df.copy()
    df["hour"] = df["hour_slot"].dt.hour.astype(int)
    df["dow"] = df["hour_slot"].dt.dayofweek.astype(int)
    return df
