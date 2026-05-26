"""Inférence : prédiction PM2.5 à H+1 pour une station donnée.

Utilisé par le dashboard et la CLI.

Stratégie de fraîcheur des données (Option B) :
    1. Tente d'abord un appel direct à l'API AQICN pour pm25_h1 live
    2. Si l'appel échoue ou si la mesure a plus de 2h, fallback sur la BDD
    Cette approche garantit que la prédiction porte sur H+1 depuis maintenant,
    pas depuis la dernière mesure stockée (qui peut avoir 4-6h de délai).
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
from sqlalchemy import Engine

from ml_pollution.data_access import fetch_recent_for_inference
from ml_pollution.features import build_inference_row
from ml_pollution.persistence import load_model

logger = logging.getLogger(__name__)

# Délai maximum acceptable pour la mesure live (en heures)
_LIVE_MAX_AGE_HOURS = 2


@dataclass(frozen=True)
class Prediction:
    """Résultat d'une prédiction."""

    station_id: str
    station_name: str
    target_dt: datetime
    predicted_pm25: float
    last_observed_pm25: float
    last_observed_at: datetime
    data_source: str  # "live" ou "db" — pour affichage dans le dashboard


def _fetch_live_pm25(station_id: str) -> tuple[float, datetime] | None:
    """Tente de récupérer la mesure PM2.5 live depuis l'API AQICN.

    Returns:
        (pm25, measured_at) si la mesure est fraîche (< _LIVE_MAX_AGE_HOURS),
        None sinon (erreur réseau, token manquant, mesure trop vieille).
    """
    token = os.environ.get("AQICN_TOKEN", "")
    if not token:
        logger.debug("AQICN_TOKEN absent, fallback BDD")
        return None

    try:
        # Import local pour éviter la dépendance circulaire
        from ingestion.clients.aqicn import AqicnClient

        async def _fetch() -> tuple[float, datetime] | None:
            async with AqicnClient(token=token) as client:
                measurement = await client.get_station(station_id)
            if measurement is None or measurement.pm25 is None:
                return None
            measured_at = measurement.measured_at
            if measured_at.tzinfo is None:
                measured_at = measured_at.replace(tzinfo=UTC)
            age_hours = (
                datetime.now(UTC) - measured_at
            ).total_seconds() / 3600
            if age_hours > _LIVE_MAX_AGE_HOURS:
                logger.debug(
                    "Mesure AQICN trop vieille (%.1fh), fallback BDD",
                    age_hours,
                )
                return None
            return float(measurement.pm25), measured_at

        return asyncio.run(_fetch())

    except Exception as exc:
        logger.debug("Appel AQICN live échoué (%s), fallback BDD", exc)
        return None


def predict_next_hour(
    engine: Engine,
    model_dir: Path,
    station_id: str,
) -> Prediction:
    """Prédit le PM2.5 à H+1 pour une station donnée.

    Tente d'abord une mesure live via l'API AQICN (fraîcheur < 2h).
    Si indisponible, utilise la dernière mesure en BDD.

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

    # --- Tentative mesure live AQICN ---
    live_result = _fetch_live_pm25(station_id)
    if live_result is not None:
        pm25_h1, live_dt = live_result
        last_observed_at = live_dt
        target_dt_ts = pd.Timestamp(live_dt) + pd.Timedelta(hours=1)
        data_source = "live"
        logger.info(
            "Mesure AQICN live utilisée pour %s : %.1f µg/m³",
            station_id,
            pm25_h1,
        )
    else:
        pm25_h1 = float(last_row["pm25"])
        last_observed_at = last_dt.to_pydatetime()
        target_dt_ts = last_dt + pd.Timedelta(hours=1)
        data_source = "db"
        logger.info(
            "Fallback BDD pour %s : dernière mesure à %s",
            station_id,
            last_dt,
        )

    target_dt = target_dt_ts.to_pydatetime()

    # pm25_h24 = mesure ~24h avant la cible (toujours depuis la BDD)
    target_minus_24 = target_dt_ts - pd.Timedelta(hours=24)
    df_station["measured_at"] = pd.to_datetime(
        df_station["measured_at"], utc=True
    )
    older = df_station[df_station["measured_at"] <= target_minus_24]
    pm25_h24: float | None
    if older.empty:
        pm25_h24 = None
    else:
        idx = (older["measured_at"] - target_minus_24).abs().idxmin()
        pm25_h24 = float(older.loc[idx, "pm25"])

    # Météo : dernière obs de la station (depuis la BDD)
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
        target_dt=pd.Timestamp(target_dt),
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
        target_dt=target_dt,
        predicted_pm25=predicted,
        last_observed_pm25=pm25_h1,
        last_observed_at=last_observed_at,
        data_source=data_source,
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

    if features_df.empty:
        return pd.DataFrame(
            columns=["measured_at", "pm25_real", "pm25_predicted"]
        )

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

    valid_idx = features_df.index[valid_mask]
    timestamps = df_station.loc[valid_idx, "measured_at"].to_numpy()
    real_values = df_station.loc[valid_idx, "pm25"].to_numpy()

    target_timestamps = pd.to_datetime(timestamps, utc=True) + timedelta(
        hours=1
    )

    return pd.DataFrame({
        "measured_at": target_timestamps,
        "pm25_real": real_values,
        "pm25_predicted": predictions,
    })


__all__ = [
    "Prediction",
    "backtest_station",
    "predict_next_hour",
]