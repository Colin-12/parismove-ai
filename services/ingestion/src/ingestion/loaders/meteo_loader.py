"""Loader PostgreSQL pour les `WeatherObservation`.

Idempotent : INSERT ... ON CONFLICT DO NOTHING sur (point_id, observed_at).
"""
from __future__ import annotations

import logging
from collections.abc import Iterable

from shared.schemas import WeatherObservation
from sqlalchemy import Engine, text

from ingestion.loaders.postgres import LoadResult

logger = logging.getLogger(__name__)


_INSERT_SQL = text(
    """
    INSERT INTO weather_observations (
        point_id, point_name, latitude, longitude, elevation_m,
        temperature_c, apparent_temperature_c, humidity_pct,
        pressure_hpa, surface_pressure_hpa, cloud_cover_pct, visibility_m,
        precipitation_mm, rain_mm, showers_mm, snowfall_cm,
        wind_speed_ms, wind_gusts_ms, wind_direction_deg,
        uv_index, is_day, weather_code,
        aqi_european, pm25, pm10, no2, o3, so2, co,
        alder_pollen, birch_pollen, grass_pollen, ragweed_pollen,
        observed_at, recorded_at, source
    )
    VALUES (
        :point_id, :point_name, :latitude, :longitude, :elevation_m,
        :temperature_c, :apparent_temperature_c, :humidity_pct,
        :pressure_hpa, :surface_pressure_hpa, :cloud_cover_pct, :visibility_m,
        :precipitation_mm, :rain_mm, :showers_mm, :snowfall_cm,
        :wind_speed_ms, :wind_gusts_ms, :wind_direction_deg,
        :uv_index, :is_day, :weather_code,
        :aqi_european, :pm25, :pm10, :no2, :o3, :so2, :co,
        :alder_pollen, :birch_pollen, :grass_pollen, :ragweed_pollen,
        :observed_at, :recorded_at, :source
    )
    ON CONFLICT (point_id, observed_at)
    DO NOTHING
    """
)


def _observation_to_row(obs: WeatherObservation) -> dict[str, object | None]:
    """Convertit une WeatherObservation en dict pour l'INSERT."""
    return {
        "point_id": obs.point_id,
        "point_name": obs.point_name,
        "latitude": obs.latitude,
        "longitude": obs.longitude,
        "elevation_m": obs.elevation_m,
        "temperature_c": obs.temperature_c,
        "apparent_temperature_c": obs.apparent_temperature_c,
        "humidity_pct": obs.humidity_pct,
        "pressure_hpa": obs.pressure_hpa,
        "surface_pressure_hpa": obs.surface_pressure_hpa,
        "cloud_cover_pct": obs.cloud_cover_pct,
        "visibility_m": obs.visibility_m,
        "precipitation_mm": obs.precipitation_mm,
        "rain_mm": obs.rain_mm,
        "showers_mm": obs.showers_mm,
        "snowfall_cm": obs.snowfall_cm,
        "wind_speed_ms": obs.wind_speed_ms,
        "wind_gusts_ms": obs.wind_gusts_ms,
        "wind_direction_deg": obs.wind_direction_deg,
        "uv_index": obs.uv_index,
        "is_day": obs.is_day,
        "weather_code": obs.weather_code,
        "aqi_european": obs.aqi_european,
        "pm25": obs.pm25,
        "pm10": obs.pm10,
        "no2": obs.no2,
        "o3": obs.o3,
        "so2": obs.so2,
        "co": obs.co,
        "alder_pollen": obs.alder_pollen,
        "birch_pollen": obs.birch_pollen,
        "grass_pollen": obs.grass_pollen,
        "ragweed_pollen": obs.ragweed_pollen,
        "observed_at": obs.observed_at,
        "recorded_at": obs.recorded_at,
        "source": obs.source,
    }


def load_weather_observations(
    engine: Engine, observations: Iterable[WeatherObservation]
) -> LoadResult:
    """Insère une liste de WeatherObservation dans la table.

    Idempotent : un (point_id, observed_at) déjà présent est ignoré.

    Args:
        engine: engine SQLAlchemy.
        observations: itérable de WeatherObservation à insérer.

    Returns:
        LoadResult avec total reçu et nombre réellement inséré.
    """
    rows = [_observation_to_row(o) for o in observations]
    total = len(rows)

    if total == 0:
        return {"total": 0, "inserted": 0}

    with engine.begin() as conn:
        result = conn.execute(_INSERT_SQL, rows)
        inserted = result.rowcount if result.rowcount is not None else 0

    logger.info(
        "weather_observations_loaded",
        extra={"total": total, "inserted": inserted},
    )

    return {"total": total, "inserted": inserted}
