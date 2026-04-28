"""Loader PostgreSQL pour les `AirMeasurement`.

Idempotent comme le loader StopVisit : INSERT ... ON CONFLICT DO NOTHING
sur la clé (station_id, measured_at).
"""
from __future__ import annotations

import logging
from collections.abc import Iterable

from shared.schemas import AirMeasurement
from sqlalchemy import Engine, text

from ingestion.loaders.postgres import LoadResult

logger = logging.getLogger(__name__)


_INSERT_SQL = text(
    """
    INSERT INTO air_measurements (
        station_id, station_name, latitude, longitude,
        aqi, pm25, pm10, no2, o3, so2, co,
        temperature_c, humidity_pct, pressure_hpa, wind_speed_ms,
        measured_at, recorded_at, attribution, source
    )
    VALUES (
        :station_id, :station_name, :latitude, :longitude,
        :aqi, :pm25, :pm10, :no2, :o3, :so2, :co,
        :temperature_c, :humidity_pct, :pressure_hpa, :wind_speed_ms,
        :measured_at, :recorded_at, :attribution, :source
    )
    ON CONFLICT (station_id, measured_at)
    DO NOTHING
    """
)


def _measurement_to_row(m: AirMeasurement) -> dict[str, object | None]:
    """Convertit un AirMeasurement en dict pour l'INSERT."""
    return {
        "station_id": m.station_id,
        "station_name": m.station_name,
        "latitude": m.latitude,
        "longitude": m.longitude,
        "aqi": m.aqi,
        "pm25": m.pm25,
        "pm10": m.pm10,
        "no2": m.no2,
        "o3": m.o3,
        "so2": m.so2,
        "co": m.co,
        "temperature_c": m.temperature_c,
        "humidity_pct": m.humidity_pct,
        "pressure_hpa": m.pressure_hpa,
        "wind_speed_ms": m.wind_speed_ms,
        "measured_at": m.measured_at,
        "recorded_at": m.recorded_at,
        "attribution": m.attribution,
        "source": m.source,
    }


def load_air_measurements(
    engine: Engine, measurements: Iterable[AirMeasurement]
) -> LoadResult:
    """Insère une liste d'AirMeasurement dans la table `air_measurements`.

    Idempotent : un (station_id, measured_at) déjà présent est ignoré.

    Args:
        engine: engine SQLAlchemy.
        measurements: itérable d'AirMeasurement à insérer.

    Returns:
        LoadResult avec total reçu et nombre réellement inséré.
    """
    rows = [_measurement_to_row(m) for m in measurements]
    total = len(rows)

    if total == 0:
        return {"total": 0, "inserted": 0}

    with engine.begin() as conn:
        result = conn.execute(_INSERT_SQL, rows)
        inserted = result.rowcount if result.rowcount is not None else 0

    logger.info(
        "air_measurements_loaded",
        extra={"total": total, "inserted": inserted},
    )

    return {"total": total, "inserted": inserted}
