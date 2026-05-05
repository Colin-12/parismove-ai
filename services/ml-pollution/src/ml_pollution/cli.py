"""CLI du service ml-pollution.

Commandes :
    * train     — Entraîne le modèle global et le persiste
    * evaluate  — Affiche les métriques du modèle persisté
    * predict   — Prédit le PM2.5 H+1 pour une station
"""
from __future__ import annotations

import json
import sys

import click
import structlog
from shared.db import create_database_engine

from ml_pollution.config import get_model_dir, get_settings
from ml_pollution.persistence import load_model, model_exists, save_model
from ml_pollution.predict import predict_next_hour
from ml_pollution.train import train_model

logger = structlog.get_logger(__name__)


@click.group()
def cli() -> None:
    """Service ml-pollution : entraîne et utilise le modèle PM2.5."""


@cli.command(name="train")
@click.option("--days", default=30, show_default=True, help="Fenêtre temporelle d'entraînement")
@click.option("--test-ratio", default=0.2, show_default=True)
@click.option("--n-estimators", default=200, show_default=True)
@click.option("--max-depth", default=5, show_default=True)
@click.option("--learning-rate", default=0.1, show_default=True)
def train_cmd(
    days: int,
    test_ratio: float,
    n_estimators: int,
    max_depth: int,
    learning_rate: float,
) -> None:
    """Entraîne le modèle XGBoost sur les données récentes."""
    settings = get_settings()
    if not settings.database_url:
        click.echo("❌ DATABASE_URL n'est pas configurée dans .env", err=True)
        sys.exit(1)

    engine = create_database_engine(settings.database_url)

    try:
        result = train_model(
            engine=engine,
            days=days,
            test_ratio=test_ratio,
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
        )
    except ValueError as exc:
        click.echo(f"❌ {exc}", err=True)
        sys.exit(2)

    model_dir = get_model_dir()
    model_path, meta_path = save_model(
        result.model, model_dir, result.metadata
    )

    click.echo("")
    click.echo("=" * 60)
    click.echo("  Modèle entraîné avec succès")
    click.echo("=" * 60)
    click.echo(f"  Modèle    : {model_path}")
    click.echo(f"  Métadata  : {meta_path}")
    click.echo("")
    click.echo("  Métriques sur le set de test :")
    click.echo(f"  - MAE      : {result.metrics.mae:.2f} µg/m³")
    click.echo(f"  - RMSE     : {result.metrics.rmse:.2f} µg/m³")
    click.echo(f"  - n_train  : {result.metrics.n_train}")
    click.echo(f"  - n_test   : {result.metrics.n_test}")
    click.echo(f"  - stations : {result.metrics.n_stations}")
    click.echo("")


@cli.command(name="evaluate")
def evaluate_cmd() -> None:
    """Affiche les métriques du dernier modèle entraîné."""
    model_dir = get_model_dir()
    if not model_exists(model_dir):
        click.echo("❌ Aucun modèle entraîné. Lance `ml-pollution train` d'abord.", err=True)
        sys.exit(1)

    _model, metadata = load_model(model_dir)
    click.echo("")
    click.echo("=" * 60)
    click.echo("  Modèle persisté")
    click.echo("=" * 60)
    click.echo(json.dumps(metadata, indent=2, default=str))


@cli.command(name="predict")
@click.argument("station_id")
def predict_cmd(station_id: str) -> None:
    """Prédit la concentration PM2.5 H+1 pour une station Airparif.

    Exemple : ml-pollution predict @5722
    """
    settings = get_settings()
    if not settings.database_url:
        click.echo("❌ DATABASE_URL n'est pas configurée dans .env", err=True)
        sys.exit(1)

    engine = create_database_engine(settings.database_url)
    model_dir = get_model_dir()

    if not model_exists(model_dir):
        click.echo("❌ Aucun modèle entraîné. Lance `ml-pollution train` d'abord.", err=True)
        sys.exit(1)

    try:
        prediction = predict_next_hour(engine, model_dir, station_id)
    except (FileNotFoundError, ValueError) as exc:
        click.echo(f"❌ {exc}", err=True)
        sys.exit(2)

    click.echo("")
    click.echo("=" * 60)
    click.echo(f"  Prédiction PM2.5 — {prediction.station_name}")
    click.echo("=" * 60)
    click.echo(f"  Station        : {prediction.station_id}")
    click.echo(
        f"  Dernière mesure: {prediction.last_observed_pm25:.1f} µg/m³"
    )
    click.echo(f"  Mesurée le     : {prediction.last_observed_at}")
    click.echo("")
    click.echo(
        f"  Prédit pour {prediction.target_dt.strftime('%Y-%m-%d %H:%M')} : "
        f"{prediction.predicted_pm25:.1f} µg/m³"
    )
    click.echo("")


if __name__ == "__main__":
    cli()
