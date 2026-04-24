"""Loader PostgreSQL pour les `StopVisit`.

Principe :
    * Prend une `list[StopVisit]` et l'insère en batch dans la table `stop_visits`.
    * Utilise un UPSERT (INSERT ... ON CONFLICT DO NOTHING) pour être idempotent :
      si le cron rejoue le même batch, aucune erreur, aucun doublon.
    * Calcule et stocke `delay_seconds` côté Python (plus lisible que SQL).
"""
from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import TypedDict

from shared.schemas import StopVisit
from sqlalchemy import Engine, text

logger = logging.getLogger(__name__)


class LoadResult(TypedDict):
    """Résumé d'une opération de chargement."""

    total: int          # Nombre de StopVisit reçus
    inserted: int       # Nombre réellement insérés (hors doublons)


_INSERT_SQL = text(
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
    """Insère une liste de StopVisit dans la table `stop_visits`.

    L'insertion est idempotente : si une visite existe déjà (même
    stop/line/journey/recorded_at), elle est ignorée silencieusement.

    Args:
        engine: engine SQLAlchemy (voir `shared.db.create_database_engine`).
        visits: itérable de `StopVisit` à insérer.

    Returns:
        LoadResult avec total reçu et nombre réellement inséré.
    """
    rows = [_visit_to_row(v) for v in visits]
    total = len(rows)

    if total == 0:
        return {"total": 0, "inserted": 0}

    with engine.begin() as conn:
        result = conn.execute(_INSERT_SQL, rows)
        inserted = result.rowcount if result.rowcount is not None else 0

    logger.info(
        "stop_visits_loaded",
        extra={"total": total, "inserted": inserted},
    )

    return {"total": total, "inserted": inserted}
