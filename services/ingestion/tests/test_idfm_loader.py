"""Tests du loader référentiel IDFM."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from ingestion.reference.idfm_loader import (
    _build_line_id,
    _normalize_color,
    _record_to_row,
    fetch_idfm_lines,
    upsert_idfm_lines,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def referentiel_response() -> dict:
    with (FIXTURES_DIR / "idfm_referentiel.json").open(encoding="utf-8") as f:
        return json.load(f)


class TestBuildLineId:
    def test_simple_id(self) -> None:
        assert _build_line_id("C01390") == "STIF:Line::C01390:"

    def test_empty_string_returns_none(self) -> None:
        assert _build_line_id("") is None

    def test_none_returns_none(self) -> None:
        assert _build_line_id(None) is None


class TestNormalizeColor:
    def test_uppercases_with_hash(self) -> None:
        assert _normalize_color("7b388c") == "#7B388C"

    def test_strips_existing_hash(self) -> None:
        assert _normalize_color("#FFCD00") == "#FFCD00"

    def test_invalid_length_returns_none(self) -> None:
        assert _normalize_color("ABC") is None

    def test_empty_returns_none(self) -> None:
        assert _normalize_color("") is None

    def test_none_returns_none(self) -> None:
        assert _normalize_color(None) is None


class TestRecordToRow:
    def test_full_record(self) -> None:
        record = {
            "id_line": "C01390",
            "shortname_line": "T2",
            "name_line": "Tramway T2",
            "transportmode": "tram",
            "transportsubmode": None,
            "networkname": "RATP",
            "operatorname": "RATP",
            "colourweb_hexa": "7B388C",
            "textcolourweb_hexa": "FFFFFF",
            "status": "active",
            "accessibility": "yes",
        }
        row = _record_to_row(record)
        assert row is not None
        assert row["line_id"] == "STIF:Line::C01390:"
        assert row["short_name"] == "T2"
        assert row["long_name"] == "Tramway T2"
        assert row["transport_mode"] == "tram"
        assert row["color_web_hex"] == "#7B388C"
        assert row["text_color_hex"] == "#FFFFFF"

    def test_record_without_id_returns_none(self) -> None:
        record = {"id_line": "", "shortname_line": "X"}
        assert _record_to_row(record) is None

    def test_empty_strings_become_none(self) -> None:
        record = {
            "id_line": "C001",
            "shortname_line": "",
            "name_line": "",
            "transportmode": "bus",
        }
        row = _record_to_row(record)
        assert row is not None
        assert row["short_name"] is None
        assert row["long_name"] is None
        assert row["transport_mode"] == "bus"


class TestFetchIdfmLines:
    @pytest.mark.asyncio
    async def test_fetches_single_page(
        self, httpx_mock: HTTPXMock, referentiel_response: dict
    ) -> None:
        url_pattern = re.compile(
            r".*data\.iledefrance-mobilites\.fr.*referentiel-des-lignes.*"
        )
        httpx_mock.add_response(url=url_pattern, json=referentiel_response)

        rows = await fetch_idfm_lines()

        # 4 records mais 1 invalide (id manquant) -> 3 rows utilisables
        assert len(rows) == 3
        line_ids = {r["line_id"] for r in rows}
        assert "STIF:Line::C01390:" in line_ids  # T2
        assert "STIF:Line::C01371:" in line_ids  # M1
        assert "STIF:Line::C01742:" in line_ids  # RER B

    @pytest.mark.asyncio
    async def test_handles_pagination(self, httpx_mock: HTTPXMock) -> None:
        """Si l'API retourne PAGE_SIZE résultats, on demande la page suivante."""
        url_pattern = re.compile(
            r".*data\.iledefrance-mobilites\.fr.*referentiel-des-lignes.*"
        )
        # Page 1 : 100 résultats (page pleine -> on doit redemander)
        page_1 = {
            "results": [
                {"id_line": f"L{i:04d}", "shortname_line": f"L{i}"}
                for i in range(100)
            ]
        }
        # Page 2 : moins de 100 résultats (page non pleine -> stop)
        page_2 = {
            "results": [
                {"id_line": f"L{i:04d}", "shortname_line": f"L{i}"}
                for i in range(100, 105)
            ]
        }
        httpx_mock.add_response(url=url_pattern, json=page_1)
        httpx_mock.add_response(url=url_pattern, json=page_2)

        rows = await fetch_idfm_lines()
        assert len(rows) == 105

    @pytest.mark.asyncio
    async def test_deduplicates_repeated_line_ids(
        self, httpx_mock: HTTPXMock
    ) -> None:
        """Une ligne renvoyée plusieurs fois (ex: sous-modes) ne crée qu'une row."""
        url_pattern = re.compile(
            r".*data\.iledefrance-mobilites\.fr.*referentiel-des-lignes.*"
        )
        page = {
            "results": [
                {"id_line": "C001", "shortname_line": "X", "transportsubmode": "a"},
                {"id_line": "C001", "shortname_line": "X", "transportsubmode": "b"},
                {"id_line": "C002", "shortname_line": "Y", "transportsubmode": "a"},
            ]
        }
        httpx_mock.add_response(url=url_pattern, json=page)
        rows = await fetch_idfm_lines()
        assert len(rows) == 2


class TestUpsertIdfmLines:
    def test_empty_returns_zero_without_connecting(self) -> None:
        # None comme engine : si la fonction essaie d'y aller, elle crashe
        result = upsert_idfm_lines(None, [])  # type: ignore[arg-type]
        assert result == 0
