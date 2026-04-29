"""Découverte des stations AQICN actives dans une zone donnée.

Utilise l'endpoint `map/bounds` de l'API AQICN pour lister toutes les
stations dans une bounding box, puis appelle `feed/@{id}` pour vérifier
que chaque station retourne bien des données récentes.

Usage:
    python -m ingestion.scripts.discover_aqicn_stations

Affiche un tableau des stations IDF triées par AQI avec leurs IDs
utilisables dans DEFAULT_AQICN_STATIONS.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx

# Ajout dynamique du répertoire src au PYTHONPATH si lancé depuis la racine du projet
THIS_DIR = Path(__file__).resolve().parent
SRC_DIR = THIS_DIR.parent.parent / "src"
if SRC_DIR.exists() and str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ingestion.config import get_settings  # noqa: E402

# Bounding box approximative pour l'Île-de-France (rayon ~50 km autour de Paris)
# Format : (lat_min, lon_min, lat_max, lon_max)
IDF_BBOX = (48.5, 1.8, 49.2, 3.1)

AQICN_BOUNDS_URL = "https://api.waqi.info/v2/map/bounds"
AQICN_FEED_URL = "https://api.waqi.info/feed/@{station_id}/"


async def discover_stations() -> list[dict[str, object]]:
    """Récupère toutes les stations AQICN actives dans la bounding box IDF."""
    settings = get_settings()
    if not settings.aqicn_token:
        print("❌ AQICN_TOKEN manquant dans .env", file=sys.stderr)
        sys.exit(1)

    lat_min, lon_min, lat_max, lon_max = IDF_BBOX
    latlng = f"{lat_min},{lon_min},{lat_max},{lon_max}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Récupérer la liste des stations dans la bbox
        response = await client.get(
            AQICN_BOUNDS_URL,
            params={"latlng": latlng, "token": settings.aqicn_token},
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "ok":
            print(f"❌ Erreur API : {data}", file=sys.stderr)
            sys.exit(1)

        stations = data.get("data", [])
        print(f"📍 {len(stations)} stations trouvées dans la bbox IDF\n")

        # 2. Pour chaque station, vérifier qu'elle retourne des données fraîches
        validated = []
        for station in stations:
            uid = station.get("uid")
            if uid is None:
                continue

            try:
                feed_response = await client.get(
                    AQICN_FEED_URL.format(station_id=uid),
                    params={"token": settings.aqicn_token},
                )
                feed_data = feed_response.json()

                if feed_data.get("status") != "ok":
                    continue

                feed = feed_data.get("data", {})
                aqi = feed.get("aqi")
                if aqi == "-" or aqi is None:
                    continue  # station sans données

                city = feed.get("city", {})
                geo = city.get("geo", [None, None])

                validated.append({
                    "uid": f"@{uid}",
                    "name": city.get("name", "?"),
                    "latitude": geo[0],
                    "longitude": geo[1],
                    "aqi": aqi,
                    "attribution": (feed.get("attributions") or [{}])[0].get(
                        "name", "?"
                    ),
                })
            except (httpx.HTTPError, KeyError, IndexError):
                continue

    return validated


def display_stations(stations: list[dict[str, object]]) -> None:
    """Affiche un tableau formaté des stations validées."""
    if not stations:
        print("Aucune station active trouvée.")
        return

    # Tri par latitude puis longitude pour faciliter la sélection géographique
    def _sort_key(s: dict[str, object]) -> tuple[float, float]:
        lat = s["latitude"] if isinstance(s["latitude"], (int, float)) else 0.0
        lon = s["longitude"] if isinstance(s["longitude"], (int, float)) else 0.0
        return (float(lat), float(lon))

    stations.sort(key=_sort_key)

    print(f"{'ID':<10} {'Nom':<45} {'Lat':>8} {'Lon':>8} {'AQI':>4}  Source")
    print("-" * 110)
    for s in stations:
        lat_val = s["latitude"]
        lon_val = s["longitude"]
        lat = f"{float(lat_val):.4f}" if isinstance(lat_val, (int, float)) else "?"
        lon = f"{float(lon_val):.4f}" if isinstance(lon_val, (int, float)) else "?"
        name = str(s["name"] or "?")[:43]
        attribution = str(s["attribution"] or "?")[:40]
        print(
            f"{s['uid']!s:<10} {name:<45} {lat:>8} {lon:>8} "
            f"{s['aqi']!s:>4}  {attribution}"
        )

    print()
    print("💡 Pour utiliser ces stations, mets à jour DEFAULT_AQICN_STATIONS")
    print("   dans services/ingestion/src/ingestion/cli.py")


def main() -> None:
    stations = asyncio.run(discover_stations())
    display_stations(stations)


if __name__ == "__main__":
    main()
