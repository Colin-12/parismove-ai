"""Accès aux données BDD pour entraînement et inférence.

Joint :
    * `air_measurements` (station, AQI, PM2.5, PM10, NO2, mesure)
    * `weather_observations` (température, humidité, vent — station Airparif
      la plus proche du point météo)

Le mapping station Airparif <-> point météo est fait par "nearest neighbor"
sur les coordonnées (les stations Airparif sont fixes, les points météo aussi).
"""
from __future__ import annotations

import math

import pandas as pd
from sqlalchemy import Engine, text


def _haversine_km(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Distance haversine en km entre 2 points géographiques."""
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    )
    return r * 2 * math.asin(math.sqrt(a))


def fetch_training_data(engine: Engine, days: int = 30) -> pd.DataFrame:
    """Récupère les mesures d'air enrichies par la météo la plus proche.

    Pour chaque ligne d'air_measurements, on attache l'observation météo
    la plus récente (≤ 1h) du point météo le plus proche géographiquement.

    Returns:
        DataFrame avec colonnes :
            station_id, station_name, latitude, longitude,
            measured_at, pm25, pm10, no2,
            temperature_c, humidity_pct, wind_speed_ms, precipitation_mm
        Les lignes sans météo correspondante sont gardées avec NaN.
    """
    sql_air = text(
        """
        SELECT
            station_id, station_name, latitude, longitude,
            measured_at, pm25, pm10, no2
        FROM air_measurements
        WHERE measured_at >= NOW() - (:days || ' days')::INTERVAL
          AND pm25 IS NOT NULL
        ORDER BY station_id, measured_at ASC
        """
    )
    sql_weather = text(
        """
        SELECT
            point_id, latitude, longitude, observed_at,
            temperature_c, humidity_pct, wind_speed_ms, precipitation_mm
        FROM weather_observations
        WHERE observed_at >= NOW() - (:days || ' days')::INTERVAL
        ORDER BY observed_at ASC
        """
    )

    with engine.connect() as conn:
        df_air = pd.read_sql(sql_air, conn, params={"days": days})
        df_w = pd.read_sql(sql_weather, conn, params={"days": days})

    if df_air.empty:
        return df_air

    # Pour chaque mesure d'air, on cherche le point météo le plus proche
    # qui a une obs récente (par station_id, on memoize pour la perf)
    nearest_point_by_station: dict[str, str] = {}
    if not df_w.empty:
        weather_points = (
            df_w[["point_id", "latitude", "longitude"]]
            .drop_duplicates(subset=["point_id"])
            .reset_index(drop=True)
        )
        for station_id, grp in df_air.groupby("station_id"):
            slat = grp.iloc[0]["latitude"]
            slon = grp.iloc[0]["longitude"]
            best_point = None
            best_dist = float("inf")
            for _, w_row in weather_points.iterrows():
                d = _haversine_km(
                    slat, slon, w_row["latitude"], w_row["longitude"]
                )
                if d < best_dist:
                    best_dist = d
                    best_point = w_row["point_id"]
            if best_point is not None:
                nearest_point_by_station[str(station_id)] = str(best_point)

    # On ajoute la colonne nearest_point_id à df_air
    df_air["nearest_point_id"] = df_air["station_id"].map(
        nearest_point_by_station
    )

    # Pour chaque ligne, on join avec l'obs météo la plus proche
    # temporellement de ce point
    if df_w.empty or not nearest_point_by_station:
        # Pas de météo : on retourne air sans enrichissement
        for col in [
            "temperature_c", "humidity_pct",
            "wind_speed_ms", "precipitation_mm",
        ]:
            df_air[col] = pd.NA
        return df_air

    # merge_asof : pour chaque mesure d'air, on prend l'obs météo la plus
    # récente du point cible dans une fenêtre de ±1h.
    df_air_sorted = df_air.sort_values("measured_at").copy()
    df_air_sorted["measured_at"] = pd.to_datetime(
        df_air_sorted["measured_at"], utc=True
    )
    df_w_sorted = df_w.sort_values("observed_at").copy()
    df_w_sorted["observed_at"] = pd.to_datetime(
        df_w_sorted["observed_at"], utc=True
    )

    merged = pd.merge_asof(
        df_air_sorted,
        df_w_sorted[
            ["point_id", "observed_at", "temperature_c",
             "humidity_pct", "wind_speed_ms", "precipitation_mm"]
        ],
        left_on="measured_at",
        right_on="observed_at",
        left_by="nearest_point_id",
        right_by="point_id",
        direction="nearest",
        tolerance=pd.Timedelta("1h"),
    )

    cols = [
        "station_id", "station_name", "latitude", "longitude",
        "measured_at", "pm25", "pm10", "no2",
        "temperature_c", "humidity_pct",
        "wind_speed_ms", "precipitation_mm",
    ]
    return merged[cols].sort_values(
        ["station_id", "measured_at"]
    ).reset_index(drop=True)


def fetch_recent_for_inference(
    engine: Engine, hours_back: int = 48
) -> pd.DataFrame:
    """Récupère le contexte récent pour faire une prédiction H+1.

    Identique à fetch_training_data mais sur une fenêtre courte.
    Utilisé par predict.py.
    """
    days = max(2, hours_back // 24 + 1)
    return fetch_training_data(engine, days=days)
