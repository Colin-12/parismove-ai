"""Tests du client AQICN avec mock HTTP."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from ingestion.clients.aqicn import AqicnAPIError, AqicnClient

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_response() -> dict:
    with (FIXTURES_DIR / "aqicn_paris.json").open(encoding="utf-8") as f:
        return json.load(f)


class TestAqicnClientInit:
    def test_empty_token_raises(self) -> None:
        with pytest.raises(ValueError, match="token"):
            AqicnClient(token="")


class TestGetStation:
    @pytest.mark.asyncio
    async def test_happy_path(
        self, httpx_mock: HTTPXMock, fixture_response: dict
    ) -> None:
        httpx_mock.add_response(
            url="https://api.waqi.info/feed/@5722/?token=test-token",
            json=fixture_response,
        )

        async with AqicnClient(token="test-token") as client:
            measurement = await client.get_station("@5722")

        assert measurement is not None
        assert measurement.aqi == 42
        assert measurement.station_id == "@5722"

    @pytest.mark.asyncio
    async def test_token_is_sent_as_query_param(
        self, httpx_mock: HTTPXMock, fixture_response: dict
    ) -> None:
        httpx_mock.add_response(
            url="https://api.waqi.info/feed/paris/?token=my-secret",
            json=fixture_response,
        )

        async with AqicnClient(token="my-secret") as client:
            await client.get_station("paris")

    @pytest.mark.asyncio
    async def test_status_error_raises(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            json={"status": "error", "data": "Unknown station"}
        )

        async with AqicnClient(token="test-token") as client:
            with pytest.raises(AqicnAPIError, match="error"):
                await client.get_station("invalid-station")

    @pytest.mark.asyncio
    async def test_4xx_raises_aqicn_api_error(
        self, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(status_code=403, text="Forbidden")

        async with AqicnClient(token="bad-token") as client:
            with pytest.raises(AqicnAPIError, match="403"):
                await client.get_station("@5722")

    @pytest.mark.asyncio
    async def test_5xx_then_success_recovers(
        self, httpx_mock: HTTPXMock, fixture_response: dict
    ) -> None:
        httpx_mock.add_response(status_code=503)
        httpx_mock.add_response(json=fixture_response)

        async with AqicnClient(token="test-token") as client:
            measurement = await client.get_station("@5722")

        assert measurement is not None
        assert measurement.aqi == 42

    @pytest.mark.asyncio
    async def test_returns_none_for_unparseable_response(
        self, httpx_mock: HTTPXMock
    ) -> None:
        """Réponse 'ok' mais sans données exploitables -> None, pas de crash."""
        httpx_mock.add_response(
            json={
                "status": "ok",
                "data": {"idx": 1, "city": {"name": "X"}},  # pas de geo, pas de time
            }
        )

        async with AqicnClient(token="test-token") as client:
            measurement = await client.get_station("@1")

        assert measurement is None
