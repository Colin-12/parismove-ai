"""Agrégation des sub-scores et conversion en grade A-E.

Pondération par défaut :
    * Pollution : 60%
    * Météo     : 30%
    * Trafic    : 10%

Cette pondération reflète la priorité scientifique : la qualité de l'air
a l'impact le plus prouvé sur la santé respiratoire et cardiovasculaire
(études OMS, ANSES). La météo et le trafic jouent surtout sur le confort.

Conversion grade :
    [80, 100] → A (vert foncé) — Recommandé
    [65, 80)  → B (vert clair) — Bon
    [50, 65)  → C (jaune)      — Moyen
    [35, 50)  → D (orange)     — Déconseillé pour personnes sensibles
    [0, 35)   → E (rouge)      — Déconseillé pour tous
"""
from __future__ import annotations

from shared.schemas import HealthGrade

DEFAULT_WEIGHTS: dict[str, float] = {
    "pollution": 0.60,
    "weather": 0.30,
    "traffic": 0.10,
}


def aggregate_scores(
    pollution_score: float,
    weather_score: float,
    traffic_score: float,
    weights: dict[str, float] | None = None,
) -> float:
    """Combine les 3 sub-scores en un score global pondéré.

    Args:
        pollution_score: 0-100
        weather_score:   0-100
        traffic_score:   0-100
        weights: dict {"pollution", "weather", "traffic"} avec des poids
                 dont la somme doit faire 1.0. Default = DEFAULT_WEIGHTS.

    Returns:
        Score global 0-100.
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS

    total = (
        pollution_score * weights["pollution"]
        + weather_score * weights["weather"]
        + traffic_score * weights["traffic"]
    )
    return max(0.0, min(100.0, total))


def score_to_grade(score: float) -> HealthGrade:
    """Convertit un score 0-100 en grade A-E.

    Seuils :
        80+   → A
        65-79 → B
        50-64 → C
        35-49 → D
        <35   → E
    """
    if score >= 80:
        return HealthGrade.A
    if score >= 65:
        return HealthGrade.B
    if score >= 50:
        return HealthGrade.C
    if score >= 35:
        return HealthGrade.D
    return HealthGrade.E


def grade_color(grade: HealthGrade) -> str:
    """Retourne la couleur web (#RRGGBB) associée au grade.

    Utile pour le dashboard et les sorties terminal colorées.
    """
    return {
        HealthGrade.A: "#1B7E3D",  # vert foncé
        HealthGrade.B: "#84BD00",  # vert clair
        HealthGrade.C: "#FFCD00",  # jaune
        HealthGrade.D: "#FF8200",  # orange
        HealthGrade.E: "#E40520",  # rouge
    }[grade]
