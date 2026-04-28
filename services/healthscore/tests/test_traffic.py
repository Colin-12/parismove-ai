"""Tests du sub-score trafic."""
from __future__ import annotations

import pytest

from healthscore.traffic import TrafficInputs, score_traffic


class TestTrafficScore:
    def test_no_delays_returns_high_score(self) -> None:
        # Trafic ponctuel : retard moyen <30s
        score = score_traffic(
            TrafficInputs(avg_delay_seconds=10, sample_count=100)
        )
        assert score == 100

    def test_chaos_returns_zero(self) -> None:
        # Retard moyen >10 min
        score = score_traffic(
            TrafficInputs(avg_delay_seconds=700, sample_count=100)
        )
        assert score == 0

    def test_no_data_returns_neutral(self) -> None:
        assert score_traffic(TrafficInputs()) == 50.0

    def test_zero_samples_returns_neutral(self) -> None:
        score = score_traffic(
            TrafficInputs(avg_delay_seconds=10, sample_count=0)
        )
        assert score == 50.0

    def test_small_sample_dampens_score(self) -> None:
        """Avec peu d'échantillons, le score est tiré vers 50 (neutre)."""
        # Excellent retard MAIS 2 échantillons seulement
        score = score_traffic(
            TrafficInputs(avg_delay_seconds=10, sample_count=2)
        )
        # confidence = 2/5 = 0.4 ; raw = 100
        # score = 100*0.4 + 50*0.6 = 70
        assert score == pytest.approx(70, abs=1)

    def test_large_sample_returns_full_score(self) -> None:
        score = score_traffic(
            TrafficInputs(avg_delay_seconds=10, sample_count=50)
        )
        assert score == 100

    @pytest.mark.parametrize(
        "delay,expected_min,expected_max",
        [
            (15, 95, 100),    # excellent
            (45, 85, 95),     # bon
            (90, 65, 75),     # acceptable
            (180, 35, 45),    # médiocre
            (500, 10, 20),    # mauvais
        ],
    )
    def test_thresholds(
        self, delay: float, expected_min: float, expected_max: float
    ) -> None:
        score = score_traffic(
            TrafficInputs(avg_delay_seconds=delay, sample_count=100)
        )
        assert expected_min <= score <= expected_max
