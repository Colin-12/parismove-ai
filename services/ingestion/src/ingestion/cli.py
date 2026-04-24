"""CLI pour lancer les jobs d'ingestion.

Usage:
    python -m ingestion.cli run --source prim
    python -m ingestion.cli run --source prim --stop STIF:StopArea:SP:71517:
    python -m ingestion.cli run --source prim --mock
    python -m ingestion.cli run --source prim --limit 10
    python -m ingestion.cli run --source prim --save-raw data/raw/
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
from shared.schemas import StopVisit

from ingestion.clients.prim import PrimClient
from ingestion.config import get_settings
from ingestion.transformers.prim_transformer import parse_stop_monitoring_response

logger = logging.getLogger(__name__)

# Arrêts bien fournis pour les tests par défaut.
# Format StopArea:SP recommandé depuis mars 2023 (cf. changements IDFM).
DEFAULT_STOPS = [
    "STIF:StopArea:SP:71517:",  # La Défense (RER A + métro 1 + bus + tram)
    "STIF:StopArea:SP:42587:",  # Châtelet (métro 1, 4, 7, 11, 14)
    "STIF:StopArea:SP:71264:",  # Châtelet - Les Halles (zone multimodale)
]

FIXTURES_DIR = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures"
)


def _save_raw_response(
    raw: dict[str, Any], stop_id: str, output_dir: Path
) -> Path:
    """Sauvegarde une réponse PRIM brute en JSON horodaté.

    Utile pour enrichir les fixtures de tests avec de vraies réponses.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_stop = stop_id.replace(":", "_").strip("_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"prim_{safe_stop}_{timestamp}.json"
    path = output_dir / filename
    path.write_text(
        json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return path


async def _run_prim(
    stop_ids: list[str],
    use_mock: bool,
    limit: int | None,
    save_raw: Path | None,
) -> None:
    """Récupère les prochains passages pour une liste d'arrêts."""
    if use_mock:
        click.echo("Mode mock : lecture depuis la fixture locale.")
        fixture = FIXTURES_DIR / "prim_stop_monitoring.json"
        with fixture.open(encoding="utf-8") as f:
            raw = json.load(f)
        visits = parse_stop_monitoring_response(raw)
        _display(visits, limit)
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
            try:
                if save_raw is not None:
                    # On récupère la réponse brute pour pouvoir la sauvegarder
                    raw = await _fetch_raw(client, stop_id)
                    saved_path = _save_raw_response(raw, stop_id, save_raw)
                    click.echo(f"  Réponse brute sauvegardée : {saved_path}")
                    visits = parse_stop_monitoring_response(raw)
                else:
                    visits = await client.get_stop_monitoring(stop_id)
                _display(visits, limit)
            except httpx.HTTPError as exc:
                click.echo(f"  ❌ Erreur réseau : {exc}", err=True)


async def _fetch_raw(client: PrimClient, stop_id: str) -> dict[str, Any]:
    """Version bas-niveau qui retourne le JSON brut, utilisée pour --save-raw."""
    return await client._fetch(
        client.STOP_MONITORING_PATH, {"MonitoringRef": stop_id}
    )


def _format_delay(delay: int | None) -> str:
    """Formate un retard en secondes de manière lisible."""
    if delay is None:
        return "?"
    if delay > 60:
        return f"+{delay // 60} min"
    if delay < -60:
        return f"{delay // 60} min"
    return "à l'heure"


def _display(visits: list[StopVisit], limit: int | None) -> None:
    """Affiche les passages de manière lisible dans le terminal."""
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
@click.option(
    "--limit",
    type=int,
    default=15,
    help="Nombre maximum de passages à afficher par arrêt (0 = tous).",
)
@click.option(
    "--save-raw",
    type=click.Path(path_type=Path),
    default=None,
    help="Sauvegarde les réponses brutes JSON dans le dossier indiqué.",
)
def run(
    source: str,
    stops: tuple[str, ...],
    mock: bool,
    limit: int,
    save_raw: Path | None,
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
            )
        )
    elif source in {"aqicn", "meteo", "all"}:
        click.echo(f"Source '{source}' : à implémenter.")
        sys.exit(2)


if __name__ == "__main__":
    main()
