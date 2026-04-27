"""Transformation des réponses sources en objets normalisés."""
from ingestion.transformers.aqicn_transformer import parse_station_response
from ingestion.transformers.prim_transformer import parse_stop_monitoring_response

__all__ = ["parse_station_response", "parse_stop_monitoring_response"]
