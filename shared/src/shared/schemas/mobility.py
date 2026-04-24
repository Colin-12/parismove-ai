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
    line_name: str | None = None
    direction: str | None = Field(
        default=None, description="Nom de la destination affichée"
    )
    transport_mode: TransportMode = TransportMode.UNKNOWN

    # Horaires
    aimed_arrival: datetime | None = Field(
        default=None, description="Horaire théorique planifié"
    )
    expected_arrival: datetime | None = Field(
        default=None, description="Horaire prévu, révisé en temps réel"
    )

    # Qualité de la donnée
    arrival_status: str | None = Field(
        default=None,
        description="onTime / delayed / cancelled / missed / arrived",
    )

    # Traçabilité
    recorded_at: datetime = Field(
        description="Instant de l'ingestion (utile pour l'historisation)"
    )
    source: str = Field(default="prim", description="Source de la donnée")

    @property
    def delay_seconds(self) -> int | None:
        """Retard en secondes (positif = en retard, négatif = en avance).

        Retourne None si l'un des deux horaires est absent.
        """
        if self.aimed_arrival is None or self.expected_arrival is None:
            return None
        return int((self.expected_arrival - self.aimed_arrival).total_seconds())
