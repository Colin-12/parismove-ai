"""Client HTTP pour Open-Meteo.

Documentation officielle :
    https://open-meteo.com/en/docs

Authentification : aucune (gratuit pour usage non-commercial).
Quota : 10 000 requêtes/jour. À 10 points x 48 runs x 2 endpoints =
960 requêtes/jour, soit moins de 10% du quota.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx
from shared.schemas import WeatherObservation
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ingestion.transformers.meteo_transformer import parse_observation

logger = logging.getLogger(__name__)


class OpenMeteoAPIError(Exception):
    """Erreur retournée par Open-Meteo."""


class OpenMeteoClient:
    """Client pour Open-Meteo (météo + qualité de l'air modélisée).

    Usage:
        async with OpenMeteoClient() as client:
            obs = await client.get_observation(48.8566, 2.3522, "paris-centre", "Paris")
    """

    FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
    AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

    # Variables météo à demander dans le bloc "current"
    _FORECAST_CURRENT_VARS = (
        "temperature_2m,relative_humidity_2m,apparent_temperature,is_day,"
        "precipitation,rain,showers,snowfall,weather_code,cloud_cover,"
        "pressure_msl,surface_pressure,wind_speed_10m,wind_direction_10m,"
        "wind_gusts_10m,visibility"
    )

    # Variables qualité de l'air et pollens
    _AIR_QUALITY_CURRENT_VARS = (
        "european_aqi,pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,"
        "sulphur_dioxide,ozone,uv_index,alder_pollen,birch_pollen,"
        "grass_pollen,ragweed_pollen"
    )

    def __init__(
        self,
        timeout: float = 10.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._timeout = timeout
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> OpenMeteoClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
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
    async def _fetch(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError(
                "Client non initialisé. Utilise `async with OpenMeteoClient(...)`."
            )

        logger.info("openmeteo_request", extra={"url": url})
        response = await self._client.get(url, params=params)

        if response.status_code >= 500:
            response.raise_for_status()
        if response.status_code >= 400:
            raise OpenMeteoAPIError(
                f"Open-Meteo a retourné {response.status_code}: "
                f"{response.text[:200]}"
            )

        data: dict[str, Any] = response.json()
        return data

    async def get_observation(
        self,
        latitude: float,
        longitude: float,
        point_id: str,
        point_name: str,
    ) -> WeatherObservation | None:
        """Récupère l'observation courante (météo + air) à un point GPS.

        Effectue 2 appels en parallèle (forecast + air-quality) puis combine
        les résultats. Si /air-quality échoue, on retourne quand même
        l'observation avec les champs air à None.

        Returns:
            WeatherObservation, ou None si la donnée météo est inexploitable.
        """
        forecast_params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": self._FORECAST_CURRENT_VARS,
            "timezone": "auto",
        }
        air_quality_params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": self._AIR_QUALITY_CURRENT_VARS,
            "timezone": "auto",
        }

        # Météo : appel obligatoire
        forecast_data = await self._fetch(self.FORECAST_URL, forecast_params)

        # Air quality : si ça plante, on continue avec air = None
        air_quality_data: dict[str, Any] | None = None
        try:
            air_quality_data = await self._fetch(
                self.AIR_QUALITY_URL, air_quality_params
            )
        except (OpenMeteoAPIError, httpx.HTTPError) as exc:
            logger.warning(
                "openmeteo_air_quality_failed",
                extra={"point_id": point_id, "error": str(exc)},
            )

        observation = parse_observation(
            forecast_data, air_quality_data, point_id, point_name
        )
        if observation is not None:
            logger.info(
                "openmeteo_response",
                extra={
                    "point_id": point_id,
                    "temperature": observation.temperature_c,
                },
            )
        return observation
