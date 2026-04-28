"""Tests du client Open-Meteo avec mock HTTP."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from ingestion.clients.meteo import OpenMeteoAPIError, OpenMeteoClient

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def forecast_response() -> dict:
    with (FIXTURES_DIR / "openmeteo_forecast.json").open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def air_quality_response() -> dict:
    with (FIXTURES_DIR / "openmeteo_air_quality.json").open(encoding="utf-8") as f:
        return json.load(f)


# Regex pour matcher chaque endpoint indépendamment des query params
FORECAST_URL_PATTERN = re.compile(r"https://api\.open-meteo\.com/v1/forecast.*")
AIR_QUALITY_URL_PATTERN = re.compile(
    r"https://air-quality-api\.open-meteo\.com/v1/air-quality.*"
)


class TestGetObservation:
    @pytest.mark.asyncio
    async def test_happy_path(
        self,
        httpx_mock: HTTPXMock,
        forecast_response: dict,
        air_quality_response: dict,
    ) -> None:
        httpx_mock.add_response(
            url=FORECAST_URL_PATTERN, json=forecast_response
        )
        httpx_mock.add_response(
            url=AIR_QUALITY_URL_PATTERN, json=air_quality_response
        )

        async with OpenMeteoClient() as client:
            obs = await client.get_observation(48.85, 2.35, "paris", "Paris")

        assert obs is not None
        assert obs.temperature_c == 14.5
        assert obs.aqi_european == 2

    @pytest.mark.asyncio
    async def test_air_quality_failure_does_not_block(
        self, httpx_mock: HTTPXMock, forecast_response: dict
    ) -> None:
        """Si /air-quality plante, l'observation météo reste utilisable."""
        httpx_mock.add_response(
            url=FORECAST_URL_PATTERN, json=forecast_response
        )
        # 3 réponses 503 pour épuiser les retries de tenacity
        for _ in range(3):
            httpx_mock.add_response(
                url=AIR_QUALITY_URL_PATTERN, status_code=503
            )

        async with OpenMeteoClient() as client:
            obs = await client.get_observation(48.85, 2.35, "paris", "Paris")

        assert obs is not None
        assert obs.temperature_c == 14.5
        # Champs air doivent être None puisque l'appel a échoué
        assert obs.aqi_european is None
        assert obs.pm25 is None

    @pytest.mark.asyncio
    async def test_forecast_4xx_raises(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url=FORECAST_URL_PATTERN, status_code=400, text="Bad Request"
        )

        async with OpenMeteoClient() as client:
            with pytest.raises(OpenMeteoAPIError, match="400"):
                await client.get_observation(48.85, 2.35, "paris", "Paris")
