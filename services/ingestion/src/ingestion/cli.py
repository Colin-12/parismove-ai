"""CLI pour lancer les jobs d'ingestion.

Usage:
    python -m ingestion.cli run --source prim --store
    python -m ingestion.cli run --source aqicn --store
    python -m ingestion.cli run --source meteo --store
    python -m ingestion.cli run --source all --store
    python -m ingestion.cli refresh-references
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import click
import httpx
from shared.db import create_database_engine
from shared.schemas import AirMeasurement, StopVisit, WeatherObservation

from ingestion.clients.aqicn import AqicnClient
from ingestion.clients.meteo import OpenMeteoClient
from ingestion.clients.prim import PrimClient
from ingestion.config import get_settings
from ingestion.loaders import (
    load_air_measurements,
    load_stop_visits,
    load_weather_observations,
)
from ingestion.reference import fetch_idfm_lines, upsert_idfm_lines
from ingestion.transformers.prim_transformer import parse_stop_monitoring_response

logger = logging.getLogger(__name__)

DEFAULT_STOPS = [
    "STIF:StopArea:SP:71517:",  # La Défense
    "STIF:StopArea:SP:42587:",  # Châtelet
    "STIF:StopArea:SP:71264:",  # Châtelet - Les Halles
    "STIF:StopArea:SP:43135:",  # Gare du Nord
    "STIF:StopArea:SP:43136:",  # Gare Saint-Lazare
    "STIF:StopArea:SP:43122:",  # Gare de Lyon
    "STIF:StopArea:SP:43124:",  # Montparnasse
    "STIF:StopArea:SP:71061:",  # Nation
    "STIF:StopArea:SP:43185:",  # Versailles Château Rive Gauche
    "STIF:StopArea:SP:411160:", # Saint-Denis
]

# Stations AQICN vérifiées dans la bounding box IDF.
# Sélection couvrant Paris intra-muros + petite couronne.
# Les IDs ont été obtenus via l'API map/bounds AQICN
# (voir scripts/discover_aqicn_stations.py).
#
# Stations AQICN vérifiées en IDF (réseau Airparif officiel).
# Sélectionnées via scripts/discover_aqicn_stations.py pour offrir une
# bonne couverture géographique : centre + 4 cardinaux + grande couronne.
# Si une station devient inactive, le tool aqicn renverra
# "Données indisponibles" et le run continuera avec les autres.
DEFAULT_AQICN_STATIONS = [
    "@5722",   # Paris (Place de l'Opéra) — centre ville historique
    "@12763",  # Paris 1er Les Halles — centre intra-muros
    "@3082",   # Paris 18ème — nord intra-muros
    "@3097",   # La Défense — pôle économique ouest
    "@3085",   # Gennevilliers — nord-ouest périphérique
    "@3099",   # Bobigny — nord-est
    "@3103",   # Vitry-sur-Seine — sud
    "@3104",   # Cergy-Pontoise — grande couronne nord-ouest
]

DEFAULT_METEO_POINTS: list[tuple[str, str, float, float]] = [
    ("paris-centre",    "Paris centre (Châtelet)",  48.8566, 2.3522),
    ("la-defense",      "La Défense",                48.8918, 2.2389),
    ("saint-denis",     "Saint-Denis",               48.9362, 2.3574),
    ("versailles",      "Versailles",                48.8044, 2.1232),
    ("creteil",         "Créteil",                   48.7800, 2.4655),
    ("boulogne",        "Boulogne-Billancourt",      48.8350, 2.2410),
    ("vitry",           "Vitry-sur-Seine",           48.7872, 2.4023),
    ("argenteuil",      "Argenteuil",                48.9472, 2.2498),
    ("cergy",           "Cergy (grande couronne O)", 49.0388, 2.0780),
    ("melun",           "Melun (grande couronne SE)",48.5403, 2.6605),
]

FIXTURES_DIR = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures"
)


def _save_raw_response(
    raw: dict[str, Any], stop_id: str, output_dir: Path
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_stop = stop_id.replace(":", "_").strip("_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"prim_{safe_stop}_{timestamp}.json"
    path = output_dir / filename
    path.write_text(
        json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return path


# ============================================================
# PRIM
# ============================================================


async def _run_prim(
    stop_ids: list[str],
    use_mock: bool,
    limit: int | None,
    save_raw: Path | None,
    store: bool,
) -> None:
    all_visits: list[StopVisit] = []

    if use_mock:
        click.echo("Mode mock : lecture depuis la fixture locale.")
        fixture = FIXTURES_DIR / "prim_stop_monitoring.json"
        with fixture.open(encoding="utf-8") as f:
            raw = json.load(f)
        visits = parse_stop_monitoring_response(raw)
        _display_visits(visits, limit)
        all_visits.extend(visits)
    else:
        settings = get_settings()
        if not settings.prim_api_key:
            click.echo(
                "❌ PRIM_API_KEY manquante. Renseigne-la dans .env ou "
                "utilise --mock pour tester hors ligne.",
                err=True,
            )
            sys.exit(1)

        async with PrimClient(
            api_key=settings.prim_api_key,
            base_url=str(settings.prim_base_url),
        ) as client:
            for stop_id in stop_ids:
                click.echo(f"\n→ Arrêt {stop_id}")
                try:
                    if save_raw is not None:
                        raw = await _fetch_raw_prim(client, stop_id)
                        saved_path = _save_raw_response(raw, stop_id, save_raw)
                        click.echo(f"  Réponse brute sauvegardée : {saved_path}")
                        visits = parse_stop_monitoring_response(raw)
                    else:
                        visits = await client.get_stop_monitoring(stop_id)
                    _display_visits(visits, limit)
                    all_visits.extend(visits)
                except httpx.HTTPError as exc:
                    click.echo(f"  ❌ Erreur réseau : {exc}", err=True)

    if store and all_visits:
        _store_visits(all_visits)


async def _fetch_raw_prim(client: PrimClient, stop_id: str) -> dict[str, Any]:
    return await client._fetch(
        client.STOP_MONITORING_PATH, {"MonitoringRef": stop_id}
    )


def _store_visits(visits: list[StopVisit]) -> None:
    settings = get_settings()
    if not settings.database_url:
        click.echo("❌ DATABASE_URL manquante.", err=True)
        sys.exit(1)

    click.echo(f"\n💾 Stockage de {len(visits)} passages en base...")
    engine = create_database_engine(settings.database_url)
    try:
        result = load_stop_visits(engine, visits)
    finally:
        engine.dispose()

    click.echo(
        f"   {result['inserted']} nouveaux passages insérés "
        f"({result['total'] - result['inserted']} doublons ignorés)."
    )


def _format_delay(delay: int | None) -> str:
    if delay is None:
        return "?"
    if delay > 60:
        return f"+{delay // 60} min"
    if delay < -60:
        return f"{delay // 60} min"
    return "à l'heure"


def _display_visits(visits: list[StopVisit], limit: int | None) -> None:
    if not visits:
        click.echo("  Aucun passage annoncé.")
        return

    shown = visits if limit is None else visits[:limit]
    click.echo(f"  {len(shown)} / {len(visits)} passages affichés\n")

    for v in shown:
        when = v.best_time.strftime("%H:%M") if v.best_time else "  ?  "
        mode = v.transport_mode.value
        line = v.line_name or "?"
        direction = (v.direction or "?")[:40]
        status = _format_delay(v.delay_seconds)
        operator = f" ({v.operator})" if v.operator else ""

        click.echo(
            f"  {when}  {mode:7} {line:8} → {direction:40} [{status}]{operator}"
        )


# ============================================================
# AQICN
# ============================================================


async def _run_aqicn(stations: list[str], store: bool) -> None:
    settings = get_settings()
    if not settings.aqicn_token:
        click.echo("❌ AQICN_TOKEN manquant.", err=True)
        sys.exit(1)

    measurements: list[AirMeasurement] = []

    async with AqicnClient(token=settings.aqicn_token) as client:
        for station_id in stations:
            click.echo(f"\n→ Station {station_id}")
            try:
                m = await client.get_station(station_id)
                if m is None:
                    click.echo("  Données indisponibles.")
                    continue

                # Vérification post-fetch : la station retournée est-elle bien
                # en Île-de-France ? (lat 48-50, lon 1.5-3.5).
                # Cette protection évite que des IDs invalides ramènent par
                # erreur des stations à l'autre bout du monde.
                if not _is_in_idf(m.latitude, m.longitude):
                    click.echo(
                        f"  ⚠️  Station hors IDF ignorée : "
                        f"{m.station_name} ({m.latitude:.4f}, {m.longitude:.4f})"
                    )
                    continue

                _display_measurement(m)
                measurements.append(m)
            except httpx.HTTPError as exc:
                click.echo(f"  ❌ Erreur réseau : {exc}", err=True)

    if store and measurements:
        _store_measurements(measurements)


def _is_in_idf(lat: float | None, lon: float | None) -> bool:
    """Vérifie qu'une coordonnée GPS est bien en Île-de-France.

    Bounding box IDF étendue : 48-50°N, 1.5-3.5°E.
    """
    if lat is None or lon is None:
        return False
    return 48.0 <= lat <= 50.0 and 1.5 <= lon <= 3.5


def _display_measurement(m: AirMeasurement) -> None:
    pollutants = []
    if m.pm25 is not None:
        pollutants.append(f"PM2.5={m.pm25:.0f}")
    if m.pm10 is not None:
        pollutants.append(f"PM10={m.pm10:.0f}")
    if m.no2 is not None:
        pollutants.append(f"NO2={m.no2:.0f}")
    if m.o3 is not None:
        pollutants.append(f"O3={m.o3:.0f}")

    pollutants_str = " ".join(pollutants) if pollutants else "—"
    weather = []
    if m.temperature_c is not None:
        weather.append(f"{m.temperature_c:.0f}°C")
    if m.humidity_pct is not None:
        weather.append(f"{m.humidity_pct:.0f}%RH")
    weather_str = f" [{' '.join(weather)}]" if weather else ""

    click.echo(
        f"  {m.station_name[:30]:30} AQI={m.aqi or '?':>3} "
        f"({m.aqi_category}) {pollutants_str}{weather_str}"
    )
    if m.attribution:
        click.echo(f"     source: {m.attribution}")


def _store_measurements(measurements: list[AirMeasurement]) -> None:
    settings = get_settings()
    if not settings.database_url:
        click.echo("❌ DATABASE_URL manquante.", err=True)
        sys.exit(1)

    click.echo(f"\n💾 Stockage de {len(measurements)} mesures en base...")
    engine = create_database_engine(settings.database_url)
    try:
        result = load_air_measurements(engine, measurements)
    finally:
        engine.dispose()

    click.echo(
        f"   {result['inserted']} nouvelles mesures insérées "
        f"({result['total'] - result['inserted']} doublons ignorés)."
    )


# ============================================================
# Open-Meteo
# ============================================================


async def _run_meteo(
    points: list[tuple[str, str, float, float]], store: bool
) -> None:
    observations: list[WeatherObservation] = []

    async with OpenMeteoClient() as client:
        for point_id, point_name, lat, lon in points:
            click.echo(f"\n→ Point {point_name} ({lat:.4f}, {lon:.4f})")
            try:
                obs = await client.get_observation(lat, lon, point_id, point_name)
                if obs is None:
                    click.echo("  Données indisponibles.")
                    continue
                _display_observation(obs)
                observations.append(obs)
            except httpx.HTTPError as exc:
                click.echo(f"  ❌ Erreur réseau : {exc}", err=True)

    if store and observations:
        _store_observations(observations)


def _display_observation(obs: WeatherObservation) -> None:
    parts = []
    if obs.temperature_c is not None:
        parts.append(f"{obs.temperature_c:.1f}°C")
    if obs.humidity_pct is not None:
        parts.append(f"{obs.humidity_pct:.0f}%RH")
    if obs.wind_speed_ms is not None:
        parts.append(f"vent {obs.wind_speed_ms:.1f}m/s")
    if obs.precipitation_mm is not None:
        parts.append(f"pluie {obs.precipitation_mm:.1f}mm")
    if obs.cloud_cover_pct is not None:
        parts.append(f"nuages {obs.cloud_cover_pct:.0f}%")

    click.echo(f"  météo: {' · '.join(parts) if parts else '—'}")

    air_parts = []
    if obs.aqi_european is not None:
        air_parts.append(f"EAQI {obs.aqi_european:.0f}")
    if obs.pm25 is not None:
        air_parts.append(f"PM2.5={obs.pm25:.0f}")
    if obs.no2 is not None:
        air_parts.append(f"NO2={obs.no2:.0f}")
    if obs.uv_index is not None:
        air_parts.append(f"UV {obs.uv_index:.1f}")

    if air_parts:
        click.echo(f"  air:   {' · '.join(air_parts)}")


def _store_observations(observations: list[WeatherObservation]) -> None:
    settings = get_settings()
    if not settings.database_url:
        click.echo("❌ DATABASE_URL manquante.", err=True)
        sys.exit(1)

    click.echo(f"\n💾 Stockage de {len(observations)} observations en base...")
    engine = create_database_engine(settings.database_url)
    try:
        result = load_weather_observations(engine, observations)
    finally:
        engine.dispose()

    click.echo(
        f"   {result['inserted']} nouvelles observations insérées "
        f"({result['total'] - result['inserted']} doublons ignorés)."
    )


# ============================================================
# Référentiel IDFM
# ============================================================


async def _run_refresh_references() -> None:
    """Télécharge le référentiel IDFM et le stocke en base."""
    settings = get_settings()
    if not settings.database_url:
        click.echo("❌ DATABASE_URL manquante.", err=True)
        sys.exit(1)

    click.echo("📥 Téléchargement du référentiel des lignes IDFM...")
    rows = await fetch_idfm_lines()
    click.echo(f"   {len(rows)} lignes récupérées.")

    click.echo("💾 Stockage en base (UPSERT)...")
    engine = create_database_engine(settings.database_url)
    try:
        count = upsert_idfm_lines(engine, rows)
    finally:
        engine.dispose()

    click.echo(f"   {count} lignes traitées.")

    # Affiche un échantillon pour vérifier visuellement
    sample = rows[:5]
    click.echo("\n📋 Échantillon :")
    for row in sample:
        click.echo(
            f"   {row['short_name'] or '?':10} "
            f"({row['transport_mode'] or '?':10}) "
            f"{row['long_name']}"
        )


# ============================================================
# CLI
# ============================================================


@click.group()
@click.option("--log-level", default="WARNING", help="Niveau de log")
def main(log_level: str) -> None:
    """Ingestion ParisMove AI — collecte des données ouvertes."""
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@main.command()
@click.option(
    "--source",
    type=click.Choice(["prim", "aqicn", "meteo", "all"]),
    required=True,
    help="Source à ingérer",
)
@click.option("--stop", "stops", multiple=True, help="ID d'arrêt PRIM (répétable).")
@click.option(
    "--station",
    "stations",
    multiple=True,
    help="ID de station AQICN (répétable, ex: @5722).",
)
@click.option("--mock", is_flag=True, help="Fixture locale (PRIM uniquement).")
@click.option("--limit", type=int, default=15, help="Nb max passages affichés (PRIM).")
@click.option(
    "--save-raw",
    type=click.Path(path_type=Path),
    default=None,
    help="Sauvegarde des réponses brutes (PRIM uniquement).",
)
@click.option(
    "--store",
    is_flag=True,
    help="Stocke les données captées en BDD (DATABASE_URL requise).",
)
def run(
    source: str,
    stops: tuple[str, ...],
    stations: tuple[str, ...],
    mock: bool,
    limit: int,
    save_raw: Path | None,
    store: bool,
) -> None:
    """Exécute un job d'ingestion (PRIM, AQICN, Open-Meteo)."""
    display_limit = None if limit == 0 else limit

    if source == "prim":
        stop_ids = list(stops) if stops else DEFAULT_STOPS
        asyncio.run(
            _run_prim(stop_ids, mock, display_limit, save_raw, store)
        )
    elif source == "aqicn":
        station_ids = list(stations) if stations else DEFAULT_AQICN_STATIONS
        asyncio.run(_run_aqicn(station_ids, store))
    elif source == "meteo":
        asyncio.run(_run_meteo(DEFAULT_METEO_POINTS, store))
    elif source == "all":
        stop_ids = list(stops) if stops else DEFAULT_STOPS
        station_ids = list(stations) if stations else DEFAULT_AQICN_STATIONS
        asyncio.run(_run_prim(stop_ids, mock, display_limit, save_raw, store))
        asyncio.run(_run_aqicn(station_ids, store))
        asyncio.run(_run_meteo(DEFAULT_METEO_POINTS, store))


@main.command("refresh-references")
def refresh_references() -> None:
    """Télécharge le référentiel IDFM des lignes et l'upsert en BDD.

    À exécuter ponctuellement (mensuellement, ou après changement IDFM).
    """
    asyncio.run(_run_refresh_references())


if __name__ == "__main__":
    main()
