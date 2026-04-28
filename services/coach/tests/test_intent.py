"""Tests du classifieur d'intent."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from coach.intent import IntentResult, IntentType, classify_intent


@pytest.fixture
def mock_llm() -> MagicMock:
    return MagicMock()


class TestIntentResult:
    def test_basic_construction(self) -> None:
        r = IntentResult(IntentType.AIR_QUALITY, "fr")
        assert r.intent == IntentType.AIR_QUALITY
        assert r.language == "fr"


class TestClassifyIntent:
    def test_valid_json_response(self, mock_llm: MagicMock) -> None:
        mock_llm.chat.return_value = '{"intent": "air_quality", "language": "fr"}'
        result = classify_intent("comment est l'air ?", mock_llm)
        assert result.intent == IntentType.AIR_QUALITY
        assert result.language == "fr"

    def test_english_question(self, mock_llm: MagicMock) -> None:
        mock_llm.chat.return_value = '{"intent": "weather", "language": "en"}'
        result = classify_intent("is it raining?", mock_llm)
        assert result.intent == IntentType.WEATHER
        assert result.language == "en"

    def test_response_with_markdown_fence(self, mock_llm: MagicMock) -> None:
        """Le LLM enveloppe parfois la sortie de ```json ... ```."""
        mock_llm.chat.return_value = '```json\n{"intent": "greeting", "language": "fr"}\n```'
        result = classify_intent("salut", mock_llm)
        assert result.intent == IntentType.GREETING

    def test_invalid_json_falls_back_to_general_knowledge(
        self, mock_llm: MagicMock
    ) -> None:
        mock_llm.chat.return_value = "blabla pas json"
        result = classify_intent("question", mock_llm)
        assert result.intent == IntentType.GENERAL_KNOWLEDGE
        assert result.language == "fr"

    def test_unknown_intent_falls_back(self, mock_llm: MagicMock) -> None:
        mock_llm.chat.return_value = '{"intent": "unknown_thing", "language": "fr"}'
        result = classify_intent("question", mock_llm)
        assert result.intent == IntentType.GENERAL_KNOWLEDGE

    def test_invalid_language_defaults_to_french(self, mock_llm: MagicMock) -> None:
        mock_llm.chat.return_value = '{"intent": "weather", "language": "klingon"}'
        result = classify_intent("question", mock_llm)
        assert result.language == "fr"

    def test_uses_temperature_zero_for_classification(
        self, mock_llm: MagicMock
    ) -> None:
        mock_llm.chat.return_value = '{"intent": "greeting", "language": "fr"}'
        classify_intent("salut", mock_llm)
        # On vérifie que la température 0 a bien été passée
        call_kwargs = mock_llm.chat.call_args.kwargs
        assert call_kwargs.get("temperature") == 0.0
