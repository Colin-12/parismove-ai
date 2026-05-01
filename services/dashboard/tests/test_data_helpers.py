"""Tests des helpers data.py (sans dépendance à la BDD)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from dashboard.data import aqi_color, aqi_label, format_age


class TestAqiColor:
    @pytest.mark.parametrize(
        "aqi,expected_color",
        [
            (None, "#9CA3AF"),
            (0, "#10B981"),
            (50, "#10B981"),
            (51, "#F59E0B"),
            (100, "#F59E0B"),
            (101, "#F97316"),
            (150, "#F97316"),
            (151, "#EF4444"),
            (200, "#EF4444"),
            (201, "#A855F7"),
            (300, "#A855F7"),
            (301, "#7C2D12"),
            (500, "#7C2D12"),
        ],
    )
    def test_thresholds(self, aqi: int | None, expected_color: str) -> None:
        assert aqi_color(aqi) == expected_color


class TestAqiLabel:
    @pytest.mark.parametrize(
        "aqi,expected",
        [
            (None, "?"),
            (25, "Bon"),
            (75, "Modéré"),
            (125, "Mauvais (sensibles)"),
            (175, "Mauvais"),
            (250, "Très mauvais"),
            (400, "Dangereux"),
        ],
    )
    def test_labels(self, aqi: int | None, expected: str) -> None:
        assert aqi_label(aqi) == expected


class TestFormatAge:
    def test_none(self) -> None:
        assert format_age(None) == "?"

    def test_just_now(self) -> None:
        when = datetime.now(UTC) - timedelta(seconds=10)
        assert format_age(when) == "à l'instant"

    def test_minutes(self) -> None:
        when = datetime.now(UTC) - timedelta(minutes=5)
        result = format_age(when)
        assert "min" in result
        # On ne vérifie pas le chiffre exact car il y a un offset de quelques
        # secondes entre le `now` du test et celui de format_age

    def test_hours(self) -> None:
        when = datetime.now(UTC) - timedelta(hours=3)
        result = format_age(when)
        assert "h" in result and "min" not in result

    def test_days(self) -> None:
        when = datetime.now(UTC) - timedelta(days=2)
        result = format_age(when)
        assert "j" in result
