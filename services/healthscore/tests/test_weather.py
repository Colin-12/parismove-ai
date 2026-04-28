"""Tests du sub-score météo."""
from __future__ import annotations

import pytest

from healthscore.weather import WeatherInputs, score_weather


class TestWeatherScore:
    def test_perfect_weather_returns_100(self) -> None:
        # 20°C, pas de pluie, vent calme, UV faible
        score = score_weather(
            WeatherInputs(
                temperature_c=20.0,
                precipitation_mm=0,
                wind_speed_ms=2,
                uv_index=2,
            )
        )
        assert score == pytest.approx(100, abs=1)

    def test_cold_decreases_score(self) -> None:
        # -5°C : 23°C en dessous du confort, devrait scorer bas
        score = score_weather(WeatherInputs(temperature_c=-5))
        assert score < 40

    def test_hot_decreases_score(self) -> None:
        # 38°C : 16°C au-dessus du confort
        score = score_weather(WeatherInputs(temperature_c=38))
        assert score < 40

    def test_heavy_rain_decreases_score(self) -> None:
        score = score_weather(
            WeatherInputs(temperature_c=20, precipitation_mm=15)
        )
        # Précipitations >10mm → 0 sur 30%
        # Température 20 → 100 sur 35%
        # Pas d'autre, renormalisation
        # (0.35*100 + 0.30*0) / 0.65 ≈ 53.8
        assert 50 <= score <= 60

    def test_storm_low_score(self) -> None:
        score = score_weather(
            WeatherInputs(
                temperature_c=10, precipitation_mm=20,
                wind_speed_ms=20, uv_index=1,
            )
        )
        # Tempête + froid → score bas
        assert score < 40

    def test_no_data_returns_neutral(self) -> None:
        assert score_weather(WeatherInputs()) == 50.0

    def test_high_uv_decreases_score(self) -> None:
        score_low_uv = score_weather(
            WeatherInputs(temperature_c=20, uv_index=2)
        )
        score_high_uv = score_weather(
            WeatherInputs(temperature_c=20, uv_index=10)
        )
        assert score_high_uv < score_low_uv
