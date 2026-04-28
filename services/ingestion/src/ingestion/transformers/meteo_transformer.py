"""Transforme les réponses JSON d'Open-Meteo en `WeatherObservation`.

Open-Meteo renvoie 2 endpoints distincts qu'on agrège ici :

1. /v1/forecast : météo (température, vent, précipitations...)
2. /v1/air-quality : qualité de l'air modélisée (CAMS)

On fait un seul appel par endpoint par point d'observation.

Format simplifié d'une réponse `current` du forecast :

    {
      "latitude": 48.85, "longitude": 2.35, "elevation": 35.0,
      "current": {
        "time": "2026-04-27T14:00",
        "temperature_2m": 14.5,
        "relative_humidity_2m": 60,
        "apparent_temperature": 13.2,
        "is_day": 1,
        "precipitation": 0.0,
        "rain": 0.0,
        "showers": 0.0,
        "snowfall": 0.0,
        "weather_code": 3,
        "cloud_cover": 75,
        "pressure_msl": 1015.2,
        "surface_pressure": 1011.0,
        "wind_speed_10m": 4.5,
        "wind_direction_10m": 225,
        "wind_gusts_10m": 7.8
      }
    }

Et pour /v1/air-quality :

    {
      "latitude": 48.85, "longitude": 2.35,
      "current": {
        "time": "2026-04-27T14:00",
        "european_aqi": 2,
        "pm10": 18,
        "pm2_5": 11,
        "carbon_monoxide": 220,
        "nitrogen_dioxide": 24,
        "ozone": 65,
        "sulphur_dioxide": 1.5,
        "uv_index": 4.5,
        "alder_pollen": 0,
        "birch_pollen": 12,
        "grass_pollen": 3,
        "ragweed_pollen": 0
      }
    }
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from shared.schemas import WeatherObservation


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_bool(value: Any) -> bool | None:
    """Open-Meteo renvoie 0/1 pour les booléens."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    return None


def _parse_datetime(raw: str | None) -> datetime | None:
    """Open-Meteo renvoie des dates ISO sans timezone (UTC implicite)."""
    if not raw:
        return None
    # On force UTC si pas de timezone explicite
    if not raw.endswith("Z") and "+" not in raw and len(raw) <= 19:
        raw = raw + "+00:00"
    normalized = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def parse_observation(
    forecast_response: dict[str, Any],
    air_quality_response: dict[str, Any] | None,
    point_id: str,
    point_name: str,
) -> WeatherObservation | None:
    """Combine les réponses météo et air en une seule observation normalisée.

    Args:
        forecast_response: réponse de /v1/forecast (obligatoire).
        air_quality_response: réponse de /v1/air-quality (optionnelle).
        point_id: slug logique du point (ex: 'paris-centre').
        point_name: nom lisible.

    Returns:
        WeatherObservation, ou None si la donnée météo est absente / dégradée.
    """
    current = forecast_response.get("current")
    if not isinstance(current, dict):
        return None

    observed_at = _parse_datetime(current.get("time"))
    if observed_at is None:
        return None

    lat = _safe_float(forecast_response.get("latitude"))
    lon = _safe_float(forecast_response.get("longitude"))
    if lat is None or lon is None:
        return None

    air = (
        air_quality_response.get("current", {})
        if isinstance(air_quality_response, dict)
        else {}
    )

    return WeatherObservation(
        point_id=point_id,
        point_name=point_name,
        latitude=lat,
        longitude=lon,
        elevation_m=_safe_float(forecast_response.get("elevation")),
        # Météo
        temperature_c=_safe_float(current.get("temperature_2m")),
        apparent_temperature_c=_safe_float(current.get("apparent_temperature")),
        humidity_pct=_safe_float(current.get("relative_humidity_2m")),
        pressure_hpa=_safe_float(current.get("pressure_msl")),
        surface_pressure_hpa=_safe_float(current.get("surface_pressure")),
        cloud_cover_pct=_safe_float(current.get("cloud_cover")),
        visibility_m=_safe_float(current.get("visibility")),
        # Précipitations
        precipitation_mm=_safe_float(current.get("precipitation")),
        rain_mm=_safe_float(current.get("rain")),
        showers_mm=_safe_float(current.get("showers")),
        snowfall_cm=_safe_float(current.get("snowfall")),
        # Vent
        wind_speed_ms=_safe_float(current.get("wind_speed_10m")),
        wind_gusts_ms=_safe_float(current.get("wind_gusts_10m")),
        wind_direction_deg=_safe_float(current.get("wind_direction_10m")),
        # Soleil
        is_day=_safe_bool(current.get("is_day")),
        weather_code=_safe_int(current.get("weather_code")),
        # Qualité de l'air (depuis air-quality)
        aqi_european=_safe_float(air.get("european_aqi")),
        pm25=_safe_float(air.get("pm2_5")),
        pm10=_safe_float(air.get("pm10")),
        no2=_safe_float(air.get("nitrogen_dioxide")),
        o3=_safe_float(air.get("ozone")),
        so2=_safe_float(air.get("sulphur_dioxide")),
        co=_safe_float(air.get("carbon_monoxide")),
        uv_index=_safe_float(air.get("uv_index")),
        # Pollens
        alder_pollen=_safe_float(air.get("alder_pollen")),
        birch_pollen=_safe_float(air.get("birch_pollen")),
        grass_pollen=_safe_float(air.get("grass_pollen")),
        ragweed_pollen=_safe_float(air.get("ragweed_pollen")),
        # Traçabilité
        observed_at=observed_at,
        recorded_at=datetime.now().astimezone(),
        source="open-meteo",
    )
