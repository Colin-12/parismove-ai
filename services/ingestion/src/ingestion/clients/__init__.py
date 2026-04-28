"""Clients HTTP pour les sources de données ouvertes."""
from ingestion.clients.aqicn import AqicnAPIError, AqicnClient
from ingestion.clients.meteo import OpenMeteoAPIError, OpenMeteoClient
from ingestion.clients.prim import PrimAPIError, PrimClient

__all__ = [
    "AqicnAPIError",
    "AqicnClient",
    "OpenMeteoAPIError",
    "OpenMeteoClient",
    "PrimAPIError",
    "PrimClient",
]
