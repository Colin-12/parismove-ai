"""Schémas partagés pour les données de mobilité.

Ces modèles servent de contrat entre les services (ingestion, ml, api).
Toute donnée qui circule dans le pipeline doit passer par l'un de ces modèles.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class TransportMode(StrEnum):
    """Modes de transport gérés par PRIM."""

    METRO = "metro"
    RER = "rer"
    TRAIN = "train"
    TRAM = "tram"
    BUS = "bus"
    UNKNOWN = "unknown"


class StopVisit(BaseModel):
    """Un passage (théorique ou temps réel) d'un véhicule à un arrêt.

    Correspond à un objet MonitoredStopVisit dans la réponse SIRI-Lite
    de l'API PRIM "Prochains passages".
    """

    model_config = ConfigDict(frozen=True)

    # Identifiants
    stop_id: str = Field(description="ID de l'arrêt au format STIF:StopPoint:Q:...")
    line_id: str = Field(description="ID de la ligne")
    vehicle_journey_id: str | None = Field(
        default=None, description="ID du passage (course)"
    )

    # Métadonnées ligne
    line_name: str | None = Field(
        default=None,
        description="Nom d'affichage (ex: '1', 'RER A', 'T2', '38')",
    )
    operator: str | None = Field(
        default=None, description="Opérateur : RATP, SNCF, Transdev..."
    )
    direction: str | None = Field(
        default=None, description="Nom de la destination affichée"
    )
    transport_mode: TransportMode = TransportMode.UNKNOWN

    # Horaires : on stocke à la fois arrivée et départ car selon l'opérateur
    # PRIM renvoie parfois seulement l'un ou l'autre.
    aimed_arrival: datetime | None = Field(
        default=None, description="Arrivée théorique planifiée"
    )
    expected_arrival: datetime | None = Field(
        default=None, description="Arrivée prévue, révisée en temps réel"
    )
    aimed_departure: datetime | None = Field(
        default=None, description="Départ théorique planifié"
    )
    expected_departure: datetime | None = Field(
        default=None, description="Départ prévu, révisé en temps réel"
    )

    # Qualité de la donnée
    arrival_status: str | None = Field(
        default=None,
        description="onTime / delayed / cancelled / missed / arrived",
    )
    departure_status: str | None = Field(default=None)

    # Traçabilité
    recorded_at: datetime = Field(
        description="Instant de l'ingestion (utile pour l'historisation)"
    )
    source: str = Field(default="prim", description="Source de la donnée")

    @property
    def best_time(self) -> datetime | None:
        """Retourne le meilleur horaire disponible (prévu > théorique, arrivée > départ).

        Ordre de priorité :
            1. expected_arrival (la plus précise pour un voyageur)
            2. expected_departure
            3. aimed_arrival
            4. aimed_departure
        """
        return (
            self.expected_arrival
            or self.expected_departure
            or self.aimed_arrival
            or self.aimed_departure
        )

    @property
    def delay_seconds(self) -> int | None:
        """Retard en secondes (positif = en retard, négatif = en avance).

        Utilise en priorité la paire arrivée, sinon la paire départ.
        Retourne None si aucune paire comparable n'est disponible.
        """
        if self.aimed_arrival is not None and self.expected_arrival is not None:
            return int((self.expected_arrival - self.aimed_arrival).total_seconds())
        if self.aimed_departure is not None and self.expected_departure is not None:
            return int(
                (self.expected_departure - self.aimed_departure).total_seconds()
            )
        return None
