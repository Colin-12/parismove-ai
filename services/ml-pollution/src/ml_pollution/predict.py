"""Inférence : prédiction PM2.5 à H+1 pour une station donnée.

Utilisé par le dashboard et la CLI.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import Engine

from ml_pollution.data_access import fetch_recent_for_inference
from ml_pollution.features import build_inference_row
from ml_pollution.persistence import load_model


@dataclass(frozen=True)
class Prediction:
    """Résultat d'une prédiction."""

    station_id: str
    station_name: str
    target_dt: datetime
    predicted_pm25: float
    last_observed_pm25: float
    last_observed_at: datetime


def predict_next_hour(
    engine: Engine,
    model_dir: Path,
    station_id: str,
) -> Prediction:
    """Prédit le PM2.5 à H+1 pour une station donnée.

    Reconstruit les features nécessaires depuis la BDD :
        * pm25_h1   = dernière mesure de la station
        * pm25_h24  = mesure de la même station il y a ~24h
        * météo     = obs météo récente du point le plus proche

    Args:
        engine: SQLAlchemy engine
        model_dir: répertoire où le modèle est sauvegardé
        station_id: ID Airparif (ex: '@5722')

    Returns:
        Prediction avec la valeur prédite et le contexte.

    Raises:
        FileNotFoundError: si le modèle n'a jamais été entraîné
        ValueError: si la station n'a pas de mesure récente
    """
    model, _meta = load_model(model_dir)

    df = fetch_recent_for_inference(engine, hours_back=48)
    df_station = df[df["station_id"] == station_id].copy()
    if df_station.empty:
        raise ValueError(
            f"Aucune mesure récente pour la station {station_id}. "
            "Le modèle ne peut pas prédire sans contexte."
        )

    df_station = df_station.sort_values("measured_at")
    last_row = df_station.iloc[-1]
    last_dt = pd.Timestamp(last_row["measured_at"])
    if last_dt.tz is None:
        last_dt = last_dt.tz_localize("UTC")

    target_dt = last_dt + pd.Timedelta(hours=1)

    # pm25_h1 = la dernière mesure (l'heure H actuelle)
    pm25_h1 = float(last_row["pm25"])

    # pm25_h24 = mesure ~24h avant la cible
    target_minus_24 = target_dt - pd.Timedelta(hours=24)
    df_station["measured_at"] = pd.to_datetime(
        df_station["measured_at"], utc=True
    )
    older = df_station[df_station["measured_at"] <= target_minus_24]
    pm25_h24: float | None
    if older.empty:
        pm25_h24 = None
    else:
        # On prend la mesure la plus proche de target-24h
        idx = (older["measured_at"] - target_minus_24).abs().idxmin()
        pm25_h24 = float(older.loc[idx, "pm25"])

    # Météo : on prend la dernière obs de la station
    def _coerce(value: object) -> float | None:
        if value is None or pd.isna(value):
            return None
        return float(value)  # type: ignore[arg-type]

    temperature_c = _coerce(last_row.get("temperature_c"))
    humidity_pct = _coerce(last_row.get("humidity_pct"))
    wind_speed_ms = _coerce(last_row.get("wind_speed_ms"))
    precipitation_mm = _coerce(last_row.get("precipitation_mm"))

    features = build_inference_row(
        station_id=station_id,
        target_dt=target_dt,
        pm25_h1=pm25_h1,
        pm25_h24=pm25_h24,
        temperature_c=temperature_c,
        humidity_pct=humidity_pct,
        wind_speed_ms=wind_speed_ms,
        precipitation_mm=precipitation_mm,
    )

    predicted = float(model.predict(features)[0])

    return Prediction(
        station_id=station_id,
        station_name=str(last_row["station_name"]),
        target_dt=target_dt.to_pydatetime(),
        predicted_pm25=predicted,
        last_observed_pm25=pm25_h1,
        last_observed_at=last_dt.to_pydatetime(),
    )


def backtest_station(
    engine: Engine,
    model_dir: Path,
    station_id: str,
    hours: int = 48,
) -> pd.DataFrame:
    """Génère les prédictions historiques pour une station (visualisation).

    Pour chaque heure de la fenêtre où on a les features nécessaires,
    on calcule ce que le modèle aurait prédit. Permet de tracer la courbe
    "Prédiction passée" du dashboard.

    Returns:
        DataFrame avec colonnes : measured_at, pm25_real, pm25_predicted
    """
    model, _meta = load_model(model_dir)

    df = fetch_recent_for_inference(engine, hours_back=hours + 24)
    df_station = df[df["station_id"] == station_id].copy()
    if df_station.empty:
        return pd.DataFrame(
            columns=["measured_at", "pm25_real", "pm25_predicted"]
        )

    from ml_pollution.features import FEATURE_COLUMNS, build_features

    features_df = build_features(df_station, for_training=False)
    df_station = df_station.sort_values("measured_at").reset_index(drop=True)

    # Aligne les features avec les mesures (même order)
    if features_df.empty:
        return pd.DataFrame(
            columns=["measured_at", "pm25_real", "pm25_predicted"]
        )

    # On ne prédit que sur les lignes qui ont les lag (h1 et h24 non NaN)
    valid_mask = (
        features_df["pm25_h1"].notna() & features_df["pm25_h24"].notna()
    )
    valid_features = features_df.loc[valid_mask, FEATURE_COLUMNS].copy()
    if valid_features.empty:
        return pd.DataFrame(
            columns=["measured_at", "pm25_real", "pm25_predicted"]
        )

    valid_features["station_id"] = valid_features["station_id"].astype(
        "category"
    )
    predictions = model.predict(valid_features)

    # On aligne avec les timestamps correspondants
    valid_idx = features_df.index[valid_mask]
    timestamps = df_station.loc[valid_idx, "measured_at"].to_numpy()
    real_values = df_station.loc[valid_idx, "pm25"].to_numpy()

    # Les prédictions sont pour H+1 par rapport aux features
    target_timestamps = pd.to_datetime(timestamps, utc=True) + timedelta(
        hours=1
    )

    return pd.DataFrame({
        "measured_at": target_timestamps,
        "pm25_real": real_values,
        "pm25_predicted": predictions,
    })


# Imports dynamiques nécessaires pour éviter les circulaires
__all__ = [
    "Prediction",
    "backtest_station",
    "predict_next_hour",
]


# datetime/timezone non-utilisés pour le typage ci-dessus; pour ruff
_ = (datetime, timezone)
