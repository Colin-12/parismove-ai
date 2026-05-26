"""Feature engineering pour le modèle de prédiction PM2.5.

Améliorations v2 :
    * Exclusion de @5722 (station trafic routier, trop volatile)
    * Lags h2 et h3 ajoutés (signal court-terme plus fort)
    * Prédiction sur log(pm25) pour stabiliser la distribution asymétrique
    * Target = log(pm25_h1) au lieu de pm25_h1

Features construites :
    Temporelles
        * heure (0-23)
        * jour_semaine (0=lundi, 6=dimanche)
        * mois (1-12)

    Lag (PM2.5 historiques de la station)
        * pm25_h1   — concentration il y a 1h
        * pm25_h2   — concentration il y a 2h
        * pm25_h3   — concentration il y a 3h
        * pm25_h24  — concentration il y a 24h

    Météo (point le plus proche, au moment de la mesure)
        * temperature_c
        * humidity_pct
        * wind_speed_ms
        * precipitation_mm

    Géographiques / catégorielles
        * station_id  — encodé en feature catégorielle XGBoost (enable_categorical)

    Cible
        * target_log_pm25_h1  — log(PM2.5) de la prochaine heure (shift -1)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Stations exclues de l'entraînement (trop volatiles / non représentatives)
EXCLUDED_STATIONS = {"@5722"}  # station trafic routier, variation moyenne 9 µg/m³/h

# Liste des colonnes utilisées comme features pour le modèle.
FEATURE_COLUMNS = [
    "heure",
    "jour_semaine",
    "mois",
    "pm25_h1",
    "pm25_h2",
    "pm25_h3",
    "pm25_h24",
    "temperature_c",
    "humidity_pct",
    "wind_speed_ms",
    "precipitation_mm",
    "station_id",
]

CATEGORICAL_FEATURES = ["station_id"]
TARGET_COLUMN = "target_log_pm25_h1"


def build_features(
    df: pd.DataFrame, *, for_training: bool = True
) -> pd.DataFrame:
    """Construit le DataFrame de features depuis les mesures brutes."""
    if df.empty:
        cols = FEATURE_COLUMNS + ([TARGET_COLUMN] if for_training else [])
        return pd.DataFrame(columns=cols)

    df = df.copy()
    df["measured_at"] = pd.to_datetime(df["measured_at"], utc=True)
    df = df.sort_values(["station_id", "measured_at"])

    # Exclure les stations trop volatiles pour l'entraînement
    if for_training:
        df = df[~df["station_id"].isin(EXCLUDED_STATIONS)]

    # Features temporelles
    df["heure"] = df["measured_at"].dt.hour
    df["jour_semaine"] = df["measured_at"].dt.dayofweek
    df["mois"] = df["measured_at"].dt.month

    # Features lag — par station
    df["pm25_h1"] = df.groupby("station_id")["pm25"].shift(1)
    df["pm25_h2"] = df.groupby("station_id")["pm25"].shift(2)
    df["pm25_h3"] = df.groupby("station_id")["pm25"].shift(3)
    df["pm25_h24"] = df.groupby("station_id")["pm25"].shift(24)

    # station_id en catégoriel
    df["station_id"] = df["station_id"].astype("category")

    if for_training:
        # Cible : log(PM2.5) de l'heure suivante
        next_pm25 = df.groupby("station_id", observed=True)["pm25"].shift(-1)
        df[TARGET_COLUMN] = np.log1p(next_pm25)

    if for_training:
        result_cols = [*FEATURE_COLUMNS, TARGET_COLUMN]
        result = df[result_cols].dropna().reset_index(drop=True)
    else:
        result = df[FEATURE_COLUMNS].reset_index(drop=True)

    return result


def build_inference_row(
    station_id: str,
    target_dt: pd.Timestamp,
    pm25_h1: float | None,
    pm25_h24: float | None,
    temperature_c: float | None,
    humidity_pct: float | None,
    wind_speed_ms: float | None,
    precipitation_mm: float | None,
    pm25_h2: float | None = None,
    pm25_h3: float | None = None,
) -> pd.DataFrame:
    """Construit une ligne de features pour une prédiction ponctuelle."""
    target_dt = pd.Timestamp(target_dt)
    if target_dt.tz is None:
        target_dt = target_dt.tz_localize("UTC")

    row = pd.DataFrame([{
        "heure":            target_dt.hour,
        "jour_semaine":     target_dt.dayofweek,
        "mois":             target_dt.month,
        "pm25_h1":          pm25_h1,
        "pm25_h2":          pm25_h2,
        "pm25_h3":          pm25_h3,
        "pm25_h24":         pm25_h24,
        "temperature_c":    temperature_c,
        "humidity_pct":     humidity_pct,
        "wind_speed_ms":    wind_speed_ms,
        "precipitation_mm": precipitation_mm,
        "station_id":       station_id,
    }])
    row["station_id"] = row["station_id"].astype("category")
    return row[FEATURE_COLUMNS]
