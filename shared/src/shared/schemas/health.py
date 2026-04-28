"""Schémas pour les scores de santé de trajet."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class HealthGrade(str, Enum):
    """Grade de qualité d'exposition, format Nutri-Score / Yuka.

    A = très bon (vert) — recommandé
    B = bon (vert clair)
    C = moyen (jaune)
    D = mauvais (orange) — déconseillé pour personnes sensibles
    E = très mauvais (rouge) — déconseillé pour tous
    """

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"


class WaypointExposure(BaseModel):
    """Exposition mesurée à un point (sub-score d'un waypoint d'un trajet)."""

    model_config = ConfigDict(frozen=True)

    latitude: float
    longitude: float

    # Score 0-100 par dimension (100 = excellent, 0 = catastrophique)
    pollution_score: float = Field(ge=0, le=100)
    weather_score: float = Field(ge=0, le=100)
    traffic_score: float = Field(ge=0, le=100)

    # Indicateurs bruts utilisés pour le scoring (pour le débuggage/explication)
    nearest_air_station_id: str | None = None
    nearest_air_station_distance_km: float | None = None
    pm25: float | None = None
    no2: float | None = None
    aqi: int | None = None

    nearest_weather_point_id: str | None = None
    nearest_weather_point_distance_km: float | None = None
    temperature_c: float | None = None
    precipitation_mm: float | None = None
    wind_speed_ms: float | None = None
    uv_index: float | None = None

    # Score global pondéré du waypoint
    overall_score: float = Field(ge=0, le=100)


class JourneyScore(BaseModel):
    """Score d'un trajet décrit comme une liste de coordonnées GPS."""

    model_config = ConfigDict(frozen=True)

    # Identité du trajet
    journey_id: str = Field(
        description="Identifiant logique fourni par l'appelant (ex: 'rer-a')"
    )
    journey_label: str = Field(
        description="Label lisible (ex: 'RER A direct Châtelet → La Défense')"
    )
    waypoints: list[WaypointExposure]

    # Scores agrégés sur l'ensemble du trajet (moyenne des waypoints)
    pollution_score: float = Field(ge=0, le=100)
    weather_score: float = Field(ge=0, le=100)
    traffic_score: float = Field(ge=0, le=100)
    overall_score: float = Field(ge=0, le=100)

    # Grade calculé à partir du overall_score
    grade: HealthGrade

    # Métadonnées
    evaluated_at: datetime
    weights: dict[str, float] = Field(
        description="Poids utilisés (pollution/weather/traffic)"
    )

    # Limitations / warnings éventuels (ex: "station AQICN à plus de 5km")
    warnings: list[str] = Field(default_factory=list)


class JourneyComparison(BaseModel):
    """Résultat d'une comparaison entre 2+ trajets."""

    model_config = ConfigDict(frozen=True)

    journeys: list[JourneyScore]
    best_journey_id: str = Field(
        description="ID du trajet avec le meilleur overall_score"
    )
    score_gap: float = Field(
        description="Différence de score entre le meilleur et le pire (sur 100)"
    )
    evaluated_at: datetime

    @property
    def is_significant(self) -> bool:
        """Une différence < 5 points sur 100 n'est pas significative."""
        return self.score_gap >= 5.0
