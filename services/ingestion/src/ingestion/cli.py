"""CLI pour lancer les jobs d'ingestion.

Usage:
    python -m ingestion.cli run --source prim
    python -m ingestion.cli run --source prim --stop STIF:StopPoint:Q:41136:
    python -m ingestion.cli run --source prim --mock
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

import click

from ingestion.clients.prim import PrimClient
from ingestion.config import get_settings
from ingestion.transformers.prim_transformer import parse_stop_monitoring_response

logger = logging.getLogger(__name__)

# Quelques arrêts clés pour les tests rapides (Paris centre)
DEFAULT_STOPS = [
    "STIF:StopPoint:Q:41136:",  # Châtelet-Les Halles RER
    "STIF:StopPoint:Q:41084:",  # Gare du Nord RER
]

FIXTURES_DIR = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures"
)


async def _run_prim(stop_ids: list[str], use_mock: bool) -> None:
    """Récupère les prochains passages pour une liste d'arrêts."""
    if use_mock:
        click.echo("Mode mock : lecture depuis la fixture locale.")
        fixture = FIXTURES_DIR / "prim_stop_monitoring.json"
        with fixture.open(encoding="utf-8") as f:
            raw = json.load(f)
        visits = parse_stop_monitoring_response(raw)
        _display(visits)
        return

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
            visits = await client.get_stop_monitoring(stop_id)
            _display(visits)


def _display(visits: list) -> None:
    """Affiche les passages de manière lisible dans le terminal."""
    if not visits:
        click.echo("  Aucun passage annoncé.")
        return

    for v in visits:
        delay = v.delay_seconds
        if delay is None:
            status = "?"
        elif delay > 60:
            status = f"+{delay // 60} min"
        elif delay < -60:
            status = f"{delay // 60} min"
        else:
            status = "à l'heure"

        expected = (
            v.expected_arrival.strftime("%H:%M")
            if v.expected_arrival
            else "?"
        )
        click.echo(
            f"  {expected}  {v.transport_mode.value:6} "
            f"{v.line_name or '?':8}  → {v.direction or '?':40}  [{status}]"
        )


@click.group()
@click.option("--log-level", default="INFO", help="Niveau de log")
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
@click.option(
    "--stop",
    "stops",
    multiple=True,
    help="ID d'arrêt PRIM (répétable). Par défaut : quelques arrêts Paris centre.",
)
@click.option(
    "--mock",
    is_flag=True,
    help="Utilise une fixture locale au lieu d'appeler l'API (dev / démo).",
)
def run(source: str, stops: tuple[str, ...], mock: bool) -> None:
    """Exécute un job d'ingestion."""
    if source == "prim":
        stop_ids = list(stops) if stops else DEFAULT_STOPS
        asyncio.run(_run_prim(stop_ids, use_mock=mock))
    elif source in {"aqicn", "meteo", "all"}:
        click.echo(f"Source '{source}' : à implémenter.")
        sys.exit(2)


if __name__ == "__main__":
    main()
