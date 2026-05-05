"""Feature engineering pour le modèle de prédiction PM2.5.

Features construites :
    Temporelles
        * heure (0-23)
        * jour_semaine (0=lundi, 6=dimanche)
        * mois (1-12)

    Lag (PM2.5 historiques de la station)
        * pm25_h1   — concentration il y a 1h
        * pm25_h24  — concentration il y a 24h

    Météo (point le plus proche, au moment de la mesure)
        * temperature_c
        * humidity_pct
        * wind_speed_ms
        * precipitation_mm

    Géographiques / catégorielles
        * station_id  — encodé en feature catégorielle XGBoost (enable_categorical)

    Cible
        * target_pm25_h1  — PM2.5 de la prochaine heure (shift -1)
"""
from __future__ import annotations

import pandas as pd

# Liste des colonnes utilisées comme features pour le modèle.
# Doit être stable : le modèle entraîné dépend de cet ordre exact.
FEATURE_COLUMNS = [
    "heure",
    "jour_semaine",
    "mois",
    "pm25_h1",
    "pm25_h24",
    "temperature_c",
    "humidity_pct",
    "wind_speed_ms",
    "precipitation_mm",
    "station_id",
]

CATEGORICAL_FEATURES = ["station_id"]
TARGET_COLUMN = "target_pm25_h1"


def build_features(
    df: pd.DataFrame, *, for_training: bool = True
) -> pd.DataFrame:
    """Construit le DataFrame de features depuis les mesures brutes.

    Args:
        df: DataFrame issu de fetch_training_data
        for_training: si True, on calcule aussi la cible (target_pm25_h1)
            et on droppe les lignes incomplètes. Si False (inférence),
            on garde toutes les lignes et la cible n'est pas calculée.

    Returns:
        DataFrame indexé par (station_id, measured_at) avec les features
        et éventuellement la cible.
    """
    if df.empty:
        cols = FEATURE_COLUMNS + ([TARGET_COLUMN] if for_training else [])
        return pd.DataFrame(columns=cols)

    df = df.copy()
    df["measured_at"] = pd.to_datetime(df["measured_at"], utc=True)
    df = df.sort_values(["station_id", "measured_at"])

    # Features temporelles
    df["heure"] = df["measured_at"].dt.hour
    df["jour_semaine"] = df["measured_at"].dt.dayofweek
    df["mois"] = df["measured_at"].dt.month

    # Features lag — par station (groupby pour éviter la fuite entre stations)
    df["pm25_h1"] = df.groupby("station_id")["pm25"].shift(1)
    df["pm25_h24"] = df.groupby("station_id")["pm25"].shift(24)

    # station_id en catégoriel
    df["station_id"] = df["station_id"].astype("category")

    if for_training:
        # Cible : PM2.5 de l'heure suivante (shift -1)
        df[TARGET_COLUMN] = df.groupby(
            "station_id", observed=True
        )["pm25"].shift(-1)

    # Sélection des colonnes finales
    if for_training:
        result_cols = [*FEATURE_COLUMNS, TARGET_COLUMN]
        result = df[result_cols].dropna().reset_index(drop=True)
    else:
        # Pour l'inférence on garde aussi les NaN (le modèle XGBoost les gère)
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
) -> pd.DataFrame:
    """Construit une ligne de features pour une prédiction ponctuelle.

    Utile depuis le dashboard quand on veut prédire la prochaine heure
    pour une station précise.

    Args:
        station_id: ID de la station Airparif (ex: '@5722')
        target_dt: datetime de la prédiction (heure cible H+1)
        pm25_h1: PM2.5 mesuré il y a 1h (à l'heure H actuelle)
        pm25_h24: PM2.5 mesuré il y a 24h
        temperature_c: température actuelle
        ...
    """
    target_dt = pd.Timestamp(target_dt)
    if target_dt.tz is None:
        target_dt = target_dt.tz_localize("UTC")

    row = pd.DataFrame([{
        "heure": target_dt.hour,
        "jour_semaine": target_dt.dayofweek,
        "mois": target_dt.month,
        "pm25_h1": pm25_h1,
        "pm25_h24": pm25_h24,
        "temperature_c": temperature_c,
        "humidity_pct": humidity_pct,
        "wind_speed_ms": wind_speed_ms,
        "precipitation_mm": precipitation_mm,
        "station_id": station_id,
    }])
    row["station_id"] = row["station_id"].astype("category")
    return row[FEATURE_COLUMNS]
