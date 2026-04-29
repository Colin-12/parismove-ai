"""Tests de l'orchestrateur Coach (avec LLM mocké)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy import Engine

from coach.intent import IntentType
from coach.orchestrator import Coach


@pytest.fixture
def mock_engine() -> MagicMock:
    return MagicMock(spec=Engine)


@pytest.fixture
def mock_llm() -> MagicMock:
    return MagicMock()


class TestExtractZone:
    def test_paris(self, mock_engine: MagicMock, mock_llm: MagicMock) -> None:
        coach = Coach(mock_engine, mock_llm)
        assert coach._extract_zone("comment est l'air à Paris ?") == "paris"

    def test_la_defense(self, mock_engine: MagicMock, mock_llm: MagicMock) -> None:
        coach = Coach(mock_engine, mock_llm)
        assert coach._extract_zone("la pollution à la défense") == "défense"

    def test_unknown_zone(self, mock_engine: MagicMock, mock_llm: MagicMock) -> None:
        coach = Coach(mock_engine, mock_llm)
        assert coach._extract_zone("comment ça va ?") is None


class TestExtractLine:
    def test_rer_a(self, mock_engine: MagicMock, mock_llm: MagicMock) -> None:
        coach = Coach(mock_engine, mock_llm)
        assert coach._extract_line("comment est le RER A ?") == "RER A"

    def test_rer_with_space_and_lowercase(
        self, mock_engine: MagicMock, mock_llm: MagicMock
    ) -> None:
        coach = Coach(mock_engine, mock_llm)
        assert coach._extract_line("le rer b est il en retard ?") == "RER B"

    def test_tram(self, mock_engine: MagicMock, mock_llm: MagicMock) -> None:
        coach = Coach(mock_engine, mock_llm)
        assert coach._extract_line("la T2 marche bien ?") == "T2"

    def test_metro_with_keyword(
        self, mock_engine: MagicMock, mock_llm: MagicMock
    ) -> None:
        coach = Coach(mock_engine, mock_llm)
        assert coach._extract_line("comment va le métro 1 ?") == "1"
        assert coach._extract_line("la ligne 14 est en panne ?") == "14"

    def test_no_line(self, mock_engine: MagicMock, mock_llm: MagicMock) -> None:
        coach = Coach(mock_engine, mock_llm)
        assert coach._extract_line("comment ça va ?") is None


class TestGatherContext:
    """Vérifie que selon l'intent, les bons tools sont appelés."""

    def test_greeting_returns_no_context(
        self, mock_engine: MagicMock, mock_llm: MagicMock
    ) -> None:
        from coach.intent import IntentResult

        coach = Coach(mock_engine, mock_llm)
        intent = IntentResult(IntentType.GREETING, "fr")
        contexts, tools = coach._gather_context("salut", intent)
        assert contexts == []
        assert tools == []

    def test_help_calls_list_capabilities(
        self, mock_engine: MagicMock, mock_llm: MagicMock
    ) -> None:
        from coach.intent import IntentResult

        coach = Coach(mock_engine, mock_llm)
        intent = IntentResult(IntentType.HELP, "fr")
        contexts, tools = coach._gather_context("aide", intent)
        assert "list_capabilities" in tools
        assert any("[DATA]" in c for c in contexts)

    def test_general_knowledge_no_tools(
        self, mock_engine: MagicMock, mock_llm: MagicMock
    ) -> None:
        from coach.intent import IntentResult

        coach = Coach(mock_engine, mock_llm)
        intent = IntentResult(IntentType.GENERAL_KNOWLEDGE, "fr")
        contexts, tools = coach._gather_context(
            "qui est président ?", intent
        )
        # Pas de tools car on bascule en mode "connaissance générale"
        assert contexts == []
        assert tools == []
