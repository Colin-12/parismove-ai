"""Schémas pour les observations météorologiques."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WeatherObservation(BaseModel):
    """Une observation météo + qualité de l'air à un point GPS, à un instant T.

    Source : Open-Meteo (modèles atmosphériques DWD ICON / ECMWF + CAMS pour
    la qualité de l'air). Contrairement à AQICN qui mesure au sol via capteurs,
    Open-Meteo fournit des valeurs **modélisées** : utile pour la prédiction
    et pour valider les mesures terrain.

    Toutes les concentrations sont en µg/m³ sauf le CO en mg/m³.
    Les vitesses de vent sont en m/s, les températures en °C.
    """

    model_config = ConfigDict(frozen=True)

    # Identifiant logique du point d'observation (slug stable, pas de coordonnée)
    point_id: str = Field(
        description="Slug du point d'observation (ex: 'paris-centre')"
    )
    point_name: str = Field(description="Nom lisible du point")
    latitude: float
    longitude: float
    elevation_m: float | None = Field(
        default=None, description="Altitude du point en mètres"
    )

    # Météo générale
    temperature_c: float | None = None
    apparent_temperature_c: float | None = Field(
        default=None, description="Ressentie (Wind Chill / Heat Index)"
    )
    humidity_pct: float | None = None
    pressure_hpa: float | None = Field(
        default=None, description="Pression au niveau de la mer"
    )
    surface_pressure_hpa: float | None = None
    cloud_cover_pct: float | None = None
    visibility_m: float | None = None

    # Précipitations
    precipitation_mm: float | None = Field(
        default=None, description="Cumul des 60 dernières minutes"
    )
    rain_mm: float | None = None
    showers_mm: float | None = None
    snowfall_cm: float | None = None

    # Vent
    wind_speed_ms: float | None = None
    wind_gusts_ms: float | None = None
    wind_direction_deg: float | None = None

    # UV et soleil
    uv_index: float | None = None
    is_day: bool | None = Field(default=None, description="True si après le lever")

    # Code WMO synthétique (0=ciel clair, 1-3=variable, 51-55=bruine, 61-65=pluie...)
    weather_code: int | None = Field(
        default=None, description="Code WMO 4677 décrivant le temps"
    )

    # Qualité de l'air modélisée (CAMS European Air Quality Forecast)
    aqi_european: float | None = Field(
        default=None, description="EAQI 1-5 (1=très bon, 5=très mauvais)"
    )
    pm25: float | None = None
    pm10: float | None = None
    no2: float | None = None
    o3: float | None = None
    so2: float | None = None
    co: float | None = None

    # Pollens (utile pour le score santé en saison)
    alder_pollen: float | None = None
    birch_pollen: float | None = None
    grass_pollen: float | None = None
    ragweed_pollen: float | None = None

    # Traçabilité
    observed_at: datetime = Field(description="Horodatage de la mesure modélisée")
    recorded_at: datetime = Field(description="Instant de l'ingestion")
    source: str = Field(default="open-meteo")

    @property
    def has_precipitation(self) -> bool:
        """Helper : y a-t-il des précipitations significatives ?"""
        return any(
            v is not None and v > 0
            for v in (self.precipitation_mm, self.rain_mm, self.snowfall_cm)
        )
