"""CLI pour lancer les jobs d'ingestion.

Usage:
    python -m ingestion.cli run --source prim
    python -m ingestion.cli run --source prim --stop STIF:StopArea:SP:71517:
    python -m ingestion.cli run --source prim --mock
    python -m ingestion.cli run --source prim --limit 10
    python -m ingestion.cli run --source prim --save-raw data/raw/
    python -m ingestion.cli run --source prim --store
    python -m ingestion.cli run --source aqicn --store
    python -m ingestion.cli run --source aqicn --station @5722
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
from shared.schemas import AirMeasurement, StopVisit

from ingestion.clients.aqicn import AqicnClient
from ingestion.clients.prim import PrimClient
from ingestion.config import get_settings
from ingestion.loaders import load_air_measurements, load_stop_visits
from ingestion.transformers.prim_transformer import parse_stop_monitoring_response

logger = logging.getLogger(__name__)

DEFAULT_STOPS = [
    # Hubs majeurs Paris intra-muros
    "STIF:StopArea:SP:71517:",  # La Défense (RER A + M1 + T2 + bus)
    "STIF:StopArea:SP:42587:",  # Châtelet (M1, M4, M7, M11, M14)
    "STIF:StopArea:SP:71264:",  # Châtelet - Les Halles (multimodal)
    "STIF:StopArea:SP:43135:",  # Gare du Nord (RER B/D + Eurostar + Transilien)
    "STIF:StopArea:SP:43136:",  # Gare Saint-Lazare (Transilien J/L)
    "STIF:StopArea:SP:43122:",  # Gare de Lyon (RER A/D + Transilien)
    "STIF:StopArea:SP:43124:",  # Montparnasse (Transilien N + métros)
    "STIF:StopArea:SP:71061:",  # Nation (M1, M2, M6, M9 + RER A)
    # Banlieue significative pour la diversité ML
    "STIF:StopArea:SP:43185:",  # Versailles Château Rive Gauche (RER C)
    "STIF:StopArea:SP:411160:", # Saint-Denis (RER B/D + T1 + T8)
]

# Stations AQICN par défaut. IDs vérifiés via aqicn.org/city/<slug>.
# 4 zones distinctes pour avoir une diversité spatiale (centre, ouest, nord, sud-ouest).
DEFAULT_AQICN_STATIONS = [
    "@5722",   # Paris 18e (Aubervilliers) - zone Nord
    "@5724",   # Paris centre (Les Halles)
    "@13109",  # La Défense - zone Ouest business
    "@5708",   # Versailles - zone banlieue résidentielle
]

FIXTURES_DIR = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures"
)


def _save_raw_response(
    raw: dict[str, Any], stop_id: str, output_dir: Path
) -> Path:
    """Sauvegarde une réponse PRIM brute en JSON horodaté."""
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
    """Récupère les prochains passages pour une liste d'arrêts."""
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
    """Récupère la qualité de l'air pour une liste de stations."""
    settings = get_settings()
    if not settings.aqicn_token:
        click.echo(
            "❌ AQICN_TOKEN manquant. Renseigne-le dans .env "
            "(token gratuit sur https://aqicn.org/data-platform/token/).",
            err=True,
        )
        sys.exit(1)

    measurements: list[AirMeasurement] = []

    async with AqicnClient(token=settings.aqicn_token) as client:
        for station_id in stations:
            click.echo(f"\n→ Station {station_id}")
            try:
                m = await client.get_station(station_id)
                if m is None:
                    click.echo("  Données indisponibles ou dégradées.")
                    continue
                _display_measurement(m)
                measurements.append(m)
            except httpx.HTTPError as exc:
                click.echo(f"  ❌ Erreur réseau : {exc}", err=True)

    if store and measurements:
        _store_measurements(measurements)


def _display_measurement(m: AirMeasurement) -> None:
    """Affiche une mesure de qualité de l'air dans le terminal."""
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
@click.option("--mock", is_flag=True, help="Utilise une fixture locale (PRIM uniquement).")
@click.option("--limit", type=int, default=15, help="Nb max de passages affichés (PRIM).")
@click.option(
    "--save-raw",
    type=click.Path(path_type=Path),
    default=None,
    help="Sauvegarde les réponses brutes dans ce dossier (PRIM uniquement).",
)
@click.option(
    "--store",
    is_flag=True,
    help="Stocke les données captées dans la BDD (DATABASE_URL requise).",
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
    """Exécute un job d'ingestion."""
    display_limit = None if limit == 0 else limit

    if source == "prim":
        stop_ids = list(stops) if stops else DEFAULT_STOPS
        asyncio.run(
            _run_prim(
                stop_ids,
                use_mock=mock,
                limit=display_limit,
                save_raw=save_raw,
                store=store,
            )
        )
    elif source == "aqicn":
        station_ids = list(stations) if stations else DEFAULT_AQICN_STATIONS
        asyncio.run(_run_aqicn(station_ids, store=store))
    elif source == "all":
        # Lance PRIM puis AQICN dans la foulée
        stop_ids = list(stops) if stops else DEFAULT_STOPS
        station_ids = list(stations) if stations else DEFAULT_AQICN_STATIONS
        asyncio.run(
            _run_prim(
                stop_ids,
                use_mock=mock,
                limit=display_limit,
                save_raw=save_raw,
                store=store,
            )
        )
        asyncio.run(_run_aqicn(station_ids, store=store))
    elif source == "meteo":
        click.echo("Source 'meteo' : à implémenter dans une prochaine PR.")
        sys.exit(2)


if __name__ == "__main__":
    main()
