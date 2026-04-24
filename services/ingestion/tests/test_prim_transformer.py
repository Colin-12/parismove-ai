"""Tests unitaires du transformer SIRI -> StopVisit.

Ces tests tournent hors ligne : ils utilisent une fixture JSON statique
qui reproduit la structure d'une vraie réponse PRIM.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ingestion.transformers.prim_transformer import (
    _extract_value,
    _parse_datetime,
    _parse_transport_mode,
    _short_line_code,
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

    def test_whitespace_string_returns_none(self) -> None:
        assert _extract_value("   ") is None

    def test_dict_with_value_key(self) -> None:
        assert _extract_value({"value": "RER B"}) == "RER B"

    def test_list_of_dicts(self) -> None:
        assert _extract_value([{"value": "La Défense"}]) == "La Défense"

    def test_list_skips_empty_and_returns_first_valid(self) -> None:
        assert _extract_value([{"value": ""}, {"value": "RER A"}]) == "RER A"

    def test_none(self) -> None:
        assert _extract_value(None) is None

    def test_empty_list(self) -> None:
        assert _extract_value([]) is None


class TestParseDatetime:
    def test_utc_with_z_suffix(self) -> None:
        result = _parse_datetime("2026-04-24T10:00:00Z")
        assert result is not None
        assert result.year == 2026
        assert result.tzinfo is not None

    def test_with_offset(self) -> None:
        result = _parse_datetime("2026-04-24T10:00:00+02:00")
        assert result is not None
        assert result.hour == 10

    def test_invalid_returns_none(self) -> None:
        assert _parse_datetime("not a date") is None

    def test_none_returns_none(self) -> None:
        assert _parse_datetime(None) is None


class TestShortLineCode:
    def test_standard_line_ref(self) -> None:
        assert _short_line_code("STIF:Line::C01371:") == "C01371"

    def test_line_ref_without_trailing_colon(self) -> None:
        assert _short_line_code("STIF:Line::C01371") == "C01371"

    def test_none_input(self) -> None:
        assert _short_line_code(None) is None

    def test_empty_string(self) -> None:
        assert _short_line_code("") is None


class TestParseTransportMode:
    @pytest.mark.parametrize(
        "raw_mode,line_id,operator,expected",
        [
            # Cas 1 : champ explicite présent
            (["metro"], None, None, TransportMode.METRO),
            ("rail", None, None, TransportMode.RER),
            ([{"value": "bus"}], None, None, TransportMode.BUS),
            (["tram"], None, None, TransportMode.TRAM),
            # Cas 2 : déduction via préfixe de ligne connu
            (None, "STIF:Line::C01742:", None, TransportMode.RER),  # RER B
            (None, "STIF:Line::C01728:", None, TransportMode.RER),  # RER D
            # Cas 3 : déduction via opérateur
            (None, "STIF:Line::UNKNOWN:", "SNCF", TransportMode.TRAIN),
            # Cas 4 : rien n'est exploitable
            (None, "STIF:Line::XXX:", None, TransportMode.UNKNOWN),
            (None, None, None, TransportMode.UNKNOWN),
        ],
    )
    def test_mode_detection(
        self,
        raw_mode: object,
        line_id: str | None,
        operator: str | None,
        expected: TransportMode,
    ) -> None:
        assert _parse_transport_mode(raw_mode, line_id, operator) == expected


class TestParseStopMonitoringResponse:
    def test_returns_expected_number_of_visits(self, sample_response: dict) -> None:
        visits = parse_stop_monitoring_response(sample_response)
        # 5 visites dans la fixture : 2 RER B, 1 métro 1, 1 bus avec départ, 1 bus sans horaire
        assert len(visits) == 5

    def test_visits_are_sorted_by_best_time(self, sample_response: dict) -> None:
        visits = parse_stop_monitoring_response(sample_response)
        times = [v.best_time for v in visits if v.best_time is not None]
        assert times == sorted(times)

    def test_visit_without_time_is_placed_last(self, sample_response: dict) -> None:
        visits = parse_stop_monitoring_response(sample_response)
        # Le dernier doit être le bus sans aucun horaire
        assert visits[-1].best_time is None
        assert visits[-1].direction == "Musée d'Orsay"

    def test_delay_from_arrival_is_computed(self, sample_response: dict) -> None:
        visits = parse_stop_monitoring_response(sample_response)
        rer_delayed = next(v for v in visits if v.arrival_status == "delayed")
        # 10:05 théorique, 10:07:30 prévu -> 150 secondes de retard
        assert rer_delayed.delay_seconds == 150

    def test_delay_from_departure_when_no_arrival(
        self, sample_response: dict
    ) -> None:
        """Bus Transdev : seul AimedDepartureTime/ExpectedDepartureTime est renvoyé."""
        visits = parse_stop_monitoring_response(sample_response)
        bus = next(
            v for v in visits if v.direction == "Pont de Bezons"
        )
        assert bus.aimed_arrival is None
        assert bus.aimed_departure is not None
        # 10:12 théorique, 10:15 prévu -> 180 secondes
        assert bus.delay_seconds == 180

    def test_on_time_visits_have_zero_delay(self, sample_response: dict) -> None:
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
        rers = [v for v in visits if v.line_name == "RER B"]
        assert len(rers) == 2
        assert all(v.transport_mode == TransportMode.RER for v in rers)

    def test_operator_is_extracted(self, sample_response: dict) -> None:
        visits = parse_stop_monitoring_response(sample_response)
        ratp = next(v for v in visits if v.operator == "RATP")
        assert ratp is not None

    def test_fallback_direction_uses_destination_name(
        self, sample_response: dict
    ) -> None:
        """Le bus Transdev n'a pas DirectionName mais DestinationName."""
        visits = parse_stop_monitoring_response(sample_response)
        bus = next(v for v in visits if v.direction == "Pont de Bezons")
        assert bus is not None

    def test_fallback_line_name_to_short_code(self, sample_response: dict) -> None:
        """Le dernier bus n'a pas PublishedLineName - fallback sur le code court."""
        visits = parse_stop_monitoring_response(sample_response)
        bus = next(v for v in visits if v.direction == "Musée d'Orsay")
        assert bus.line_name == "C01999"

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
                                {  # visite sans MonitoringRef -> skip
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
