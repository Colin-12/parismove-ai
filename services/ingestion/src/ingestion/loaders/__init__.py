"""Loaders : persistent les données en base."""
from ingestion.loaders.postgres import LoadResult, load_stop_visits

__all__ = ["LoadResult", "load_stop_visits"]
