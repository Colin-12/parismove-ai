"""Client HTTP pour l'API AQICN (World Air Quality Index project).

Documentation officielle :
    https://aqicn.org/api/

Authentification : token unique passé en paramètre de query `token=...`.
Quota gratuit : 1000 requêtes/jour.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx
from shared.schemas import AirMeasurement
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ingestion.transformers.aqicn_transformer import parse_station_response

logger = logging.getLogger(__name__)


class AqicnAPIError(Exception):
    """Erreur retournée par l'API AQICN."""


class AqicnClient:
    """Client pour l'API AQICN "feed" (mesure unitaire par station).

    Usage:
        async with AqicnClient(token="abc123") as client:
            measurement = await client.get_station("@5722")  # Paris 18

    Identifiants supportés : slug ('paris') ou ID numérique avec @ ('@5722').
    """

    BASE_URL = "https://api.waqi.info"

    def __init__(
        self,
        token: str,
        timeout: float = 10.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not token:
            raise ValueError("Un token AQICN est requis")

        self._token = token
        self._timeout = timeout
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> AqicnClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                timeout=self._timeout,
                headers={"Accept": "application/json"},
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
    async def _fetch(self, path: str) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError(
                "Client non initialisé. Utilise `async with AqicnClient(...)`."
            )

        params = {"token": self._token}
        logger.info("aqicn_request", extra={"path": path})
        response = await self._client.get(path, params=params)

        if response.status_code >= 500:
            response.raise_for_status()
        if response.status_code >= 400:
            raise AqicnAPIError(
                f"AQICN a retourné {response.status_code}: {response.text[:200]}"
            )

        data: dict[str, Any] = response.json()

        # AQICN renvoie 200 OK même quand la requête échoue, avec un champ
        # `status` à 'error'. On vérifie explicitement.
        if data.get("status") != "ok":
            raise AqicnAPIError(
                f"AQICN status={data.get('status')}: {data.get('data', '')}"
            )

        return data

    async def get_station(self, station_id: str) -> AirMeasurement | None:
        """Récupère la dernière mesure d'une station.

        Args:
            station_id: identifiant AQICN, ex. '@5722' ou 'paris'.

        Returns:
            AirMeasurement, ou None si la donnée n'est pas exploitable.
        """
        path = f"/feed/{station_id}/"
        raw = await self._fetch(path)
        measurement = parse_station_response(raw)
        if measurement is not None:
            logger.info(
                "aqicn_response",
                extra={"station_id": station_id, "aqi": measurement.aqi},
            )
        return measurement
