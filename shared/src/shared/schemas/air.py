"""Schémas pour les mesures de qualité de l'air."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AirMeasurement(BaseModel):
    """Une mesure de qualité de l'air à une station, à un instant T.

    Les concentrations sont en µg/m³ (microgrammes par mètre cube).
    L'AQI (Air Quality Index) est une valeur agrégée sans unité, où :
        0-50    bon
        51-100  modéré
        101-150 mauvais pour groupes sensibles
        151-200 mauvais
        201-300 très mauvais
        301+    dangereux
    """

    model_config = ConfigDict(frozen=True)

    station_id: str = Field(description="ID interne de la station AQICN")
    station_name: str = Field(description="Nom lisible de la station")
    latitude: float
    longitude: float

    aqi: int | None = Field(default=None, description="Indice agrégé US EPA")
    pm25: float | None = Field(default=None, description="Particules PM2.5 µg/m³")
    pm10: float | None = Field(default=None, description="Particules PM10 µg/m³")
    no2: float | None = Field(default=None, description="Dioxyde d'azote µg/m³")
    o3: float | None = Field(default=None, description="Ozone µg/m³")
    so2: float | None = Field(default=None, description="Dioxyde de soufre µg/m³")
    co: float | None = Field(default=None, description="Monoxyde de carbone mg/m³")

    temperature_c: float | None = None
    humidity_pct: float | None = None
    pressure_hpa: float | None = None
    wind_speed_ms: float | None = None

    measured_at: datetime = Field(description="Horodatage donné par AQICN")
    recorded_at: datetime = Field(description="Instant de l'ingestion")
    attribution: str | None = Field(
        default=None, description="Source officielle (Airparif, Atmo France...)"
    )
    source: str = Field(default="aqicn")

    @property
    def aqi_category(self) -> str:
        """Retourne la catégorie textuelle de l'AQI selon la grille US EPA."""
        if self.aqi is None:
            return "unknown"
        if self.aqi <= 50:
            return "good"
        if self.aqi <= 100:
            return "moderate"
        if self.aqi <= 150:
            return "unhealthy_sensitive"
        if self.aqi <= 200:
            return "unhealthy"
        if self.aqi <= 300:
            return "very_unhealthy"
        return "hazardous"
