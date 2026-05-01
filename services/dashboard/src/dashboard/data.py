"""Couche d'accès aux données du dashboard.

Toutes les fonctions sont décorées avec `@st.cache_data` pour éviter de
re-exécuter les requêtes à chaque interaction utilisateur. Le cache est
invalidé toutes les `ttl` secondes (par défaut 60s pour les données fraîches).

Pour le cache de l'engine SQLAlchemy lui-même, on utilise `@st.cache_resource`
qui partage l'objet entre toutes les sessions.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
from shared.db import create_database_engine
from sqlalchemy import Engine, text

from dashboard.config import get_settings


@st.cache_resource
def get_engine() -> Engine:
    """Retourne un engine SQLAlchemy partagé par toutes les sessions.

    Mise en cache via `cache_resource` car l'engine est un objet réutilisable
    qu'on ne veut pas recréer à chaque requête.
    """
    settings = get_settings()
    if not settings.database_url:
        st.error("❌ DATABASE_URL n'est pas configurée.")
        st.stop()
    return create_database_engine(settings.database_url)


# ============================================================
# Vue d'ensemble — page Accueil
# ============================================================


@st.cache_data(ttl=60)
def get_global_stats() -> dict[str, int | datetime | None]:
    """Retourne les statistiques globales pour la page d'accueil."""
    engine = get_engine()

    sql = text(
        """
        SELECT
            (SELECT COUNT(*) FROM stop_visits) AS stop_visits_count,
            (SELECT COUNT(*) FROM air_measurements) AS air_count,
            (SELECT COUNT(*) FROM weather_observations) AS weather_count,
            (SELECT COUNT(*) FROM idfm_lines) AS lines_count,
            (SELECT MAX(recorded_at) FROM stop_visits) AS last_stop_visit,
            (SELECT MAX(measured_at) FROM air_measurements) AS last_air,
            (SELECT MAX(observed_at) FROM weather_observations) AS last_weather
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql).one()

    return {
        "stop_visits_count": row.stop_visits_count or 0,
        "air_count": row.air_count or 0,
        "weather_count": row.weather_count or 0,
        "lines_count": row.lines_count or 0,
        "last_stop_visit": row.last_stop_visit,
        "last_air": row.last_air,
        "last_weather": row.last_weather,
    }


@st.cache_data(ttl=300)
def get_ingestion_history(hours: int = 24) -> pd.DataFrame:
    """Retourne le nombre d'inserts par heure et par source sur la fenêtre."""
    engine = get_engine()

    sql = text(
        """
        SELECT
            DATE_TRUNC('hour', recorded_at) AS hour,
            'PRIM IDFM' AS source,
            COUNT(*) AS count
        FROM stop_visits
        WHERE recorded_at >= NOW() - (:hours || ' hours')::INTERVAL
        GROUP BY hour
        UNION ALL
        SELECT
            DATE_TRUNC('hour', measured_at) AS hour,
            'AQICN' AS source,
            COUNT(*) AS count
        FROM air_measurements
        WHERE measured_at >= NOW() - (:hours || ' hours')::INTERVAL
        GROUP BY hour
        UNION ALL
        SELECT
            DATE_TRUNC('hour', observed_at) AS hour,
            'Open-Meteo' AS source,
            COUNT(*) AS count
        FROM weather_observations
        WHERE observed_at >= NOW() - (:hours || ' hours')::INTERVAL
        GROUP BY hour
        ORDER BY hour ASC
        """
    )
    with engine.connect() as conn:
        df = pd.read_sql(sql, conn, params={"hours": hours})
    return df


# ============================================================
# Qualité de l'air — page dédiée
# ============================================================


@st.cache_data(ttl=60)
def get_latest_air_measurements() -> pd.DataFrame:
    """Dernière mesure pour chaque station AQICN active."""
    engine = get_engine()

    sql = text(
        """
        SELECT DISTINCT ON (station_id)
            station_id,
            station_name,
            latitude,
            longitude,
            aqi,
            pm25,
            pm10,
            no2,
            o3,
            temperature_c,
            humidity_pct,
            measured_at,
            attribution
        FROM air_measurements
        WHERE measured_at >= NOW() - INTERVAL '24 hours'
        ORDER BY station_id, measured_at DESC
        """
    )
    with engine.connect() as conn:
        df = pd.read_sql(sql, conn)
    return df


@st.cache_data(ttl=300)
def get_air_history(station_id: str | None = None, hours: int = 48) -> pd.DataFrame:
    """Historique des mesures d'air, par station ou global."""
    engine = get_engine()

    if station_id is not None:
        sql = text(
            """
            SELECT
                station_id, station_name,
                aqi, pm25, pm10, no2,
                measured_at
            FROM air_measurements
            WHERE measured_at >= NOW() - (:hours || ' hours')::INTERVAL
              AND station_id = :station_id
            ORDER BY measured_at ASC
            """
        )
        params: dict[str, object] = {"hours": hours, "station_id": station_id}
    else:
        sql = text(
            """
            SELECT
                station_id, station_name,
                aqi, pm25, pm10, no2,
                measured_at
            FROM air_measurements
            WHERE measured_at >= NOW() - (:hours || ' hours')::INTERVAL
            ORDER BY measured_at ASC
            """
        )
        params = {"hours": hours}

    with engine.connect() as conn:
        df = pd.read_sql(sql, conn, params=params)
    return df


# ============================================================
# Helpers de formatage
# ============================================================


def format_age(when: datetime | None) -> str:
    """'il y a 5 min' / 'il y a 2h' / '?' si None."""
    if when is None:
        return "?"
    now = datetime.now(when.tzinfo) if when.tzinfo else datetime.now()
    delta = now - when
    if delta < timedelta(minutes=1):
        return "à l'instant"
    if delta < timedelta(hours=1):
        return f"il y a {int(delta.total_seconds() / 60)} min"
    if delta < timedelta(days=1):
        return f"il y a {int(delta.total_seconds() / 3600)}h"
    return f"il y a {delta.days}j"


def aqi_color(aqi: float | int | None) -> str:
    """Retourne la couleur officielle AQI selon le seuil."""
    if aqi is None:
        return "#9CA3AF"  # gris
    if aqi <= 50:
        return "#10B981"  # vert (good)
    if aqi <= 100:
        return "#F59E0B"  # jaune (moderate)
    if aqi <= 150:
        return "#F97316"  # orange (sensitive)
    if aqi <= 200:
        return "#EF4444"  # rouge (unhealthy)
    if aqi <= 300:
        return "#A855F7"  # violet (very unhealthy)
    return "#7C2D12"      # marron (hazardous)


def aqi_label(aqi: float | int | None) -> str:
    """Catégorie textuelle correspondant à l'AQI."""
    if aqi is None:
        return "?"
    if aqi <= 50:
        return "Bon"
    if aqi <= 100:
        return "Modéré"
    if aqi <= 150:
        return "Mauvais (sensibles)"
    if aqi <= 200:
        return "Mauvais"
    if aqi <= 300:
        return "Très mauvais"
    return "Dangereux"
