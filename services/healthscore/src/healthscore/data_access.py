"""Accès aux données récentes pour le scoring santé.

Récupère depuis Supabase les dernières mesures par capteur, à utiliser
pour scorer les waypoints d'un trajet.

Patterns utilisés :
    * "Latest per group" : pour chaque station/point, la mesure la plus récente
    * "Window aggregate" : pour le trafic, moyenne sur les N dernières heures
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine, text

from healthscore.exposure import GeoPoint


@dataclass(frozen=True)
class AirSnapshot:
    """Dernière mesure de qualité d'air d'une station."""

    station_id: str
    station_name: str
    latitude: float
    longitude: float
    aqi: int | None
    pm25: float | None
    pm10: float | None
    no2: float | None

    def as_geo_point(self) -> GeoPoint:
        return GeoPoint(self.station_id, self.latitude, self.longitude)


@dataclass(frozen=True)
class WeatherSnapshot:
    """Dernière observation météo d'un point."""

    point_id: str
    point_name: str
    latitude: float
    longitude: float
    temperature_c: float | None
    precipitation_mm: float | None
    wind_speed_ms: float | None
    uv_index: float | None

    def as_geo_point(self) -> GeoPoint:
        return GeoPoint(self.point_id, self.latitude, self.longitude)


@dataclass(frozen=True)
class TrafficStats:
    """Statistiques de retards sur les arrêts dans une zone."""

    avg_delay_seconds: float | None
    sample_count: int


_LATEST_AIR_SQL = text(
    """
    SELECT DISTINCT ON (station_id)
        station_id, station_name, latitude, longitude,
        aqi, pm25, pm10, no2
    FROM air_measurements
    WHERE measured_at >= NOW() - INTERVAL '6 hours'
    ORDER BY station_id, measured_at DESC
    """
)


_LATEST_WEATHER_SQL = text(
    """
    SELECT DISTINCT ON (point_id)
        point_id, point_name, latitude, longitude,
        temperature_c, precipitation_mm, wind_speed_ms, uv_index
    FROM weather_observations
    WHERE observed_at >= NOW() - INTERVAL '3 hours'
    ORDER BY point_id, observed_at DESC
    """
)


def fetch_latest_air_measurements(engine: Engine) -> list[AirSnapshot]:
    """Récupère la dernière mesure de chaque station AQICN (< 6h)."""
    with engine.connect() as conn:
        rows = conn.execute(_LATEST_AIR_SQL).fetchall()

    return [
        AirSnapshot(
            station_id=row.station_id,
            station_name=row.station_name,
            latitude=row.latitude,
            longitude=row.longitude,
            aqi=row.aqi,
            pm25=row.pm25,
            pm10=row.pm10,
            no2=row.no2,
        )
        for row in rows
    ]


def fetch_latest_weather_observations(engine: Engine) -> list[WeatherSnapshot]:
    """Récupère la dernière observation de chaque point Open-Meteo (< 3h)."""
    with engine.connect() as conn:
        rows = conn.execute(_LATEST_WEATHER_SQL).fetchall()

    return [
        WeatherSnapshot(
            point_id=row.point_id,
            point_name=row.point_name,
            latitude=row.latitude,
            longitude=row.longitude,
            temperature_c=row.temperature_c,
            precipitation_mm=row.precipitation_mm,
            wind_speed_ms=row.wind_speed_ms,
            uv_index=row.uv_index,
        )
        for row in rows
    ]


def fetch_traffic_stats_in_area(
    engine: Engine,
    latitude: float,
    longitude: float,
    radius_km: float = 2.0,
    hours: int = 24,
) -> TrafficStats:
    """Calcule le retard moyen sur les arrêts dans un rayon donné.

    Approximation : on filtre par bounding box (lat ± radius/111, lon ± radius/...).
    Pas un vrai calcul haversine côté SQL (ce serait plus précis avec PostGIS).
    On compense en filtrant côté Python ensuite si nécessaire.

    Note importante : on n'a PAS la position GPS dans stop_visits actuellement.
    Cette implémentation est volontairement simpliste : on prend le retard moyen
    GLOBAL sur la fenêtre temporelle. C'est une limite documentée à corriger
    quand on aura enrichi stop_visits avec les coordonnées des arrêts.
    """
    sql = text(
        """
        SELECT
            AVG(delay_seconds)::FLOAT AS avg_delay,
            COUNT(*)::INTEGER AS sample_count
        FROM stop_visits
        WHERE recorded_at >= NOW() - (:hours || ' hours')::INTERVAL
          AND delay_seconds IS NOT NULL
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql, {"hours": hours}).one()

    return TrafficStats(
        avg_delay_seconds=row.avg_delay,
        sample_count=row.sample_count or 0,
    )
