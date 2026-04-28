"""Tests du module exposure (calcul de proximité)."""
from __future__ import annotations

import pytest

from healthscore.exposure import (
    GeoPoint,
    find_nearest,
    find_within_radius,
    haversine_km,
)


class TestHaversine:
    def test_same_point_zero_distance(self) -> None:
        assert haversine_km(48.85, 2.35, 48.85, 2.35) == pytest.approx(0)

    def test_paris_versailles_about_17km(self) -> None:
        # Paris centre ~48.85, 2.35 ; Versailles ~48.80, 2.13
        d = haversine_km(48.8566, 2.3522, 48.8044, 2.1232)
        # Distance réelle ~17 km
        assert 16 <= d <= 18

    def test_paris_lyon_about_390km(self) -> None:
        # Sanity check sur grande distance
        d = haversine_km(48.8566, 2.3522, 45.7640, 4.8357)
        assert 380 <= d <= 400

    def test_symmetric(self) -> None:
        d1 = haversine_km(48.85, 2.35, 48.90, 2.40)
        d2 = haversine_km(48.90, 2.40, 48.85, 2.35)
        assert d1 == pytest.approx(d2)


class TestFindNearest:
    def test_returns_closest(self) -> None:
        candidates = [
            GeoPoint("far", 48.0, 2.0),
            GeoPoint("close", 48.85, 2.35),
            GeoPoint("medium", 48.5, 2.2),
        ]
        result = find_nearest(48.86, 2.36, candidates)
        assert result is not None
        point, _ = result
        assert point.point_id == "close"

    def test_empty_candidates(self) -> None:
        assert find_nearest(48.85, 2.35, []) is None


class TestFindWithinRadius:
    def test_filters_by_radius(self) -> None:
        candidates = [
            GeoPoint("a", 48.85, 2.35),  # même point
            GeoPoint("b", 48.86, 2.36),  # ~1.4 km
            GeoPoint("c", 48.95, 2.50),  # ~15 km
        ]
        result = find_within_radius(48.85, 2.35, candidates, radius_km=5.0)
        ids = [p.point_id for p, _ in result]
        assert ids == ["a", "b"]

    def test_sorted_by_distance(self) -> None:
        candidates = [
            GeoPoint("medium", 48.86, 2.36),
            GeoPoint("close", 48.851, 2.351),
            GeoPoint("close-bis", 48.852, 2.352),
        ]
        result = find_within_radius(48.85, 2.35, candidates, radius_km=10)
        distances = [d for _, d in result]
        assert distances == sorted(distances)
