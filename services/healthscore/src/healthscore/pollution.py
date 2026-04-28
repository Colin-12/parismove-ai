"""Sub-score pollution basé sur les seuils OMS et la grille EAQI.

Sources scientifiques :
    * OMS Global Air Quality Guidelines 2021
      https://www.who.int/publications/i/item/9789240034228
    * Indice EAQI (European Air Quality Index)
      https://www.eea.europa.eu/themes/air/air-quality-index

Logique :
    * On convertit chaque polluant en un score 0-100 par rapport aux seuils
      OMS (niveau "good" → 100, niveau "hazardous" → 0).
    * Le score pollution global est la moyenne pondérée :
        - PM2.5 : 50% (le plus dangereux pour la santé respiratoire)
        - NO2   : 30% (proxy du trafic urbain)
        - AQI   : 20% (indicateur agrégé fallback)
    * Si une mesure est manquante, son poids est redistribué.
"""
from __future__ import annotations

from dataclasses import dataclass

# Seuils OMS 2021 pour PM2.5 (moyenne 24h en µg/m³)
# https://www.who.int/news-room/feature-stories/detail/what-are-the-who-air-quality-guidelines
PM25_THRESHOLDS: list[tuple[float, float, float]] = [
    (0, 5, 100),      # OMS guideline = excellent
    (5, 15, 80),      # Acceptable
    (15, 25, 60),     # Modéré
    (25, 50, 40),     # Mauvais
    (50, 75, 20),     # Très mauvais
    (75, 999, 0),     # Catastrophique
]

# Seuils OMS 2021 pour NO2 (moyenne 24h en µg/m³)
NO2_THRESHOLDS: list[tuple[float, float, float]] = [
    (0, 10, 100),
    (10, 25, 80),
    (25, 50, 60),
    (50, 100, 40),
    (100, 200, 20),
    (200, 999, 0),
]

# Seuils US AQI (US EPA)
AQI_THRESHOLDS: list[tuple[float, float, float]] = [
    (0, 50, 100),     # Good
    (50, 100, 75),    # Moderate
    (100, 150, 50),   # Unhealthy for sensitive
    (150, 200, 30),   # Unhealthy
    (200, 300, 15),   # Very unhealthy
    (300, 999, 0),    # Hazardous
]

@dataclass(frozen=True)
class PollutionInputs:
    """Mesures brutes utilisées pour calculer le sub-score pollution."""

    pm25: float | None = None
    no2: float | None = None
    aqi: int | None = None


def _score_from_thresholds(
    value: float, thresholds: list[tuple[float, float, float]]
) -> float:
    """Interpole linéairement un score à partir d'une grille de seuils.

    Pour value=12 dans une grille [(5, 15, 80), (15, 25, 60)] :
        - 12 est entre 5 et 15 (range 80)
        - position relative : (12-5)/(15-5) = 0.7
        - score : 100 - 0.7 * (100-80) = 86 (interpolation)

    En réalité on simplifie : on retourne directement la valeur du palier.
    """
    for low, high, score in thresholds:
        if low <= value < high:
            return score
    # Au-delà du dernier palier
    return thresholds[-1][2]


def score_pollution(inputs: PollutionInputs) -> float:
    """Calcule un score 0-100 (100 = excellent) à partir des mesures.

    Si toutes les mesures sont absentes, retourne 50 (neutre).
    Sinon, fait la moyenne pondérée des sous-scores disponibles.

    Args:
        inputs: PollutionInputs avec les mesures brutes (peuvent être None)

    Returns:
        Score 0-100, où 100 = qualité excellente.
    """
    contributions: list[tuple[float, float]] = []  # (score, weight)

    if inputs.pm25 is not None:
        contributions.append(
            (_score_from_thresholds(inputs.pm25, PM25_THRESHOLDS), 0.5)
        )
    if inputs.no2 is not None:
        contributions.append(
            (_score_from_thresholds(inputs.no2, NO2_THRESHOLDS), 0.3)
        )
    if inputs.aqi is not None:
        contributions.append(
            (_score_from_thresholds(float(inputs.aqi), AQI_THRESHOLDS), 0.2)
        )

    if not contributions:
        return 50.0  # neutre quand aucune mesure n'est dispo

    total_weight = sum(w for _, w in contributions)
    weighted_sum = sum(s * w for s, w in contributions)
    return weighted_sum / total_weight
