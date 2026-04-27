"""Tests du loader AirMeasurement (logique Python uniquement)."""
from __future__ import annotations

from datetime import UTC, datetime

from shared.schemas import AirMeasurement

from ingestion.loaders.aqicn_loader import _measurement_to_row, load_air_measurements


def _make_measurement(
    station_id: str = "@5722",
    measured_at: datetime | None = None,
) -> AirMeasurement:
    return AirMeasurement(
        station_id=station_id,
        station_name="Aubervilliers",
        latitude=48.8919,
        longitude=2.3796,
        aqi=42,
        pm25=18.0,
        pm10=22.0,
        no2=21.2,
        measured_at=measured_at or datetime(2026, 4, 27, 14, 0, tzinfo=UTC),
        recorded_at=datetime(2026, 4, 27, 14, 5, tzinfo=UTC),
        attribution="Airparif",
    )


class TestMeasurementToRow:
    def test_all_fields_are_mapped(self) -> None:
        m = _make_measurement()
        row = _measurement_to_row(m)

        assert row["station_id"] == "@5722"
        assert row["station_name"] == "Aubervilliers"
        assert row["latitude"] == 48.8919
        assert row["aqi"] == 42
        assert row["pm25"] == 18.0
        assert row["attribution"] == "Airparif"
        assert row["source"] == "aqicn"

    def test_optional_fields_default_to_none(self) -> None:
        m = AirMeasurement(
            station_id="@1",
            station_name="X",
            latitude=0,
            longitude=0,
            measured_at=datetime(2026, 4, 27, 10, 0, tzinfo=UTC),
            recorded_at=datetime(2026, 4, 27, 10, 0, tzinfo=UTC),
        )
        row = _measurement_to_row(m)
        assert row["aqi"] is None
        assert row["pm25"] is None
        assert row["temperature_c"] is None


class TestLoadAirMeasurementsEmptyBatch:
    def test_empty_returns_zero_without_connecting(self) -> None:
        # Pas d'engine fourni : la fonction ne doit pas tenter de s'y connecter
        result = load_air_measurements(None, [])  # type: ignore[arg-type]
        assert result == {"total": 0, "inserted": 0}
