"""Tests du loader Postgres.

Ces tests valident la logique Python du loader sans exécuter le SQL réel.
Le comportement ON CONFLICT (spécifique PostgreSQL) est validé en intégration
directe contre Supabase via le script `scripts/check_loader.py`.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ingestion.loaders.postgres import _visit_to_row, load_stop_visits
from shared.schemas import StopVisit, TransportMode


def _make_visit(
    stop_id: str = "STIF:StopPoint:Q:1:",
    line_id: str = "STIF:Line::L1:",
    vehicle_journey_id: str | None = "journey-1",
    recorded_at: datetime | None = None,
) -> StopVisit:
    """Factory pour créer un StopVisit de test."""
    return StopVisit(
        stop_id=stop_id,
        line_id=line_id,
        vehicle_journey_id=vehicle_journey_id,
        line_name="RER B",
        operator="RATP",
        direction="Aéroport CDG",
        transport_mode=TransportMode.RER,
        aimed_arrival=datetime(2026, 4, 24, 10, 0, tzinfo=timezone.utc),
        expected_arrival=datetime(2026, 4, 24, 10, 3, tzinfo=timezone.utc),
        arrival_status="delayed",
        recorded_at=recorded_at
        or datetime(2026, 4, 24, 9, 59, tzinfo=timezone.utc),
    )


class TestVisitToRow:
    """Conversion StopVisit -> dict de paramètres SQL."""

    def test_all_fields_are_mapped(self) -> None:
        visit = _make_visit()
        row = _visit_to_row(visit)

        assert row["stop_id"] == "STIF:StopPoint:Q:1:"
        assert row["line_id"] == "STIF:Line::L1:"
        assert row["vehicle_journey_id"] == "journey-1"
        assert row["line_name"] == "RER B"
        assert row["operator"] == "RATP"
        assert row["direction"] == "Aéroport CDG"
        assert row["transport_mode"] == "rer"
        assert row["arrival_status"] == "delayed"
        assert row["source"] == "prim"

    def test_delay_is_computed(self) -> None:
        visit = _make_visit()
        row = _visit_to_row(visit)
        # 10:00 théorique, 10:03 prévu -> 180 secondes
        assert row["delay_seconds"] == 180

    def test_none_optional_fields_are_preserved(self) -> None:
        visit = _make_visit(vehicle_journey_id=None)
        row = _visit_to_row(visit)
        assert row["vehicle_journey_id"] is None

    def test_transport_mode_is_serialized_as_string(self) -> None:
        """L'enum TransportMode doit être converti en string pour SQL."""
        visit = _make_visit()
        row = _visit_to_row(visit)
        assert row["transport_mode"] == "rer"
        assert isinstance(row["transport_mode"], str)


class TestLoadStopVisitsEmptyBatch:
    """Cas limite : batch vide, ne doit pas toucher à la BDD."""

    def test_empty_batch_returns_zero_without_connecting(self) -> None:
        # On passe None comme engine : si la fonction essaie de s'y connecter,
        # elle crashera. Elle doit retourner un résultat sans même tenter.
        result = load_stop_visits(None, [])  # type: ignore[arg-type]
        assert result == {"total": 0, "inserted": 0}