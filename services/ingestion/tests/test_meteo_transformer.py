"""Tests unitaires du transformer Open-Meteo."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from ingestion.transformers.meteo_transformer import (
    _parse_datetime,
    _safe_bool,
    _safe_float,
    parse_observation,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def forecast_response() -> dict:
    with (FIXTURES_DIR / "openmeteo_forecast.json").open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def air_quality_response() -> dict:
    with (FIXTURES_DIR / "openmeteo_air_quality.json").open(encoding="utf-8") as f:
        return json.load(f)


class TestSafeFloat:
    def test_int_input(self) -> None:
        assert _safe_float(42) == 42.0

    def test_float_input(self) -> None:
        assert _safe_float(14.5) == 14.5

    def test_string_number(self) -> None:
        assert _safe_float("3.14") == 3.14

    def test_none_input(self) -> None:
        assert _safe_float(None) is None

    def test_invalid_string(self) -> None:
        assert _safe_float("abc") is None


class TestSafeBool:
    def test_zero_is_false(self) -> None:
        assert _safe_bool(0) is False

    def test_one_is_true(self) -> None:
        assert _safe_bool(1) is True

    def test_none(self) -> None:
        assert _safe_bool(None) is None


class TestParseDatetime:
    def test_no_timezone_assumes_utc(self) -> None:
        result = _parse_datetime("2026-04-27T14:00")
        assert result is not None
        assert result.tzinfo is not None

    def test_with_offset(self) -> None:
        result = _parse_datetime("2026-04-27T14:00:00+02:00")
        assert result is not None
        assert result.hour == 14

    def test_invalid_returns_none(self) -> None:
        assert _parse_datetime("not a date") is None


class TestParseObservation:
    def test_full_parse(
        self, forecast_response: dict, air_quality_response: dict
    ) -> None:
        obs = parse_observation(
            forecast_response,
            air_quality_response,
            point_id="paris-centre",
            point_name="Paris centre",
        )
        assert obs is not None
        assert obs.point_id == "paris-centre"
        assert obs.point_name == "Paris centre"

    def test_temperature_extracted(
        self, forecast_response: dict, air_quality_response: dict
    ) -> None:
        obs = parse_observation(
            forecast_response, air_quality_response, "p", "P"
        )
        assert obs is not None
        assert obs.temperature_c == 14.5
        assert obs.apparent_temperature_c == 13.2

    def test_wind_extracted(
        self, forecast_response: dict, air_quality_response: dict
    ) -> None:
        obs = parse_observation(
            forecast_response, air_quality_response, "p", "P"
        )
        assert obs is not None
        assert obs.wind_speed_ms == 4.5
        assert obs.wind_direction_deg == 225

    def test_air_quality_extracted(
        self, forecast_response: dict, air_quality_response: dict
    ) -> None:
        obs = parse_observation(
            forecast_response, air_quality_response, "p", "P"
        )
        assert obs is not None
        assert obs.aqi_european == 2
        assert obs.pm25 == 11
        assert obs.no2 == 24
        assert obs.uv_index == 4.5

    def test_pollens_extracted(
        self, forecast_response: dict, air_quality_response: dict
    ) -> None:
        obs = parse_observation(
            forecast_response, air_quality_response, "p", "P"
        )
        assert obs is not None
        assert obs.birch_pollen == 12
        assert obs.alder_pollen == 0

    def test_is_day_converted_to_bool(
        self, forecast_response: dict, air_quality_response: dict
    ) -> None:
        obs = parse_observation(
            forecast_response, air_quality_response, "p", "P"
        )
        assert obs is not None
        assert obs.is_day is True

    def test_observed_at_parsed(
        self, forecast_response: dict, air_quality_response: dict
    ) -> None:
        obs = parse_observation(
            forecast_response, air_quality_response, "p", "P"
        )
        assert obs is not None
        assert obs.observed_at.year == 2026
        assert obs.observed_at.month == 4
        assert obs.observed_at.day == 27

    def test_works_without_air_quality(self, forecast_response: dict) -> None:
        """Si /air-quality échoue, on doit quand même avoir l'observation météo."""
        obs = parse_observation(forecast_response, None, "p", "P")
        assert obs is not None
        assert obs.temperature_c == 14.5
        assert obs.aqi_european is None
        assert obs.pm25 is None

    def test_no_current_block_returns_none(self) -> None:
        bad_forecast = {"latitude": 48.0, "longitude": 2.0}
        assert parse_observation(bad_forecast, None, "p", "P") is None

    def test_no_time_returns_none(self) -> None:
        bad_forecast = {
            "latitude": 48.0,
            "longitude": 2.0,
            "current": {"temperature_2m": 14.5},  # pas de "time"
        }
        assert parse_observation(bad_forecast, None, "p", "P") is None


class TestHasPrecipitation:
    def test_zero_means_no_precipitation(
        self, forecast_response: dict, air_quality_response: dict
    ) -> None:
        obs = parse_observation(
            forecast_response, air_quality_response, "p", "P"
        )
        assert obs is not None
        assert obs.has_precipitation is False

    def test_rain_means_precipitation(self) -> None:
        from shared.schemas import WeatherObservation

        obs = WeatherObservation(
            point_id="p",
            point_name="P",
            latitude=0,
            longitude=0,
            rain_mm=2.5,
            observed_at=datetime.fromisoformat("2026-04-27T10:00:00+00:00"),
            recorded_at=datetime.fromisoformat("2026-04-27T10:00:00+00:00"),
        )
        assert obs.has_precipitation is True
