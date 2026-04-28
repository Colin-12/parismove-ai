"""Tests du loader WeatherObservation (logique Python uniquement)."""
from __future__ import annotations

from datetime import UTC, datetime

from shared.schemas import WeatherObservation

from ingestion.loaders.meteo_loader import (
    _observation_to_row,
    load_weather_observations,
)


def _make_observation(
    point_id: str = "paris-centre",
    observed_at: datetime | None = None,
) -> WeatherObservation:
    return WeatherObservation(
        point_id=point_id,
        point_name="Paris centre",
        latitude=48.8566,
        longitude=2.3522,
        elevation_m=35.0,
        temperature_c=14.5,
        humidity_pct=60,
        precipitation_mm=0.0,
        wind_speed_ms=4.5,
        weather_code=3,
        aqi_european=2,
        pm25=11,
        no2=24,
        observed_at=observed_at or datetime(2026, 4, 27, 14, 0, tzinfo=UTC),
        recorded_at=datetime(2026, 4, 27, 14, 5, tzinfo=UTC),
    )


class TestObservationToRow:
    def test_all_fields_are_mapped(self) -> None:
        obs = _make_observation()
        row = _observation_to_row(obs)

        assert row["point_id"] == "paris-centre"
        assert row["temperature_c"] == 14.5
        assert row["aqi_european"] == 2
        assert row["pm25"] == 11
        assert row["weather_code"] == 3
        assert row["source"] == "open-meteo"

    def test_missing_optional_fields_are_none(self) -> None:
        obs = WeatherObservation(
            point_id="p",
            point_name="P",
            latitude=0,
            longitude=0,
            observed_at=datetime(2026, 4, 27, 10, 0, tzinfo=UTC),
            recorded_at=datetime(2026, 4, 27, 10, 0, tzinfo=UTC),
        )
        row = _observation_to_row(obs)
        assert row["temperature_c"] is None
        assert row["aqi_european"] is None
        assert row["uv_index"] is None


class TestLoadWeatherObservationsEmpty:
    def test_empty_returns_zero_without_connecting(self) -> None:
        result = load_weather_observations(None, [])  # type: ignore[arg-type]
        assert result == {"total": 0, "inserted": 0}
