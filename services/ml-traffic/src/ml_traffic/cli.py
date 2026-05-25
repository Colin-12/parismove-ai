"""Point d'entrée CLI du service ml-traffic.

Usage :
    python -m ml_traffic.cli train      # Entraîne et sauvegarde le modèle
    python -m ml_traffic.cli evaluate   # Évalue le modèle sauvegardé
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

from ml_traffic.config import Settings, get_settings
from ml_traffic.data import clean_outliers, filter_eligible_lines, load_stop_visits
from ml_traffic.features import aggregate_hourly_by_line, build_features, build_target
from ml_traffic.predict import load_model
from ml_traffic.train import (
    ALL_FEATURE_COLS,
    EvaluationMetrics,
    evaluate,
    save_model,
    split_chronological,
    train_baseline,
)

MODEL_FILENAME = "baseline_logistic.joblib"
REPORT_FILENAME = "baseline_report.md"
TRIVIAL_AUC_THRESHOLD = 0.5


def _prepare_dataset(settings: Settings) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    """Pipeline data complet : chargement -> nettoyage -> features -> split."""
    if not settings.database_url:
        raise RuntimeError(
            "DATABASE_URL n'est pas configurée. Renseigne-la dans .env"
        )

    engine = create_engine(settings.database_url)
    visits = load_stop_visits(engine)
    visits = clean_outliers(visits, settings.outlier_min_s, settings.outlier_max_s)
    visits = filter_eligible_lines(visits, settings.min_passages_per_line)

    agg = aggregate_hourly_by_line(visits)
    agg_targ = build_target(
        df_visits=visits,
        df_agg=agg,
        delay_threshold_s=settings.delay_threshold_s,
        severe_delay_threshold_s=settings.severe_delay_threshold_s,
        severe_count_threshold=settings.severe_count_threshold,
        horizon_hours=settings.prediction_horizon_hours,
    )
    agg_feat = build_features(agg_targ)

    train, val, test = split_chronological(
        agg_feat,
        train_ratio=settings.train_ratio,
        val_ratio=settings.val_ratio,
    )
    return train, val, test


def _format_table_row(label: str, m: EvaluationMetrics) -> str:
    """Formate une ligne du tableau Markdown de métriques."""
    return (
        f"| {label:<5} "
        f"| {m.accuracy:.4f} "
        f"| {m.precision:.4f} "
        f"| {m.recall:.4f} "
        f"| {m.f1:.4f} "
        f"| {m.roc_auc:.4f} "
        f"| {m.pct_positive:.2%} "
        f"| {m.n_samples} |"
    )


def _write_report(
    path: Path,
    train_metrics: EvaluationMetrics,
    val_metrics: EvaluationMetrics,
    test_metrics: EvaluationMetrics,
) -> None:
    """Écrit un rapport Markdown des métriques d'évaluation."""
    now = datetime.now(UTC).isoformat(timespec="seconds")
    header = (
        "| Split | Accuracy | Precision | Recall | F1 | AUC | Pos% | N |\n"
        "|-------|----------|-----------|--------|-----|-----|------|---|"
    )
    rows = "\n".join([
        _format_table_row("Train", train_metrics),
        _format_table_row("Val", val_metrics),
        _format_table_row("Test", test_metrics),
    ])
    trivial_acc = 1 - test_metrics.pct_positive
    f1_verdict = "OUI" if test_metrics.f1 > 0 else "NON"
    auc_verdict = "OUI" if test_metrics.roc_auc > TRIVIAL_AUC_THRESHOLD else "NON"

    content = (
        f"# Rapport d'évaluation — baseline logistique\n\n"
        f"Généré le {now}.\n\n"
        f"## Métriques\n\n"
        f"{header}\n{rows}\n\n"
        f"## Matrice de confusion (test)\n\n"
        f"```\n{json.dumps(test_metrics.confusion, indent=2)}\n```\n\n"
        f"## Baseline trivial à battre\n\n"
        f"Un modèle qui prédirait toujours `False` aurait :\n"
        f"- accuracy ≈ 1 - {test_metrics.pct_positive:.2%} = {trivial_acc:.4f}\n"
        f"- F1 = 0\n"
        f"- AUC = {TRIVIAL_AUC_THRESHOLD}\n\n"
        f"**Le baseline logistique bat-il le trivial ?**\n"
        f"- Sur F1 : {f1_verdict}\n"
        f"- Sur AUC : {auc_verdict}\n"
    )
    path.write_text(content, encoding="utf-8")


def _cmd_train(settings: Settings) -> int:
    """Entraîne le baseline et écrit modèle + rapport."""
    print("Préparation du dataset...")
    train, val, test = _prepare_dataset(settings)

    print(f"  train : {len(train):>6} lignes ({train['target'].mean():.1%} positifs)")
    print(f"  val   : {len(val):>6} lignes ({val['target'].mean():.1%} positifs)")
    print(f"  test  : {len(test):>6} lignes ({test['target'].mean():.1%} positifs)")

    print("Entraînement régression logistique...")
    model = train_baseline(
        train[ALL_FEATURE_COLS],
        train["target"],
        random_state=settings.xgb_random_state,
    )

    print("Évaluation...")
    train_m = evaluate(model, train, train["target"])
    val_m = evaluate(model, val, val["target"])
    test_m = evaluate(model, test, test["target"])

    print(f"\nTest accuracy : {test_m.accuracy:.4f}")
    print(f"Test F1       : {test_m.f1:.4f}")
    print(f"Test AUC      : {test_m.roc_auc:.4f}")

    model_path = settings.models_dir / MODEL_FILENAME
    report_path = settings.models_dir / REPORT_FILENAME
    save_model(model, model_path)
    _write_report(report_path, train_m, val_m, test_m)
    print(f"\nModèle sauvegardé : {model_path}")
    print(f"Rapport sauvegardé : {report_path}")
    return 0


def _cmd_evaluate(settings: Settings) -> int:
    """Évalue le modèle sauvegardé sur le test set actuel."""
    model_path = settings.models_dir / MODEL_FILENAME
    print(f"Chargement modèle : {model_path}")
    model = load_model(model_path)

    print("Préparation du dataset (recalcul des splits)...")
    _, _, test = _prepare_dataset(settings)
    metrics = evaluate(model, test, test["target"])
    print(json.dumps(metrics.to_dict(), indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entrée CLI principale."""
    parser = argparse.ArgumentParser(prog="ml_traffic")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("train", help="Entraîne et sauvegarde le modèle baseline")
    sub.add_parser("evaluate", help="Évalue le modèle baseline sauvegardé")

    args = parser.parse_args(argv)
    settings = get_settings()

    if args.command == "train":
        return _cmd_train(settings)
    if args.command == "evaluate":
        return _cmd_evaluate(settings)
    return 1


if __name__ == "__main__":
    sys.exit(main())
