"""Tests du client PRIM avec mock HTTP.

Utilise pytest-httpx pour intercepter les appels et retourner des réponses
simulées. Aucun trafic réseau réel pendant les tests.
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from pytest_httpx import HTTPXMock

from ingestion.clients.prim import PrimAPIError, PrimClient

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_response() -> dict:
    with (FIXTURES_DIR / "prim_stop_monitoring.json").open() as f:
        return json.load(f)


class TestPrimClientInit:
    def test_empty_api_key_raises(self) -> None:
        with pytest.raises(ValueError, match="clé API"):
            PrimClient(api_key="")


class TestGetStopMonitoring:
    @pytest.mark.asyncio
    async def test_happy_path(
        self, httpx_mock: HTTPXMock, fixture_response: dict
    ) -> None:
        httpx_mock.add_response(
            url="https://prim.iledefrance-mobilites.fr/marketplace/stop-monitoring?MonitoringRef=STIF:StopPoint:Q:41136:",
            json=fixture_response,
        )

        async with PrimClient(api_key="test-key") as client:
            visits = await client.get_stop_monitoring("STIF:StopPoint:Q:41136:")

        assert len(visits) == 5
        assert visits[0].stop_id == "STIF:StopPoint:Q:41136:"

    @pytest.mark.asyncio
    async def test_api_key_is_sent_as_header(
        self, httpx_mock: HTTPXMock, fixture_response: dict
    ) -> None:
        httpx_mock.add_response(
            match_headers={"apikey": "my-secret-key"},
            json=fixture_response,
        )

        async with PrimClient(api_key="my-secret-key") as client:
            await client.get_stop_monitoring("STIF:StopPoint:Q:1:")

    @pytest.mark.asyncio
    async def test_4xx_raises_prim_api_error(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=401, text="Unauthorized")

        async with PrimClient(api_key="bad-key") as client:
            with pytest.raises(PrimAPIError, match="401"):
                await client.get_stop_monitoring("STIF:StopPoint:Q:1:")

    @pytest.mark.asyncio
    async def test_5xx_triggers_retry_then_raises(
        self, httpx_mock: HTTPXMock
    ) -> None:
        # 3 réponses 500 consécutives → tenacity abandonne après 3 tentatives
        for _ in range(3):
            httpx_mock.add_response(status_code=500, text="Server error")

        async with PrimClient(api_key="test-key") as client:
            with pytest.raises(httpx.HTTPStatusError):
                await client.get_stop_monitoring("STIF:StopPoint:Q:1:")

    @pytest.mark.asyncio
    async def test_5xx_then_success_recovers(
        self, httpx_mock: HTTPXMock, fixture_response: dict
    ) -> None:
        httpx_mock.add_response(status_code=503)
        httpx_mock.add_response(json=fixture_response)

        async with PrimClient(api_key="test-key") as client:
            visits = await client.get_stop_monitoring("STIF:StopPoint:Q:1:")

        assert len(visits) == 5
