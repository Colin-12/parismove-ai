"""Schémas Pydantic partagés entre services."""
from shared.schemas.air import AirMeasurement
from shared.schemas.health import (
    HealthGrade,
    JourneyComparison,
    JourneyScore,
    WaypointExposure,
)
from shared.schemas.mobility import StopVisit, TransportMode
from shared.schemas.weather import WeatherObservation

__all__ = [
    "AirMeasurement",
    "HealthGrade",
    "JourneyComparison",
    "JourneyScore",
    "StopVisit",
    "TransportMode",
    "WaypointExposure",
    "WeatherObservation",
]
