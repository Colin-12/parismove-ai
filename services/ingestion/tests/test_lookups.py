"""Tests du module LineLookup."""
from __future__ import annotations

import pytest
from shared.db.lookups import LineInfo, LineLookup


@pytest.fixture
def lookup() -> LineLookup:
    return LineLookup(
        by_line_id={
            "STIF:Line::C01390:": LineInfo(
                line_id="STIF:Line::C01390:",
                short_name="T2",
                long_name="Tramway T2",
                transport_mode="tram",
                network_name="RATP",
                operator_name="RATP",
                color_web_hex="#7B388C",
                text_color_hex="#FFFFFF",
            ),
            "STIF:Line::C01742:": LineInfo(
                line_id="STIF:Line::C01742:",
                short_name="RER B",
                long_name="RER B",
                transport_mode="rail",
                network_name="RATP",
                operator_name="RATP / SNCF",
                color_web_hex="#4A90E2",
                text_color_hex="#FFFFFF",
            ),
            # Ligne sans short_name (cas dégradé)
            "STIF:Line::C99999:": LineInfo(
                line_id="STIF:Line::C99999:",
                short_name=None,
                long_name="Ligne expérimentale",
                transport_mode="bus",
                network_name=None,
                operator_name=None,
                color_web_hex=None,
                text_color_hex=None,
            ),
        }
    )


class TestGet:
    def test_known_line(self, lookup: LineLookup) -> None:
        info = lookup.get("STIF:Line::C01390:")
        assert info is not None
        assert info.short_name == "T2"

    def test_unknown_line_returns_none(self, lookup: LineLookup) -> None:
        assert lookup.get("STIF:Line::UNKNOWN:") is None


class TestShortName:
    def test_known(self, lookup: LineLookup) -> None:
        assert lookup.short_name("STIF:Line::C01390:") == "T2"

    def test_unknown(self, lookup: LineLookup) -> None:
        assert lookup.short_name("STIF:Line::XXX:") is None


class TestDisplayName:
    def test_uses_short_name_when_available(self, lookup: LineLookup) -> None:
        assert lookup.display_name("STIF:Line::C01390:") == "T2"

    def test_falls_back_to_long_name(self, lookup: LineLookup) -> None:
        # C99999 a long_name mais pas short_name
        assert lookup.display_name("STIF:Line::C99999:") == "Ligne expérimentale"

    def test_falls_back_to_extracted_code(self, lookup: LineLookup) -> None:
        """Si la ligne est inconnue, on extrait le code court du line_id."""
        assert lookup.display_name("STIF:Line::C12345:") == "C12345"

    def test_handles_malformed_line_id(self, lookup: LineLookup) -> None:
        assert lookup.display_name("weird") == "weird"


class TestColor:
    def test_known(self, lookup: LineLookup) -> None:
        assert lookup.color("STIF:Line::C01390:") == "#7B388C"

    def test_unknown(self, lookup: LineLookup) -> None:
        assert lookup.color("STIF:Line::XXX:") is None


class TestTransportMode:
    def test_known(self, lookup: LineLookup) -> None:
        assert lookup.transport_mode("STIF:Line::C01390:") == "tram"
        assert lookup.transport_mode("STIF:Line::C01742:") == "rail"


class TestContainerProtocol:
    def test_len(self, lookup: LineLookup) -> None:
        assert len(lookup) == 3

    def test_contains_known(self, lookup: LineLookup) -> None:
        assert "STIF:Line::C01390:" in lookup

    def test_contains_unknown(self, lookup: LineLookup) -> None:
        assert "STIF:Line::XXX:" not in lookup
