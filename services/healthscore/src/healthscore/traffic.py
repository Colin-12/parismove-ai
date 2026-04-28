"""Sub-score trafic : densité et qualité du transport en commun à proximité.

Idée : un trajet qui passe par des arrêts en retard chronique est :
    * Moins agréable (attente, stress)
    * Souvent dans des zones de congestion = plus de pollution liée au trafic
    * Moins fiable

On calcule un score basé sur le retard moyen observé sur les arrêts dans
un rayon donné, sur les N dernières heures.

Si pas de données disponibles (BDD vide ou waypoint hors zone couverte),
on retourne un score neutre 50.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TrafficInputs:
    """Mesures brutes utilisées pour le sub-score trafic."""

    avg_delay_seconds: float | None = None
    sample_count: int = 0


def score_traffic(inputs: TrafficInputs) -> float:
    """Calcule un score trafic 0-100 (100 = ponctuel, 0 = chaos).

    Seuils choisis :
        * <30 s de retard moyen : 100 (excellent)
        * 30-60 s : 90 (bon)
        * 60-120 s : 70 (acceptable)
        * 120-300 s : 40 (médiocre)
        * 300-600 s : 15 (mauvais)
        * >10 min   : 0 (chaos)

    Si l'échantillon est trop petit (< 5 mesures), on baisse la confiance
    et on retourne un score atténué vers 50.
    """
    if inputs.avg_delay_seconds is None or inputs.sample_count == 0:
        return 50.0

    delay = inputs.avg_delay_seconds

    if delay < 30:
        raw_score = 100.0
    elif delay < 60:
        raw_score = 90.0
    elif delay < 120:
        raw_score = 70.0
    elif delay < 300:
        raw_score = 40.0
    elif delay < 600:
        raw_score = 15.0
    else:
        raw_score = 0.0

    # Atténuation si l'échantillon est trop petit
    # (on tire le score vers 50 = neutre)
    if inputs.sample_count < 5:
        confidence = inputs.sample_count / 5.0
        raw_score = raw_score * confidence + 50 * (1 - confidence)

    return raw_score
