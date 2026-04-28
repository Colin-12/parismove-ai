"""Orchestrateur principal : score un trajet, compare des trajets.

C'est le module qui combine les différents sub-scores et appelle la BDD
pour obtenir les mesures actuelles.
"""
from __future__ import annotations

from datetime import UTC, datetime

from shared.schemas import (
    JourneyComparison,
    JourneyScore,
    WaypointExposure,
)
from sqlalchemy import Engine

from healthscore.data_access import (
    AirSnapshot,
    WeatherSnapshot,
    fetch_latest_air_measurements,
    fetch_latest_weather_observations,
    fetch_traffic_stats_in_area,
)
from healthscore.exposure import find_nearest
from healthscore.pollution import PollutionInputs, score_pollution
from healthscore.scoring import (
    DEFAULT_WEIGHTS,
    aggregate_scores,
    score_to_grade,
)
from healthscore.traffic import TrafficInputs, score_traffic
from healthscore.weather import WeatherInputs, score_weather

# Au-delà de cette distance, on considère que la mesure n'est plus
# représentative pour le waypoint. On émet alors un warning.
MAX_REPRESENTATIVE_DISTANCE_KM = 5.0


def _score_waypoint(
    latitude: float,
    longitude: float,
    air_snapshots: list[AirSnapshot],
    weather_snapshots: list[WeatherSnapshot],
    traffic_avg_delay: float | None,
    traffic_sample_count: int,
) -> tuple[WaypointExposure, list[str]]:
    """Score un seul waypoint à partir des données ambiantes."""
    warnings: list[str] = []

    # Trouve la station AQICN la plus proche
    nearest_air = find_nearest(
        latitude, longitude,
        [s.as_geo_point() for s in air_snapshots],
    )
    air_data: AirSnapshot | None = None
    air_distance: float | None = None
    if nearest_air is not None:
        point, distance = nearest_air
        air_distance = distance
        if distance > MAX_REPRESENTATIVE_DISTANCE_KM:
            warnings.append(
                f"Station de pollution la plus proche à {distance:.1f} km "
                f"(>{MAX_REPRESENTATIVE_DISTANCE_KM} km), score peu représentatif"
            )
        air_data = next(
            (s for s in air_snapshots if s.station_id == point.point_id),
            None,
        )

    # Trouve le point météo le plus proche
    nearest_weather = find_nearest(
        latitude, longitude,
        [s.as_geo_point() for s in weather_snapshots],
    )
    weather_data: WeatherSnapshot | None = None
    weather_distance: float | None = None
    if nearest_weather is not None:
        point, distance = nearest_weather
        weather_distance = distance
        weather_data = next(
            (s for s in weather_snapshots if s.point_id == point.point_id),
            None,
        )

    # Calcul des sub-scores
    pollution = score_pollution(
        PollutionInputs(
            pm25=air_data.pm25 if air_data else None,
            no2=air_data.no2 if air_data else None,
            aqi=air_data.aqi if air_data else None,
        )
    )
    weather = score_weather(
        WeatherInputs(
            temperature_c=weather_data.temperature_c if weather_data else None,
            precipitation_mm=weather_data.precipitation_mm if weather_data else None,
            wind_speed_ms=weather_data.wind_speed_ms if weather_data else None,
            uv_index=weather_data.uv_index if weather_data else None,
        )
    )
    traffic = score_traffic(
        TrafficInputs(
            avg_delay_seconds=traffic_avg_delay,
            sample_count=traffic_sample_count,
        )
    )

    overall = aggregate_scores(pollution, weather, traffic)

    exposure = WaypointExposure(
        latitude=latitude,
        longitude=longitude,
        pollution_score=pollution,
        weather_score=weather,
        traffic_score=traffic,
        overall_score=overall,
        nearest_air_station_id=air_data.station_id if air_data else None,
        nearest_air_station_distance_km=air_distance,
        pm25=air_data.pm25 if air_data else None,
        no2=air_data.no2 if air_data else None,
        aqi=air_data.aqi if air_data else None,
        nearest_weather_point_id=weather_data.point_id if weather_data else None,
        nearest_weather_point_distance_km=weather_distance,
        temperature_c=weather_data.temperature_c if weather_data else None,
        precipitation_mm=weather_data.precipitation_mm if weather_data else None,
        wind_speed_ms=weather_data.wind_speed_ms if weather_data else None,
        uv_index=weather_data.uv_index if weather_data else None,
    )
    return exposure, warnings


def score_journey(
    engine: Engine,
    journey_id: str,
    journey_label: str,
    waypoints: list[tuple[float, float]],
    weights: dict[str, float] | None = None,
) -> JourneyScore:
    """Score un trajet décrit par une liste de coordonnées GPS.

    Args:
        engine: connexion à la BDD pour les snapshots actuels
        journey_id: identifiant logique du trajet (ex: 'rer-a-direct')
        journey_label: label lisible pour l'utilisateur
        waypoints: liste de (latitude, longitude) traversées par le trajet
        weights: poids pondération. Default = DEFAULT_WEIGHTS.

    Returns:
        JourneyScore agrégé sur tous les waypoints.
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS

    if not waypoints:
        raise ValueError("Le trajet doit avoir au moins un waypoint")

    # 1. Récupération unique des snapshots actuels
    air_snapshots = fetch_latest_air_measurements(engine)
    weather_snapshots = fetch_latest_weather_observations(engine)

    # Trafic : on prend une stat globale (vu la limitation actuelle de
    # stop_visits qui n'a pas les coords). Quand on aura enrichi, on
    # pourra calculer par zone.
    if waypoints:
        avg_lat = sum(w[0] for w in waypoints) / len(waypoints)
        avg_lon = sum(w[1] for w in waypoints) / len(waypoints)
        traffic_stats = fetch_traffic_stats_in_area(
            engine, avg_lat, avg_lon, radius_km=10.0
        )
    else:
        traffic_stats = None

    # 2. Score chaque waypoint
    exposures: list[WaypointExposure] = []
    all_warnings: set[str] = set()

    for lat, lon in waypoints:
        exposure, warnings = _score_waypoint(
            lat, lon,
            air_snapshots, weather_snapshots,
            traffic_stats.avg_delay_seconds if traffic_stats else None,
            traffic_stats.sample_count if traffic_stats else 0,
        )
        exposures.append(exposure)
        all_warnings.update(warnings)

    # 3. Agrégation sur le trajet (moyenne arithmétique des waypoints)
    n = len(exposures)
    avg_pollution = sum(e.pollution_score for e in exposures) / n
    avg_weather = sum(e.weather_score for e in exposures) / n
    avg_traffic = sum(e.traffic_score for e in exposures) / n
    overall = aggregate_scores(avg_pollution, avg_weather, avg_traffic, weights)

    if not air_snapshots:
        all_warnings.add("Aucune donnée de pollution récente disponible")
    if not weather_snapshots:
        all_warnings.add("Aucune donnée météo récente disponible")

    return JourneyScore(
        journey_id=journey_id,
        journey_label=journey_label,
        waypoints=exposures,
        pollution_score=avg_pollution,
        weather_score=avg_weather,
        traffic_score=avg_traffic,
        overall_score=overall,
        grade=score_to_grade(overall),
        evaluated_at=datetime.now(UTC),
        weights=weights,
        warnings=sorted(all_warnings),
    )


def compare_journeys(
    engine: Engine,
    journeys: list[tuple[str, str, list[tuple[float, float]]]],
    weights: dict[str, float] | None = None,
) -> JourneyComparison:
    """Compare plusieurs trajets et retourne le meilleur.

    Args:
        engine: connexion BDD
        journeys: liste de (journey_id, journey_label, waypoints)

    Returns:
        JourneyComparison avec tous les scores et l'ID du meilleur.
    """
    if not journeys:
        raise ValueError("Il faut au moins un trajet à comparer")

    scored = [
        score_journey(engine, jid, label, wpts, weights)
        for jid, label, wpts in journeys
    ]

    best = max(scored, key=lambda s: s.overall_score)
    worst = min(scored, key=lambda s: s.overall_score)
    gap = best.overall_score - worst.overall_score

    return JourneyComparison(
        journeys=scored,
        best_journey_id=best.journey_id,
        score_gap=gap,
        evaluated_at=datetime.now(UTC),
    )
