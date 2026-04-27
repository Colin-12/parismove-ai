"""Loader PostgreSQL pour `StopVisit` et `AirMeasurement`.

Principe :
    * Insert en batch idempotent (INSERT ... ON CONFLICT DO NOTHING).
    * Calcule les champs dérivés côté Python (delay_seconds).
"""
from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import TypedDict

from shared.schemas import AirMeasurement, StopVisit
from sqlalchemy import Engine, text

logger = logging.getLogger(__name__)


class LoadResult(TypedDict):
    """Résumé d'une opération de chargement."""

    total: int
    inserted: int


# ============================================================================
#  STOP VISITS
# ============================================================================

_INSERT_VISITS_SQL = text(
    """
    INSERT INTO stop_visits (
        stop_id, line_id, vehicle_journey_id,
        line_name, operator, direction, transport_mode,
        aimed_arrival, expected_arrival,
        aimed_departure, expected_departure,
        arrival_status, departure_status,
        delay_seconds,
        recorded_at, source
    )
    VALUES (
        :stop_id, :line_id, :vehicle_journey_id,
        :line_name, :operator, :direction, :transport_mode,
        :aimed_arrival, :expected_arrival,
        :aimed_departure, :expected_departure,
        :arrival_status, :departure_status,
        :delay_seconds,
        :recorded_at, :source
    )
    ON CONFLICT (stop_id, line_id, COALESCE(vehicle_journey_id, ''), recorded_at)
    DO NOTHING
    """
)


def _visit_to_row(visit: StopVisit) -> dict[str, object | None]:
    """Convertit un StopVisit en dict de paramètres pour l'INSERT."""
    return {
        "stop_id": visit.stop_id,
        "line_id": visit.line_id,
        "vehicle_journey_id": visit.vehicle_journey_id,
        "line_name": visit.line_name,
        "operator": visit.operator,
        "direction": visit.direction,
        "transport_mode": visit.transport_mode.value,
        "aimed_arrival": visit.aimed_arrival,
        "expected_arrival": visit.expected_arrival,
        "aimed_departure": visit.aimed_departure,
        "expected_departure": visit.expected_departure,
        "arrival_status": visit.arrival_status,
        "departure_status": visit.departure_status,
        "delay_seconds": visit.delay_seconds,
        "recorded_at": visit.recorded_at,
        "source": visit.source,
    }


def load_stop_visits(
    engine: Engine, visits: Iterable[StopVisit]
) -> LoadResult:
    """Insère une liste de StopVisit dans la table `stop_visits`."""
    rows = [_visit_to_row(v) for v in visits]
    total = len(rows)

    if total == 0:
        return {"total": 0, "inserted": 0}

    with engine.begin() as conn:
        result = conn.execute(_INSERT_VISITS_SQL, rows)
        inserted = result.rowcount if result.rowcount is not None else 0

    logger.info(
        "stop_visits_loaded",
        extra={"total": total, "inserted": inserted},
    )
    return {"total": total, "inserted": inserted}


# ============================================================================
#  AIR MEASUREMENTS
# ============================================================================

_INSERT_AIR_SQL = text(
    """
    INSERT INTO air_measurements (
        station_id, station_name,
        latitude, longitude, city,
        aqi, dominant_pollutant,
        pm25, pm10, no2, o3, so2, co,
        temperature_c, humidity_pct, pressure_hpa,
        measured_at, recorded_at, source
    )
    VALUES (
        :station_id, :station_name,
        :latitude, :longitude, :city,
        :aqi, :dominant_pollutant,
        :pm25, :pm10, :no2, :o3, :so2, :co,
        :temperature_c, :humidity_pct, :pressure_hpa,
        :measured_at, :recorded_at, :source
    )
    ON CONFLICT (station_id, measured_at, source)
    DO NOTHING
    """
)


def _air_to_row(measurement: AirMeasurement) -> dict[str, object | None]:
    """Convertit un AirMeasurement en dict de paramètres pour l'INSERT."""
    return {
        "station_id": measurement.station_id,
        "station_name": measurement.station_name,
        "latitude": measurement.latitude,
        "longitude": measurement.longitude,
        "city": measurement.city,
        "aqi": measurement.aqi,
        "dominant_pollutant": measurement.dominant_pollutant,
        "pm25": measurement.pm25,
        "pm10": measurement.pm10,
        "no2": measurement.no2,
        "o3": measurement.o3,
        "so2": measurement.so2,
        "co": measurement.co,
        "temperature_c": measurement.temperature_c,
        "humidity_pct": measurement.humidity_pct,
        "pressure_hpa": measurement.pressure_hpa,
        "measured_at": measurement.measured_at,
        "recorded_at": measurement.recorded_at,
        "source": measurement.source,
    }


def load_air_measurements(
    engine: Engine, measurements: Iterable[AirMeasurement]
) -> LoadResult:
    """Insère une liste de mesures de qualité de l'air."""
    rows = [_air_to_row(m) for m in measurements]
    total = len(rows)

    if total == 0:
        return {"total": 0, "inserted": 0}

    with engine.begin() as conn:
        result = conn.execute(_INSERT_AIR_SQL, rows)
        inserted = result.rowcount if result.rowcount is not None else 0

    logger.info(
        "air_measurements_loaded",
        extra={"total": total, "inserted": inserted},
    )
    return {"total": total, "inserted": inserted}
