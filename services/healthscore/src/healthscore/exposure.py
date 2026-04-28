"""Rapprochement spatial entre waypoints d'un trajet et capteurs disponibles.

Pour chaque waypoint (latitude, longitude), on cherche :
    * La station AQICN la plus proche (mesure de pollution réelle)
    * Le point Open-Meteo le plus proche (météo et pollution modélisée)
    * Les arrêts PRIM dans un rayon donné (proxy de densité de trafic)

On utilise la formule haversine pour calculer la distance grand-cercle entre
deux points GPS. C'est la méthode standard et précise à <1% sur les distances
en jeu (max 50 km en IDF).
"""
from __future__ import annotations

import math
from collections.abc import Iterable
from typing import NamedTuple

EARTH_RADIUS_KM = 6371.0


class GeoPoint(NamedTuple):
    """Un point géographique avec un identifiant logique."""

    point_id: str
    latitude: float
    longitude: float


def haversine_km(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Distance grand-cercle entre 2 points GPS, en kilomètres.

    Formule haversine, précise à <1% sur les distances en IDF.
    """
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(rlat1) * math.cos(rlat2) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))
    return EARTH_RADIUS_KM * c


def find_nearest(
    target_lat: float,
    target_lon: float,
    candidates: Iterable[GeoPoint],
) -> tuple[GeoPoint, float] | None:
    """Trouve le candidat le plus proche d'un point cible.

    Args:
        target_lat: latitude du point cible
        target_lon: longitude du point cible
        candidates: itérable de GeoPoint candidats

    Returns:
        Tuple (candidat le plus proche, distance en km), ou None si vide.
    """
    best: tuple[GeoPoint, float] | None = None

    for candidate in candidates:
        distance = haversine_km(
            target_lat, target_lon,
            candidate.latitude, candidate.longitude,
        )
        if best is None or distance < best[1]:
            best = (candidate, distance)

    return best


def find_within_radius(
    target_lat: float,
    target_lon: float,
    candidates: Iterable[GeoPoint],
    radius_km: float,
) -> list[tuple[GeoPoint, float]]:
    """Retourne tous les candidats dans un rayon donné, triés par distance."""
    in_range = []
    for candidate in candidates:
        distance = haversine_km(
            target_lat, target_lon,
            candidate.latitude, candidate.longitude,
        )
        if distance <= radius_km:
            in_range.append((candidate, distance))

    in_range.sort(key=lambda x: x[1])
    return in_range
