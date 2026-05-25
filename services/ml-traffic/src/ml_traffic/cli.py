"""Point d'entrée CLI du service ml-traffic.

Usage :
    python -m ml_traffic.cli train           # Entraîne baseline logistique
    python -m ml_traffic.cli train-xgb       # Entraîne XGBoost
    python -m ml_traffic.cli compare         # Compare baseline vs XGBoost
    python -m ml_traffic.cli evaluate        # Évalue le modèle actif
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from sklearn.pipeline import Pipeline
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
    train_xgboost,
)

MODEL_BASELINE = "baseline_logistic.joblib"
MODEL_XGB = "xgboost.joblib"
REPORT_BASELINE = "baseline_report.md"
REPORT_XGB = "xgboost_report.md"
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
    model_name: str,
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
        f"# Rapport d'évaluation — {model_name}\n\n"
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
        f"**{model_name} bat-il le trivial ?**\n"
        f"- Sur F1 : {f1_verdict}\n"
        f"- Sur AUC : {auc_verdict}\n"
    )
    path.write_text(content, encoding="utf-8")


def _cmd_train(settings: Settings) -> int:
    """Entraîne le baseline logistique."""
    print("Préparation du dataset...")
    train, val, test = _prepare_dataset(settings)
    _print_splits(train, val, test)

    print("Entraînement régression logistique...")
    model = train_baseline(
        train[ALL_FEATURE_COLS],
        train["target"],
        random_state=settings.xgb_random_state,
    )
    return _eval_and_save(
        model, train, val, test, settings,
        model_filename=MODEL_BASELINE,
        report_filename=REPORT_BASELINE,
        model_name="baseline logistique",
    )


def _cmd_train_xgb(settings: Settings) -> int:
    """Entraîne le modèle XGBoost."""
    print("Préparation du dataset...")
    train, val, test = _prepare_dataset(settings)
    _print_splits(train, val, test)

    print("Entraînement XGBoost...")
    model = train_xgboost(
        x_train=train[ALL_FEATURE_COLS],
        y_train=train["target"],
        x_val=val[ALL_FEATURE_COLS],
        y_val=val["target"],
        n_estimators=settings.xgb_n_estimators,
        max_depth=settings.xgb_max_depth,
        learning_rate=settings.xgb_learning_rate,
        random_state=settings.xgb_random_state,
    )
    return _eval_and_save(
        model, train, val, test, settings,
        model_filename=MODEL_XGB,
        report_filename=REPORT_XGB,
        model_name="XGBoost",
    )


def _cmd_compare(settings: Settings) -> int:
    """Compare baseline vs XGBoost sur le test set courant."""
    baseline_path = settings.models_dir / MODEL_BASELINE
    xgb_path = settings.models_dir / MODEL_XGB

    if not baseline_path.exists():
        print(f"Baseline introuvable : {baseline_path}. Lance 'train' d'abord.")
        return 1
    if not xgb_path.exists():
        print(f"XGBoost introuvable : {xgb_path}. Lance 'train-xgb' d'abord.")
        return 1

    print("Préparation du dataset...")
    _, _, test = _prepare_dataset(settings)

    baseline = load_model(baseline_path)
    xgb = load_model(xgb_path)
    b_m = evaluate(baseline, test, test["target"])
    x_m = evaluate(xgb, test, test["target"])

    print("\n=== Comparaison sur le test set ===")
    print(f"{'Métrique':<12} {'Baseline':>10} {'XGBoost':>10} {'Gagnant':>10}")
    print("-" * 46)
    for name, bv, xv in [
        ("Accuracy", b_m.accuracy, x_m.accuracy),
        ("Precision", b_m.precision, x_m.precision),
        ("Recall", b_m.recall, x_m.recall),
        ("F1", b_m.f1, x_m.f1),
        ("AUC", b_m.roc_auc, x_m.roc_auc),
    ]:
        winner = "XGBoost" if xv > bv else ("Baseline" if bv > xv else "Egal")
        print(f"{name:<12} {bv:>10.4f} {xv:>10.4f} {winner:>10}")

    print(f"\nConclusion : {'XGBoost' if x_m.roc_auc > b_m.roc_auc else 'Baseline'} "
          f"gagne sur AUC ({max(x_m.roc_auc, b_m.roc_auc):.4f} vs "
          f"{min(x_m.roc_auc, b_m.roc_auc):.4f})")
    return 0


def _cmd_evaluate(settings: Settings) -> int:
    """Évalue le meilleur modèle disponible sur le test set."""
    xgb_path = settings.models_dir / MODEL_XGB
    baseline_path = settings.models_dir / MODEL_BASELINE
    path = xgb_path if xgb_path.exists() else baseline_path

    print(f"Chargement modèle : {path}")
    model = load_model(path)

    print("Préparation du dataset...")
    _, _, test = _prepare_dataset(settings)
    metrics = evaluate(model, test, test["target"])
    print(json.dumps(metrics.to_dict(), indent=2))
    return 0


def _print_splits(
    train: pd.DataFrame,
    val: pd.DataFrame,
    test: pd.DataFrame,
) -> None:
    print(f"  train : {len(train):>6} lignes ({train['target'].mean():.1%} positifs)")
    print(f"  val   : {len(val):>6} lignes ({val['target'].mean():.1%} positifs)")
    print(f"  test  : {len(test):>6} lignes ({test['target'].mean():.1%} positifs)")


def _eval_and_save(
    model: Pipeline,
    train: pd.DataFrame,
    val: pd.DataFrame,
    test: pd.DataFrame,
    settings: Settings,
    model_filename: str,
    report_filename: str,
    model_name: str,
) -> int:
    train_m = evaluate(model, train, train["target"])
    val_m = evaluate(model, val, val["target"])
    test_m = evaluate(model, test, test["target"])

    print(f"\nTest accuracy : {test_m.accuracy:.4f}")
    print(f"Test F1       : {test_m.f1:.4f}")
    print(f"Test AUC      : {test_m.roc_auc:.4f}")

    model_path = settings.models_dir / model_filename
    report_path = settings.models_dir / report_filename
    save_model(model, model_path)
    _write_report(report_path, model_name, train_m, val_m, test_m)
    print(f"\nModèle sauvegardé : {model_path}")
    print(f"Rapport sauvegardé : {report_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entrée CLI principale."""
    parser = argparse.ArgumentParser(prog="ml_traffic")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("train", help="Entraîne le baseline logistique")
    sub.add_parser("train-xgb", help="Entraîne XGBoost")
    sub.add_parser("compare", help="Compare baseline vs XGBoost sur le test set")
    sub.add_parser("evaluate", help="Évalue le meilleur modèle disponible")

    args = parser.parse_args(argv)
    settings = get_settings()

    if args.command == "train":
        return _cmd_train(settings)
    if args.command == "train-xgb":
        return _cmd_train_xgb(settings)
    if args.command == "compare":
        return _cmd_compare(settings)
    if args.command == "evaluate":
        return _cmd_evaluate(settings)
    return 1


if __name__ == "__main__":
    sys.exit(main())
