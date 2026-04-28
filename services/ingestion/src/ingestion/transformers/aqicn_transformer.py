"""Transforme les réponses JSON d'AQICN en `AirMeasurement` normalisés.

Format de réponse AQICN (résumé) :

    {
      "status": "ok",
      "data": {
        "aqi": 42,
        "idx": 5722,
        "city": {"name": "Paris", "geo": [48.85, 2.35]},
        "iaqi": {
          "pm25": {"v": 18},
          "pm10": {"v": 25},
          "no2": {"v": 12},
          ...
        },
        "time": {"iso": "2026-04-27T14:00:00+02:00"},
        "attributions": [{"name": "Airparif"}]
      }
    }
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from shared.schemas import AirMeasurement


def _safe_float(field: Any) -> float | None:
    """Extrait une valeur numérique d'un champ AQICN type {"v": 18}."""
    if not isinstance(field, dict):
        return None
    value = field.get("v")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(field: Any) -> int | None:
    """Variante entier pour l'AQI (parfois renvoyé en string '-' si indisponible)."""
    if isinstance(field, int):
        return field
    if isinstance(field, str) and field.lstrip("-").isdigit():
        return int(field)
    return None


def _parse_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    normalized = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def parse_station_response(raw: dict[str, Any]) -> AirMeasurement | None:
    """Parse une réponse `/feed/<station>/` AQICN.

    Retourne None si :
        * status != 'ok' (déjà filtré par le client mais ceinture-bretelles)
        * la donnée est trop dégradée pour être exploitable (pas d'horodatage,
          pas de coordonnées, etc.)
    """
    if raw.get("status") != "ok":
        return None

    data = raw.get("data")
    if not isinstance(data, dict):
        return None

    # Géolocalisation : obligatoire pour qu'on puisse exploiter en aval
    city = data.get("city", {})
    geo = city.get("geo") or []
    if len(geo) != 2:
        return None
    try:
        lat, lon = float(geo[0]), float(geo[1])
    except (TypeError, ValueError):
        return None

    # Horodatage : obligatoire
    measured_at = _parse_datetime(data.get("time", {}).get("iso"))
    if measured_at is None:
        return None

    # Identifiant station : on combine idx + name pour un ID stable
    idx = data.get("idx")
    if idx is None:
        return None
    station_id = f"@{idx}"
    station_name = city.get("name") or station_id

    # Mesures détaillées dans iaqi
    iaqi = data.get("iaqi", {})

    # Attribution : on garde la première source officielle citée
    attributions = data.get("attributions", [])
    attribution = (
        attributions[0].get("name")
        if attributions and isinstance(attributions[0], dict)
        else None
    )

    return AirMeasurement(
        station_id=station_id,
        station_name=station_name,
        latitude=lat,
        longitude=lon,
        aqi=_safe_int(data.get("aqi")),
        pm25=_safe_float(iaqi.get("pm25")),
        pm10=_safe_float(iaqi.get("pm10")),
        no2=_safe_float(iaqi.get("no2")),
        o3=_safe_float(iaqi.get("o3")),
        so2=_safe_float(iaqi.get("so2")),
        co=_safe_float(iaqi.get("co")),
        temperature_c=_safe_float(iaqi.get("t")),
        humidity_pct=_safe_float(iaqi.get("h")),
        pressure_hpa=_safe_float(iaqi.get("p")),
        wind_speed_ms=_safe_float(iaqi.get("w")),
        measured_at=measured_at,
        recorded_at=datetime.now().astimezone(),
        attribution=attribution,
        source="aqicn",
    )
