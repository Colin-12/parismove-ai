"""Test minimaliste pour la page Coach IA.

Vérifie que la liste de SUGGESTIONS est cohérente.
On ne teste pas la page entière car elle dépend de Streamlit
runtime qui est complexe à mocker.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_coach_page_module() -> object:
    """Charge dynamiquement le module page malgré son nom non-importable."""
    page_path = (
        Path(__file__).resolve().parents[1]
        / "src" / "dashboard" / "pages" / "2_Coach_IA.py"
    )
    spec = importlib.util.spec_from_file_location("coach_ia_page", page_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    return module  # on ne charge pas — Streamlit n'est pas dispo en test


class TestSuggestionsStructure:
    """Vérifie le contenu du fichier — pas l'exécution."""

    def test_file_exists(self) -> None:
        page_path = (
            Path(__file__).resolve().parents[1]
            / "src" / "dashboard" / "pages" / "2_Coach_IA.py"
        )
        assert page_path.exists(), f"Fichier manquant : {page_path}"

    def test_has_suggestions_constant(self) -> None:
        page_path = (
            Path(__file__).resolve().parents[1]
            / "src" / "dashboard" / "pages" / "2_Coach_IA.py"
        )
        content = page_path.read_text(encoding="utf-8")
        assert "SUGGESTIONS = [" in content
        assert "Comment est l'air" in content

    def test_uses_coach_orchestrator(self) -> None:
        page_path = (
            Path(__file__).resolve().parents[1]
            / "src" / "dashboard" / "pages" / "2_Coach_IA.py"
        )
        content = page_path.read_text(encoding="utf-8")
        assert "from coach.orchestrator import Coach" in content
        assert "from coach.llm import LLMClient" in content
