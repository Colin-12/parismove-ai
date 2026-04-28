"""Sub-score météo : confort thermique, précipitations, vent, UV.

Logique :
    * Température : optimal 18-22°C, dégrade au-dessus/en dessous
    * Précipitations : aucune = 100, intense = 0
    * Vent : optimal <5m/s, dangereux >15m/s (rafales gênantes)
    * UV : <3 = bon, >8 = mauvais (recommandation OMS)
    * Le score météo global est la moyenne pondérée :
        - Température : 35%
        - Précipitations : 30%
        - Vent : 20%
        - UV : 15%
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WeatherInputs:
    """Mesures brutes utilisées pour calculer le sub-score météo."""

    temperature_c: float | None = None
    precipitation_mm: float | None = None
    wind_speed_ms: float | None = None
    uv_index: float | None = None


def _temperature_score(temp_c: float) -> float:
    """Score thermique : optimal 18-22°C, dégradation symétrique.

    -10°C ou +35°C → score très bas
    18-22°C        → 100 (zone de confort)
    """
    if 18 <= temp_c <= 22:
        return 100.0
    # Distance au confort optimal
    if temp_c < 18:
        diff = 18 - temp_c
    else:
        diff = temp_c - 22

    # Pénalité linéaire : -5 points par °C d'écart, plancher à 0
    score = 100 - (diff * 5)
    return max(0.0, min(100.0, score))


def _precipitation_score(precip_mm: float) -> float:
    """Score précipitations : aucune = parfait, forte pluie = nul."""
    if precip_mm <= 0:
        return 100.0
    if precip_mm < 0.5:
        return 90.0   # bruine
    if precip_mm < 2:
        return 70.0   # pluie faible
    if precip_mm < 5:
        return 50.0   # pluie modérée
    if precip_mm < 10:
        return 25.0   # pluie forte
    return 0.0        # déluge


def _wind_score(wind_ms: float) -> float:
    """Score vent : optimal en dessous de 5 m/s."""
    if wind_ms < 5:
        return 100.0
    if wind_ms < 8:
        return 80.0
    if wind_ms < 12:
        return 60.0
    if wind_ms < 17:
        return 30.0   # vent fort, gênant à pied
    return 0.0        # tempête


def _uv_score(uv: float) -> float:
    """Score UV : <3 = bon, >8 = dangereux selon OMS."""
    if uv < 3:
        return 100.0
    if uv < 6:
        return 70.0
    if uv < 8:
        return 40.0
    if uv < 11:
        return 20.0
    return 0.0


def score_weather(inputs: WeatherInputs) -> float:
    """Calcule un score météo 0-100.

    Si toutes les mesures sont absentes, retourne 50 (neutre).
    Sinon, moyenne pondérée des sous-scores disponibles.
    """
    contributions: list[tuple[float, float]] = []

    if inputs.temperature_c is not None:
        contributions.append((_temperature_score(inputs.temperature_c), 0.35))
    if inputs.precipitation_mm is not None:
        contributions.append((_precipitation_score(inputs.precipitation_mm), 0.30))
    if inputs.wind_speed_ms is not None:
        contributions.append((_wind_score(inputs.wind_speed_ms), 0.20))
    if inputs.uv_index is not None:
        contributions.append((_uv_score(inputs.uv_index), 0.15))

    if not contributions:
        return 50.0

    total_weight = sum(w for _, w in contributions)
    weighted_sum = sum(s * w for s, w in contributions)
    return weighted_sum / total_weight
