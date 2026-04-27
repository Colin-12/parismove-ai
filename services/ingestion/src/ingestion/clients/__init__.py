"""Clients HTTP pour les sources de données ouvertes."""
from ingestion.clients.aqicn import AqicnAPIError, AqicnClient
from ingestion.clients.prim import PrimAPIError, PrimClient

__all__ = ["AqicnAPIError", "AqicnClient", "PrimAPIError", "PrimClient"]
