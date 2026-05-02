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
# Trafic — page dédiée
# ============================================================


@st.cache_data(ttl=60)
def get_traffic_kpis() -> dict[str, float | int]:
    """Statistiques globales du trafic IDFM (24h)."""
    engine = get_engine()

    sql = text(
        """
        WITH recent AS (
            SELECT
                line_ref,
                EXTRACT(EPOCH FROM (
                    expected_arrival_at - aimed_arrival_at
                )) AS delay_sec
            FROM stop_visits
            WHERE recorded_at >= NOW() - INTERVAL '24 hours'
              AND aimed_arrival_at IS NOT NULL
              AND expected_arrival_at IS NOT NULL
        )
        SELECT
            COUNT(*) AS total_visits,
            COUNT(DISTINCT line_ref) AS active_lines,
            AVG(delay_sec) AS avg_delay_sec,
            COUNT(*) FILTER (WHERE delay_sec > 60) * 100.0 /
                NULLIF(COUNT(*), 0) AS pct_late
        FROM recent
        """
    )
    with engine.connect() as conn:
        row = conn.execute(sql).one()

    return {
        "total_visits": row.total_visits or 0,
        "active_lines": row.active_lines or 0,
        "avg_delay_sec": float(row.avg_delay_sec or 0),
        "pct_late": float(row.pct_late or 0),
    }


@st.cache_data(ttl=120)
def get_top_delayed_lines(limit: int = 10, mode: str | None = None) -> pd.DataFrame:
    """Top N lignes avec le plus de retard moyen sur 24h.

    Optionnellement filtré par mode (Métro, RER, Bus, Tram, Train).
    """
    engine = get_engine()

    base_sql = """
        SELECT
            sv.line_ref,
            COALESCE(il.short_name, sv.line_ref) AS line_name,
            COALESCE(il.transport_mode, 'Inconnu') AS transport_mode,
            COUNT(*) AS visits,
            AVG(EXTRACT(EPOCH FROM (
                sv.expected_arrival_at - sv.aimed_arrival_at
            ))) AS avg_delay_sec
        FROM stop_visits sv
        LEFT JOIN idfm_lines il ON sv.line_ref = il.line_ref
        WHERE sv.recorded_at >= NOW() - INTERVAL '24 hours'
          AND sv.aimed_arrival_at IS NOT NULL
          AND sv.expected_arrival_at IS NOT NULL
    """
    if mode:
        base_sql += "  AND il.transport_mode = :mode\n"
    base_sql += """
        GROUP BY sv.line_ref, il.short_name, il.transport_mode
        HAVING COUNT(*) >= 5
        ORDER BY avg_delay_sec DESC
        LIMIT :limit
    """

    params: dict[str, object] = {"limit": limit}
    if mode:
        params["mode"] = mode

    with engine.connect() as conn:
        df = pd.read_sql(text(base_sql), conn, params=params)
    return df


@st.cache_data(ttl=300)
def get_traffic_heatmap(mode: str | None = None) -> pd.DataFrame:
    """Heatmap heure x jour-de-semaine du retard moyen sur 7 derniers jours."""
    engine = get_engine()

    base_sql = """
        SELECT
            EXTRACT(DOW FROM sv.recorded_at)::INT AS day_of_week,
            EXTRACT(HOUR FROM sv.recorded_at)::INT AS hour,
            AVG(EXTRACT(EPOCH FROM (
                sv.expected_arrival_at - sv.aimed_arrival_at
            ))) AS avg_delay_sec,
            COUNT(*) AS visits
        FROM stop_visits sv
        LEFT JOIN idfm_lines il ON sv.line_ref = il.line_ref
        WHERE sv.recorded_at >= NOW() - INTERVAL '7 days'
          AND sv.aimed_arrival_at IS NOT NULL
          AND sv.expected_arrival_at IS NOT NULL
    """
    if mode:
        base_sql += "  AND il.transport_mode = :mode\n"
    base_sql += """
        GROUP BY day_of_week, hour
        ORDER BY day_of_week, hour
    """

    params: dict[str, object] = {}
    if mode:
        params["mode"] = mode

    with engine.connect() as conn:
        df = pd.read_sql(text(base_sql), conn, params=params)
    return df


@st.cache_data(ttl=300)
def get_available_modes() -> list[str]:
    """Liste des modes de transport présents dans le référentiel."""
    engine = get_engine()

    sql = text(
        """
        SELECT DISTINCT transport_mode
        FROM idfm_lines
        WHERE transport_mode IS NOT NULL
        ORDER BY transport_mode
        """
    )
    with engine.connect() as conn:
        result = conn.execute(sql).all()
    return [row.transport_mode for row in result]


# ============================================================
# Score santé — zones prédéfinies
# ============================================================


# Zones IDF prédéfinies pour le score santé. Coordonnées indicatives
# correspondant à des points emblématiques. Mêmes que DEFAULT_METEO_POINTS
# du service ingestion pour cohérence des données météo.
PREDEFINED_ZONES: dict[str, tuple[float, float]] = {
    "Châtelet (Paris 1er)": (48.8585, 2.3470),
    "La Défense": (48.8918, 2.2389),
    "Gare du Nord": (48.8809, 2.3553),
    "Saint-Lazare": (48.8754, 2.3253),
    "Gare de Lyon": (48.8447, 2.3736),
    "Montparnasse": (48.8413, 2.3210),
    "Versailles": (48.8014, 2.1301),
    "Saint-Denis": (48.9358, 2.3539),
    "Boulogne-Billancourt": (48.8347, 2.2400),
    "Créteil": (48.7910, 2.4634),
}


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


def grade_color(grade: str) -> str:
    """Couleur correspondant à un grade A-E."""
    return {
        "A": "#10B981",  # vert
        "B": "#84CC16",  # vert clair
        "C": "#F59E0B",  # jaune
        "D": "#F97316",  # orange
        "E": "#EF4444",  # rouge
    }.get(grade.upper(), "#9CA3AF")


def format_delay(seconds: float) -> str:
    """Format un retard en string lisible : '+1m 30s' / '-15s' / '0s'."""
    if seconds == 0:
        return "0s"
    sign = "+" if seconds > 0 else "-"
    abs_sec = abs(int(seconds))
    if abs_sec < 60:
        return f"{sign}{abs_sec}s"
    minutes, secs = divmod(abs_sec, 60)
    return f"{sign}{minutes}m {secs}s"
