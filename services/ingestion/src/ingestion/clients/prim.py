"""Client HTTP pour l'API PRIM Île-de-France Mobilités.

Documentation officielle :
    https://prim.iledefrance-mobilites.fr/fr/apis/idfm-ivtr-requete_unitaire

Cette API utilise le format SIRI-Lite (standard européen pour l'info voyageurs).
On encapsule la complexité SIRI dans ce client, et on expose des `StopVisit`
normalisés au reste du pipeline.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx
from shared.schemas import StopVisit
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ingestion.transformers.prim_transformer import parse_stop_monitoring_response

logger = logging.getLogger(__name__)


class PrimAPIError(Exception):
    """Erreur retournée par l'API PRIM (4xx, 5xx, réponse invalide)."""


class PrimClient:
    """Client pour l'API PRIM IDFM "Prochains passages".

    Usage:
        async with PrimClient(api_key="...") as client:
            visits = await client.get_stop_monitoring("STIF:StopPoint:Q:41136:")

    Le client applique automatiquement du retry exponentiel sur les erreurs
    réseau et 5xx, et lève `PrimAPIError` sur les erreurs métier persistantes.
    """

    STOP_MONITORING_PATH = "/stop-monitoring"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://prim.iledefrance-mobilites.fr/marketplace",
        timeout: float = 10.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("Une clé API PRIM est requise")

        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        # Injection possible pour faciliter les tests
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> PrimClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                headers={"apikey": self._api_key, "Accept": "application/json"},
            )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(
            (httpx.TimeoutException, httpx.HTTPStatusError)
        ),
        reraise=True,
    )
    async def _fetch(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        """Appel HTTP bas-niveau avec retry."""
        if self._client is None:
            raise RuntimeError(
                "Client non initialisé. Utilise `async with PrimClient(...)`."
            )

        logger.info("prim_request", extra={"path": path, "params": params})
        response = await self._client.get(path, params=params)

        if response.status_code >= 500:
            # Sera retry par tenacity
            response.raise_for_status()
        if response.status_code >= 400:
            raise PrimAPIError(
                f"PRIM a retourné {response.status_code}: {response.text[:200]}"
            )

        data: dict[str, Any] = response.json()
        return data

    async def get_stop_monitoring(self, stop_id: str) -> list[StopVisit]:
        """Récupère les prochains passages à un arrêt donné.

        Args:
            stop_id: identifiant SIRI de l'arrêt, ex. 'STIF:StopPoint:Q:41136:'

        Returns:
            Liste des prochains passages prévus, triée par horaire croissant.
            Retourne une liste vide si aucun passage n'est annoncé.

        Raises:
            PrimAPIError: en cas d'erreur métier de l'API PRIM.
        """
        params = {"MonitoringRef": stop_id}
        raw = await self._fetch(self.STOP_MONITORING_PATH, params)
        visits = parse_stop_monitoring_response(raw)
        logger.info(
            "prim_response",
            extra={"stop_id": stop_id, "visits_count": len(visits)},
        )
        return visits
