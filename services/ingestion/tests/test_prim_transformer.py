"""Tests unitaires du transformer SIRI → StopVisit.

Ces tests tournent hors ligne : ils utilisent une fixture JSON statique
qui reproduit la structure d'une vraie réponse PRIM.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ingestion.transformers.prim_transformer import (
    _extract_value,
    _parse_datetime,
    _parse_transport_mode,
    parse_stop_monitoring_response,
)
from shared.schemas import TransportMode

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_response() -> dict:
    """Charge la fixture PRIM complète."""
    with (FIXTURES_DIR / "prim_stop_monitoring.json").open(encoding="utf-8") as f:
        return json.load(f)


class TestExtractValue:
    """Le champ SIRI peut venir en dict, list ou string. On normalise tout."""

    def test_string_input(self) -> None:
        assert _extract_value("hello") == "hello"

    def test_dict_with_value_key(self) -> None:
        assert _extract_value({"value": "RER B"}) == "RER B"

    def test_list_of_dicts(self) -> None:
        assert _extract_value([{"value": "La Défense"}]) == "La Défense"

    def test_none(self) -> None:
        assert _extract_value(None) is None

    def test_empty_list(self) -> None:
        assert _extract_value([]) is None


class TestParseDatetime:
    def test_utc_with_z_suffix(self) -> None:
        result = _parse_datetime("2026-04-24T10:00:00Z")
        assert result is not None
        assert result.year == 2026
        assert result.month == 4
        assert result.tzinfo is not None

    def test_with_offset(self) -> None:
        result = _parse_datetime("2026-04-24T10:00:00+02:00")
        assert result is not None
        assert result.hour == 10

    def test_invalid_returns_none(self) -> None:
        assert _parse_datetime("not a date") is None

    def test_none_returns_none(self) -> None:
        assert _parse_datetime(None) is None


class TestParseTransportMode:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            (["metro"], TransportMode.METRO),
            ("rail", TransportMode.RER),
            ([{"value": "bus"}], TransportMode.BUS),
            (["tram"], TransportMode.TRAM),
            (["unknown_mode"], TransportMode.UNKNOWN),
            (None, TransportMode.UNKNOWN),
        ],
    )
    def test_mode_mapping(self, raw: object, expected: TransportMode) -> None:
        assert _parse_transport_mode(raw) == expected


class TestParseStopMonitoringResponse:
    def test_returns_expected_number_of_visits(self, sample_response: dict) -> None:
        visits = parse_stop_monitoring_response(sample_response)
        assert len(visits) == 3

    def test_visits_are_sorted_by_expected_arrival(
        self, sample_response: dict
    ) -> None:
        visits = parse_stop_monitoring_response(sample_response)
        arrivals = [v.expected_arrival for v in visits if v.expected_arrival]
        assert arrivals == sorted(arrivals)

    def test_delay_is_computed_correctly(self, sample_response: dict) -> None:
        visits = parse_stop_monitoring_response(sample_response)
        delayed = next(v for v in visits if v.arrival_status == "delayed")
        # Horaire théorique 10:05, prévu 10:07:30 → 150s de retard
        assert delayed.delay_seconds == 150

    def test_on_time_visit_has_zero_delay(self, sample_response: dict) -> None:
        visits = parse_stop_monitoring_response(sample_response)
        on_time = [v for v in visits if v.arrival_status == "onTime"]
        assert all(v.delay_seconds == 0 for v in on_time)

    def test_metro_line_1_is_detected(self, sample_response: dict) -> None:
        visits = parse_stop_monitoring_response(sample_response)
        metro = next(v for v in visits if v.transport_mode == TransportMode.METRO)
        assert metro.line_name == "1"
        assert "La Défense" in (metro.direction or "")

    def test_rer_b_is_detected(self, sample_response: dict) -> None:
        visits = parse_stop_monitoring_response(sample_response)
        rers = [v for v in visits if v.transport_mode == TransportMode.RER]
        assert len(rers) == 2
        assert all(v.line_name == "RER B" for v in rers)

    def test_empty_response_returns_empty_list(self) -> None:
        empty = {"Siri": {"ServiceDelivery": {"StopMonitoringDelivery": []}}}
        assert parse_stop_monitoring_response(empty) == []

    def test_malformed_response_does_not_raise(self) -> None:
        """Robustesse : une réponse cassée doit retourner [] et non crash."""
        assert parse_stop_monitoring_response({}) == []
        assert parse_stop_monitoring_response({"Siri": {}}) == []

    def test_invalid_visit_is_skipped(self) -> None:
        """Une visite sans stop_id ou line_id est ignorée, pas de crash."""
        response = {
            "Siri": {
                "ServiceDelivery": {
                    "ResponseTimestamp": "2026-04-24T10:00:00Z",
                    "StopMonitoringDelivery": [
                        {
                            "MonitoredStopVisit": [
                                {  # visite sans MonitoringRef → skip
                                    "MonitoredVehicleJourney": {
                                        "LineRef": {"value": "L1"}
                                    }
                                },
                                {  # visite valide
                                    "MonitoringRef": {"value": "STIF:StopPoint:Q:1:"},
                                    "MonitoredVehicleJourney": {
                                        "LineRef": {"value": "STIF:Line::L1:"}
                                    },
                                },
                            ]
                        }
                    ],
                }
            }
        }
        visits = parse_stop_monitoring_response(response)
        assert len(visits) == 1
        assert visits[0].stop_id == "STIF:StopPoint:Q:1:"
