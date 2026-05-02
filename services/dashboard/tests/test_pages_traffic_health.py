"""Tests structurels pour les pages 3 et 4 du dashboard.

On ne teste pas l'exécution Streamlit (mock complexe), juste que le code
est cohérent et utilise bien les bons imports/fonctions.
"""
from __future__ import annotations

from pathlib import Path

PAGES_DIR = (
    Path(__file__).resolve().parents[1]
    / "src" / "dashboard" / "pages"
)


class TestTraficPage:
    def test_file_exists(self) -> None:
        assert (PAGES_DIR / "3_Trafic.py").exists()

    def test_uses_traffic_kpis(self) -> None:
        content = (PAGES_DIR / "3_Trafic.py").read_text(encoding="utf-8")
        assert "get_traffic_kpis" in content
        assert "get_top_delayed_lines" in content
        assert "get_traffic_heatmap" in content

    def test_has_mode_filter(self) -> None:
        content = (PAGES_DIR / "3_Trafic.py").read_text(encoding="utf-8")
        assert "mode_filter" in content or "selected_mode" in content


class TestScoreSantePage:
    def test_file_exists(self) -> None:
        assert (PAGES_DIR / "4_Score_sante.py").exists()

    def test_uses_score_journey(self) -> None:
        content = (PAGES_DIR / "4_Score_sante.py").read_text(encoding="utf-8")
        assert "from healthscore.compare import score_journey" in content

    def test_uses_predefined_zones(self) -> None:
        content = (PAGES_DIR / "4_Score_sante.py").read_text(encoding="utf-8")
        assert "PREDEFINED_ZONES" in content

    def test_has_folium_map(self) -> None:
        content = (PAGES_DIR / "4_Score_sante.py").read_text(encoding="utf-8")
        assert "import folium" in content
        assert "_build_journey_map" in content

    def test_advice_by_grade_complete(self) -> None:
        content = (PAGES_DIR / "4_Score_sante.py").read_text(encoding="utf-8")
        # Vérifie que les 5 grades A-E sont couverts
        assert '"A":' in content
        assert '"B":' in content
        assert '"C":' in content
        assert '"D":' in content
        assert '"E":' in content


class TestDataHelpers:
    def test_predefined_zones_count(self) -> None:
        from dashboard.data import PREDEFINED_ZONES

        assert len(PREDEFINED_ZONES) >= 8, "Au moins 8 zones IDF prédéfinies"
        assert "Châtelet (Paris 1er)" in PREDEFINED_ZONES
        assert "La Défense" in PREDEFINED_ZONES

    def test_predefined_zones_coords_in_idf(self) -> None:
        """Toutes les zones doivent être en IDF (lat 48-49, lon 1.5-3)."""
        from dashboard.data import PREDEFINED_ZONES

        for name, (lat, lon) in PREDEFINED_ZONES.items():
            assert 48.5 < lat < 49.2, f"{name} : latitude {lat} hors IDF"
            assert 1.5 < lon < 3.0, f"{name} : longitude {lon} hors IDF"

    def test_format_delay_helper(self) -> None:
        from dashboard.data import format_delay

        assert format_delay(0) == "0s"
        assert format_delay(30) == "+30s"
        assert format_delay(-15) == "-15s"
        assert format_delay(75) == "+1m 15s"
        assert format_delay(-90) == "-1m 30s"

    def test_grade_color_helper(self) -> None:
        from dashboard.data import grade_color

        assert grade_color("A") == "#10B981"
        assert grade_color("E") == "#EF4444"
        assert grade_color("X") == "#9CA3AF"  # fallback
