"""Chargement et préparation des données depuis Supabase.

Cette couche est volontairement séparée de `features.py` :
    * `data.py`     : requête SQL, nettoyage outliers, filtre lignes éligibles
    * `features.py` : construction des features ML et de la target

Les fonctions sont pures et testables sans connexion BDD (sauf
`load_stop_visits` qui prend l'engine en paramètre).
"""
from __future__ import annotations

import pandas as pd
from sqlalchemy import Engine, text


def load_stop_visits(engine: Engine) -> pd.DataFrame:
    """Charge tous les passages avec retard non-null depuis stop_visits.

    Joint au référentiel idfm_lines pour récupérer le nom et le mode.

    Returns
    -------
    pd.DataFrame
        Colonnes : line_id, mode, delay_seconds, recorded_at, line_name.
    """
    sql = text(
        """
        SELECT
            sv.line_id,
            COALESCE(il.transport_mode, sv.transport_mode, 'Inconnu') AS mode,
            sv.delay_seconds,
            sv.recorded_at,
            COALESCE(il.short_name, sv.line_id) AS line_name
        FROM stop_visits sv
        LEFT JOIN idfm_lines il ON sv.line_id = il.line_id
        WHERE sv.delay_seconds IS NOT NULL
        ORDER BY sv.recorded_at
        """
    )
    with engine.connect() as conn:
        df = pd.read_sql(sql, conn)

    df["recorded_at"] = pd.to_datetime(df["recorded_at"], utc=True)
    return df


def clean_outliers(
    df: pd.DataFrame,
    min_s: int,
    max_s: int,
) -> pd.DataFrame:
    """Supprime les retards hors de [min_s, max_s].

    Les outliers extrêmes (> 1h, < -30 min) sont des artefacts de l'API PRIM
    (services annulés laissant un retard cumulé erroné). Voir EDA v2 §4.

    Parameters
    ----------
    df : DataFrame avec colonne `delay_seconds`.
    min_s, max_s : bornes inclusives.

    Returns
    -------
    DataFrame filtré (copie, pas de modification in-place).
    """
    mask = df["delay_seconds"].between(min_s, max_s)
    return df.loc[mask].copy()


def filter_eligible_lines(
    df: pd.DataFrame,
    min_passages: int,
) -> pd.DataFrame:
    """Conserve les lignes avec au moins `min_passages` observations.

    Filtre clé pour la fiabilité du modèle : sur les ~74 lignes présentes
    dans stop_visits, beaucoup n'ont que quelques passages et ne peuvent
    pas servir à l'entraînement. Voir ADR-010.

    Parameters
    ----------
    df : DataFrame avec colonne `line_id`.
    min_passages : seuil minimum (défaut config : 200).

    Returns
    -------
    DataFrame filtré (copie).
    """
    counts = df.groupby("line_id").size()
    eligible = counts[counts >= min_passages].index
    return df.loc[df["line_id"].isin(eligible)].copy()
