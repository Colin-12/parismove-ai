"""Tests du sub-score pollution."""
from __future__ import annotations

import pytest

from healthscore.pollution import PollutionInputs, score_pollution


class TestPollutionScore:
    def test_excellent_air_returns_high_score(self) -> None:
        # PM2.5 = 3 (excellent), NO2 = 5, AQI = 30
        score = score_pollution(PollutionInputs(pm25=3, no2=5, aqi=30))
        assert score >= 95

    def test_terrible_air_returns_low_score(self) -> None:
        # Smog : PM2.5 = 100, NO2 = 250, AQI = 350
        score = score_pollution(PollutionInputs(pm25=100, no2=250, aqi=350))
        assert score <= 5

    def test_no_data_returns_neutral(self) -> None:
        assert score_pollution(PollutionInputs()) == 50.0

    def test_pm25_dominates_when_alone(self) -> None:
        # Que PM2.5 dispo : son score doit être retourné directement
        score = score_pollution(PollutionInputs(pm25=10))  # 5-15 → 80
        assert score == pytest.approx(80, abs=1)

    def test_intermediate_values(self) -> None:
        # Valeurs intermédiaires Paris typique
        score = score_pollution(PollutionInputs(pm25=15, no2=30, aqi=60))
        # PM25=15 → 60, NO2=30 → 60, AQI=60 → 75
        # Pondéré : 0.5*60 + 0.3*60 + 0.2*75 = 30 + 18 + 15 = 63
        assert 60 <= score <= 70

    def test_partial_data_redistributes_weights(self) -> None:
        # Que PM2.5 et NO2 (pas d'AQI). Les poids 0.5 et 0.3 doivent
        # être renormalisés à 0.625 et 0.375.
        score = score_pollution(PollutionInputs(pm25=10, no2=20))
        # PM25=10 → 80, NO2=20 → 80
        # Renormalisé : (0.5*80 + 0.3*80) / 0.8 = 80
        assert score == pytest.approx(80, abs=1)
