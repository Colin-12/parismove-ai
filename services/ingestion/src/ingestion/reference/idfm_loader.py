"""Récupération et chargement du référentiel des lignes IDFM.

Source officielle :
    https://data.iledefrance-mobilites.fr/explore/dataset/referentiel-des-lignes/

API Opendatasoft (ODS) v2.1 :
    https://data.iledefrance-mobilites.fr/api/explore/v2.1/catalog/datasets/
        referentiel-des-lignes/records?limit=100&offset=0

L'API retourne des pages de 100 résultats max. On itère jusqu'à épuisement.

Format d'un enregistrement (champs utiles) :
    {
      "id_line": "C01390",
      "shortname_line": "T2",
      "name_line": "Tramway T2",
      "transportmode": "tram",
      "transportsubmode": null,
      "networkname": "RATP",
      "operatorname": "RATP",
      "colourweb_hexa": "7B388C",
      "textcolourweb_hexa": "FFFFFF",
      "status": "active",
      "accessibility": "yes"
    }

Note IDFM : `id_line` est le code court (C01390). On reconstruit l'ID complet
SIRI au format `STIF:Line::C01390:` pour matcher avec stop_visits.line_id.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlalchemy import Engine, text
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

IDFM_REFERENTIEL_URL = (
    "https://data.iledefrance-mobilites.fr/api/explore/v2.1/catalog/"
    "datasets/referentiel-des-lignes/records"
)

PAGE_SIZE = 100  # Limite max de l'API ODS


def _build_line_id(raw_id: str | None) -> str | None:
    """Reconstruit l'ID SIRI complet à partir du code court IDFM.

    "C01390" -> "STIF:Line::C01390:"
    "" -> None
    None -> None
    """
    if not raw_id:
        return None
    return f"STIF:Line::{raw_id}:"


def _normalize_color(raw: str | None) -> str | None:
    """Normalise une couleur en format #RRGGBB.

    "7B388C" -> "#7B388C"
    "#7b388c" -> "#7B388C"
    "" -> None
    """
    if not raw:
        return None
    cleaned = raw.strip().lstrip("#").upper()
    if len(cleaned) != 6:
        return None
    return f"#{cleaned}"


def _record_to_row(record: dict[str, Any]) -> dict[str, object | None] | None:
    """Convertit un enregistrement ODS en row pour idfm_lines.

    Retourne None si l'enregistrement est inexploitable (pas d'id_line).
    """
    line_id = _build_line_id(record.get("id_line"))
    if line_id is None:
        return None

    return {
        "line_id": line_id,
        "short_name": record.get("shortname_line") or None,
        "long_name": record.get("name_line") or None,
        "transport_mode": record.get("transportmode") or None,
        "transport_submode": record.get("transportsubmode") or None,
        "network_name": record.get("networkname") or None,
        "operator_name": record.get("operatorname") or None,
        "color_web_hex": _normalize_color(record.get("colourweb_hexa")),
        "text_color_hex": _normalize_color(record.get("textcolourweb_hexa")),
        "status": record.get("status") or None,
        "accessibility": record.get("accessibility") or None,
    }


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(
        (httpx.TimeoutException, httpx.HTTPStatusError)
    ),
    reraise=True,
)
async def _fetch_page(
    client: httpx.AsyncClient, offset: int
) -> dict[str, Any]:
    response = await client.get(
        IDFM_REFERENTIEL_URL,
        params={"limit": PAGE_SIZE, "offset": offset},
    )
    response.raise_for_status()
    data: dict[str, Any] = response.json()
    return data


async def fetch_idfm_lines() -> list[dict[str, object | None]]:
    """Télécharge le référentiel complet des lignes IDFM.

    Returns:
        Liste de rows prêtes pour insertion dans idfm_lines.
    """
    rows: list[dict[str, object | None]] = []
    seen_line_ids: set[str] = set()
    offset = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            logger.info("idfm_referentiel_fetch", extra={"offset": offset})
            data = await _fetch_page(client, offset)
            results = data.get("results", [])

            if not results:
                break

            for record in results:
                row = _record_to_row(record)
                if row is None:
                    continue
                # Déduplication : l'API peut retourner plusieurs fois la même
                # ligne dans des sous-modes différents
                line_id = row["line_id"]
                assert isinstance(line_id, str)
                if line_id in seen_line_ids:
                    continue
                seen_line_ids.add(line_id)
                rows.append(row)

            # Si on a reçu moins que PAGE_SIZE, c'est fini
            if len(results) < PAGE_SIZE:
                break

            offset += PAGE_SIZE

    logger.info("idfm_referentiel_fetched", extra={"count": len(rows)})
    return rows


# UPSERT : si line_id existe déjà, on met à jour les autres colonnes.
# Utile car les noms/couleurs peuvent évoluer (changement opérateur, etc.).
_UPSERT_SQL = text(
    """
    INSERT INTO idfm_lines (
        line_id, short_name, long_name,
        transport_mode, transport_submode,
        network_name, operator_name,
        color_web_hex, text_color_hex,
        status, accessibility, last_refreshed_at
    )
    VALUES (
        :line_id, :short_name, :long_name,
        :transport_mode, :transport_submode,
        :network_name, :operator_name,
        :color_web_hex, :text_color_hex,
        :status, :accessibility, NOW()
    )
    ON CONFLICT (line_id) DO UPDATE SET
        short_name        = EXCLUDED.short_name,
        long_name         = EXCLUDED.long_name,
        transport_mode    = EXCLUDED.transport_mode,
        transport_submode = EXCLUDED.transport_submode,
        network_name      = EXCLUDED.network_name,
        operator_name     = EXCLUDED.operator_name,
        color_web_hex     = EXCLUDED.color_web_hex,
        text_color_hex    = EXCLUDED.text_color_hex,
        status            = EXCLUDED.status,
        accessibility     = EXCLUDED.accessibility,
        last_refreshed_at = NOW()
    """
)


def upsert_idfm_lines(
    engine: Engine, rows: list[dict[str, object | None]]
) -> int:
    """Insère ou met à jour les lignes IDFM.

    Returns:
        Nombre de rows traitées.
    """
    if not rows:
        return 0

    with engine.begin() as conn:
        conn.execute(_UPSERT_SQL, rows)

    logger.info("idfm_referentiel_upserted", extra={"count": len(rows)})
    return len(rows)
