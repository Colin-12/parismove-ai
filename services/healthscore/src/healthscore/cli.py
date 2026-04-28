"""CLI pour le service healthscore.

Usage:
    # Score d'un trajet unique
    healthscore score --journey-id rer-a --label "RER A Châtelet→Défense" \\
        --point 48.8585,2.3470 --point 48.8918,2.2389

    # Comparaison de 2 trajets
    healthscore compare \\
        --journey "rer-a:RER A direct:48.8585,2.3470:48.8918,2.2389" \\
        --journey "metro-1:Métro 1 + bus:48.8585,2.3470:48.8718,2.2900:48.8918,2.2389"
"""
from __future__ import annotations

import sys

import click
from pydantic_settings import BaseSettings, SettingsConfigDict
from shared.db import create_database_engine
from shared.schemas import JourneyComparison, JourneyScore
from sqlalchemy.engine import Engine

from healthscore.compare import compare_journeys, score_journey
from healthscore.scoring import grade_color


class Settings(BaseSettings):
    """Configuration du service healthscore."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = ""


def _get_engine() -> Engine:
    settings = Settings()
    if not settings.database_url:
        click.echo("❌ DATABASE_URL manquante dans .env", err=True)
        sys.exit(1)
    return create_database_engine(settings.database_url)


def _parse_point(raw: str) -> tuple[float, float]:
    """Parse 'lat,lon' en tuple (float, float)."""
    try:
        lat_str, lon_str = raw.split(",")
        return float(lat_str.strip()), float(lon_str.strip())
    except (ValueError, AttributeError) as exc:
        raise click.BadParameter(
            f"Format attendu: 'lat,lon' (ex: 48.8566,2.3522). Reçu: {raw}"
        ) from exc


def _parse_journey_spec(raw: str) -> tuple[str, str, list[tuple[float, float]]]:
    """Parse 'id:label:lat1,lon1:lat2,lon2:...' en tuple."""
    parts = raw.split(":")
    if len(parts) < 4:
        raise click.BadParameter(
            "Format attendu: 'id:label:lat1,lon1:lat2,lon2:...' "
            "(au moins 2 waypoints)"
        )
    journey_id = parts[0]
    label = parts[1]
    waypoints = [_parse_point(p) for p in parts[2:]]
    return journey_id, label, waypoints


def _format_score_line(score: float, label: str) -> str:
    """Affiche un sub-score avec une barre visuelle."""
    bars = int(score / 5)  # 20 cases max
    bar = "█" * bars + "░" * (20 - bars)
    return f"  {label:12} {bar} {score:5.1f}/100"


def _display_journey(score: JourneyScore) -> None:
    """Affichage formaté d'un score de trajet."""
    color = grade_color(score.grade)

    click.echo(f"\n{'=' * 60}")
    click.secho(
        f"  {score.journey_label}",
        bold=True,
    )
    click.echo(f"{'=' * 60}")

    click.echo(f"  Évalué à : {score.evaluated_at.strftime('%Y-%m-%d %H:%M UTC')}")
    click.echo(f"  Waypoints : {len(score.waypoints)}")

    click.echo("\n  Sub-scores :")
    click.echo(_format_score_line(score.pollution_score, "Pollution"))
    click.echo(_format_score_line(score.weather_score, "Météo"))
    click.echo(_format_score_line(score.traffic_score, "Trafic"))

    click.echo("\n  Score global :")
    click.echo(_format_score_line(score.overall_score, "Total"))

    click.secho(
        f"\n  Grade: {score.grade.value}  ({color})",
        bold=True,
    )

    if score.warnings:
        click.echo("\n  ⚠️  Avertissements :")
        for w in score.warnings:
            click.echo(f"     • {w}")


def _display_comparison(comparison: JourneyComparison) -> None:
    click.echo("\n" + "=" * 60)
    click.secho("  COMPARAISON DE TRAJETS", bold=True)
    click.echo("=" * 60)

    # Tri par score décroissant pour afficher du meilleur au pire
    sorted_journeys = sorted(
        comparison.journeys, key=lambda j: j.overall_score, reverse=True
    )

    click.echo()
    for i, journey in enumerate(sorted_journeys, start=1):
        marker = "🏆" if journey.journey_id == comparison.best_journey_id else "  "
        click.echo(
            f"  {marker} {i}. {journey.journey_label} "
            f"→ {journey.grade.value} ({journey.overall_score:.1f}/100)"
        )

    click.echo()
    if comparison.is_significant:
        best = next(
            j for j in comparison.journeys
            if j.journey_id == comparison.best_journey_id
        )
        click.secho(
            f"  ✅ Recommandation : {best.journey_label} "
            f"(écart de {comparison.score_gap:.1f} points)",
            bold=True,
        )
    else:
        click.echo(
            f"  ⚖️  Les trajets sont équivalents "
            f"(écart de seulement {comparison.score_gap:.1f} points)."
        )

    click.echo("\n  Détail de chaque trajet :")
    for journey in sorted_journeys:
        _display_journey(journey)


@click.group()
def main() -> None:
    """ParisMove Healthscore — score santé des trajets."""


@main.command()
@click.option("--journey-id", required=True, help="ID logique du trajet")
@click.option("--label", required=True, help="Label lisible du trajet")
@click.option(
    "--point",
    "points",
    multiple=True,
    required=True,
    help="Waypoint au format 'lat,lon' (répétable, min 1)",
)
def score(journey_id: str, label: str, points: tuple[str, ...]) -> None:
    """Calcule le score santé d'un trajet."""
    waypoints = [_parse_point(p) for p in points]
    engine = _get_engine()
    try:
        result = score_journey(engine, journey_id, label, waypoints)
    finally:
        engine.dispose()
    _display_journey(result)


@main.command()
@click.option(
    "--journey",
    "journeys_raw",
    multiple=True,
    required=True,
    help="Spec d'un trajet (répétable, min 2). Format : 'id:label:lat1,lon1:lat2,lon2'",
)
def compare(journeys_raw: tuple[str, ...]) -> None:
    """Compare plusieurs trajets entre eux."""
    if len(journeys_raw) < 2:
        click.echo("❌ Il faut au moins 2 trajets à comparer.", err=True)
        sys.exit(1)

    journeys = [_parse_journey_spec(j) for j in journeys_raw]
    engine = _get_engine()
    try:
        comparison = compare_journeys(engine, journeys)
    finally:
        engine.dispose()
    _display_comparison(comparison)


if __name__ == "__main__":
    main()
