"""Tests unitaires du transformer AQICN -> AirMeasurement."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from ingestion.transformers.aqicn_transformer import (
    _safe_float,
    _safe_int,
    parse_station_response,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def paris_response() -> dict:
    with (FIXTURES_DIR / "aqicn_paris.json").open(encoding="utf-8") as f:
        return json.load(f)


class TestSafeFloat:
    def test_extracts_v_field(self) -> None:
        assert _safe_float({"v": 18.5}) == 18.5

    def test_extracts_int_value(self) -> None:
        assert _safe_float({"v": 42}) == 42.0

    def test_returns_none_for_missing_v(self) -> None:
        assert _safe_float({}) is None

    def test_returns_none_for_non_dict(self) -> None:
        assert _safe_float(None) is None
        assert _safe_float(42) is None

    def test_returns_none_for_invalid_value(self) -> None:
        assert _safe_float({"v": "not a number"}) is None


class TestSafeInt:
    def test_int_input(self) -> None:
        assert _safe_int(42) == 42

    def test_string_int(self) -> None:
        assert _safe_int("42") == 42

    def test_negative_string(self) -> None:
        assert _safe_int("-10") == -10

    def test_dash_returns_none(self) -> None:
        """AQICN renvoie '-' quand l'AQI n'est pas calculable."""
        assert _safe_int("-") is None

    def test_none_returns_none(self) -> None:
        assert _safe_int(None) is None


class TestParseStationResponse:
    def test_returns_measurement(self, paris_response: dict) -> None:
        m = parse_station_response(paris_response)
        assert m is not None

    def test_aqi_is_extracted(self, paris_response: dict) -> None:
        m = parse_station_response(paris_response)
        assert m is not None
        assert m.aqi == 42

    def test_pollutants_are_extracted(self, paris_response: dict) -> None:
        m = parse_station_response(paris_response)
        assert m is not None
        assert m.pm25 == 42
        assert m.pm10 == 22
        assert m.no2 == pytest.approx(21.2)
        assert m.o3 == pytest.approx(18.4)

    def test_weather_is_extracted(self, paris_response: dict) -> None:
        m = parse_station_response(paris_response)
        assert m is not None
        assert m.temperature_c == pytest.approx(14.8)
        assert m.humidity_pct == 65
        assert m.pressure_hpa == pytest.approx(1014.5)

    def test_geolocation_is_extracted(self, paris_response: dict) -> None:
        m = parse_station_response(paris_response)
        assert m is not None
        assert m.latitude == pytest.approx(48.8919)
        assert m.longitude == pytest.approx(2.3796)

    def test_station_id_is_prefixed_with_at(self, paris_response: dict) -> None:
        m = parse_station_response(paris_response)
        assert m is not None
        assert m.station_id == "@5722"

    def test_attribution_is_first_entry(self, paris_response: dict) -> None:
        m = parse_station_response(paris_response)
        assert m is not None
        assert m.attribution == "Airparif"

    def test_measured_at_is_parsed(self, paris_response: dict) -> None:
        m = parse_station_response(paris_response)
        assert m is not None
        assert m.measured_at == datetime.fromisoformat("2026-04-27T14:00:00+02:00")

    def test_aqi_category(self, paris_response: dict) -> None:
        m = parse_station_response(paris_response)
        assert m is not None
        # AQI = 42 -> "good" (0-50)
        assert m.aqi_category == "good"

    def test_status_error_returns_none(self) -> None:
        response = {"status": "error", "data": "Unknown station"}
        assert parse_station_response(response) is None

    def test_missing_geo_returns_none(self) -> None:
        response = {
            "status": "ok",
            "data": {
                "idx": 1,
                "city": {"name": "X"},  # pas de geo
                "time": {"iso": "2026-04-27T10:00:00Z"},
                "iaqi": {},
            },
        }
        assert parse_station_response(response) is None

    def test_missing_time_returns_none(self) -> None:
        response = {
            "status": "ok",
            "data": {
                "idx": 1,
                "city": {"name": "X", "geo": [48.0, 2.0]},
                "iaqi": {},
            },
        }
        assert parse_station_response(response) is None

    def test_missing_iaqi_does_not_crash(self) -> None:
        """Une station sans aucune mesure de polluant ne doit pas crasher."""
        response = {
            "status": "ok",
            "data": {
                "idx": 1,
                "aqi": "-",
                "city": {"name": "X", "geo": [48.0, 2.0]},
                "time": {"iso": "2026-04-27T10:00:00Z"},
                # pas de iaqi
            },
        }
        m = parse_station_response(response)
        assert m is not None
        assert m.aqi is None
        assert m.pm25 is None


class TestAqiCategoryThresholds:
    """Vérifie que les seuils EPA sont correctement appliqués."""

    @pytest.mark.parametrize(
        "aqi,expected",
        [
            (0, "good"),
            (50, "good"),
            (51, "moderate"),
            (100, "moderate"),
            (101, "unhealthy_sensitive"),
            (150, "unhealthy_sensitive"),
            (151, "unhealthy"),
            (200, "unhealthy"),
            (201, "very_unhealthy"),
            (300, "very_unhealthy"),
            (301, "hazardous"),
            (500, "hazardous"),
        ],
    )
    def test_categories(self, aqi: int, expected: str) -> None:
        from shared.schemas import AirMeasurement

        m = AirMeasurement(
            station_id="@1",
            station_name="X",
            latitude=0,
            longitude=0,
            aqi=aqi,
            measured_at=datetime.fromisoformat("2026-04-27T10:00:00+00:00"),
            recorded_at=datetime.fromisoformat("2026-04-27T10:00:00+00:00"),
        )
        assert m.aqi_category == expected
