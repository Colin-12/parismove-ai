"""Référentiels statiques (lignes IDFM, etc.)."""
from ingestion.reference.idfm_loader import (
    fetch_idfm_lines,
    upsert_idfm_lines,
)

__all__ = ["fetch_idfm_lines", "upsert_idfm_lines"]
