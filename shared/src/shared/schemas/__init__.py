"""Schémas Pydantic partagés entre services."""
from shared.schemas.mobility import StopVisit, TransportMode

__all__ = ["StopVisit", "TransportMode"]
