"""Schémas Pydantic partagés entre services."""
from shared.schemas.air import AirMeasurement
from shared.schemas.mobility import StopVisit, TransportMode
from shared.schemas.weather import WeatherObservation

__all__ = [
    "AirMeasurement",
    "StopVisit",
    "TransportMode",
    "WeatherObservation",
]
