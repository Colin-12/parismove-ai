"""Tests du module scoring (agrégation + grade A-E)."""
from __future__ import annotations

import pytest
from shared.schemas import HealthGrade

from healthscore.scoring import (
    DEFAULT_WEIGHTS,
    aggregate_scores,
    grade_color,
    score_to_grade,
)


class TestAggregateScores:
    def test_default_weights_pollution_dominates(self) -> None:
        # Pollution=100, météo=0, trafic=0 → 60% du total = 60
        score = aggregate_scores(100, 0, 0)
        assert score == pytest.approx(60)

    def test_all_perfect(self) -> None:
        assert aggregate_scores(100, 100, 100) == 100

    def test_all_zero(self) -> None:
        assert aggregate_scores(0, 0, 0) == 0

    def test_default_weights_sum_to_one(self) -> None:
        assert sum(DEFAULT_WEIGHTS.values()) == pytest.approx(1.0)

    def test_custom_weights(self) -> None:
        custom = {"pollution": 1.0, "weather": 0.0, "traffic": 0.0}
        score = aggregate_scores(80, 0, 0, weights=custom)
        assert score == 80


class TestScoreToGrade:
    @pytest.mark.parametrize(
        "score,expected_grade",
        [
            (100, HealthGrade.A),
            (90, HealthGrade.A),
            (80, HealthGrade.A),
            (79, HealthGrade.B),
            (70, HealthGrade.B),
            (65, HealthGrade.B),
            (64, HealthGrade.C),
            (55, HealthGrade.C),
            (50, HealthGrade.C),
            (49, HealthGrade.D),
            (40, HealthGrade.D),
            (35, HealthGrade.D),
            (34, HealthGrade.E),
            (10, HealthGrade.E),
            (0, HealthGrade.E),
        ],
    )
    def test_thresholds(self, score: float, expected_grade: HealthGrade) -> None:
        assert score_to_grade(score) == expected_grade


class TestGradeColor:
    def test_all_grades_have_color(self) -> None:
        for grade in HealthGrade:
            color = grade_color(grade)
            assert color.startswith("#")
            assert len(color) == 7

    def test_a_is_green_e_is_red(self) -> None:
        # On vérifie le sens : A vert, E rouge
        assert "1B7E3D" in grade_color(HealthGrade.A)
        assert "E40520" in grade_color(HealthGrade.E)
