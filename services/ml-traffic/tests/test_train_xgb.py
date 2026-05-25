"""Tests du modèle XGBoost."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from ml_traffic.train import (
    ALL_FEATURE_COLS,
    build_xgb_pipeline,
    evaluate,
    save_model,
    split_chronological,
    train_baseline,
    train_xgboost,
)


def _synthetic_dataset(n: int = 600, seed: int = 0) -> pd.DataFrame:
    """Dataset synthétique avec signal bus + heures de pointe."""
    rng = np.random.default_rng(seed)
    base = datetime(2026, 5, 1, tzinfo=UTC)
    rows = []
    for i in range(n):
        ts = base + timedelta(hours=i)
        mode = rng.choice(["bus", "rail"], p=[0.5, 0.5])
        hour = ts.hour
        is_peak = hour in (8, 9, 17, 18)
        p_disrupt = 0.85 if (mode == "bus" and is_peak) else 0.10
        rows.append(
            {
                "line_id": rng.choice(["A", "B", "C"]),
                "mode": mode,
                "hour_slot": ts,
                "hour": hour,
                "dow": ts.weekday(),
                "target": bool(rng.random() < p_disrupt),
            }
        )
    return pd.DataFrame(rows)


def test_build_xgb_pipeline_structure() -> None:
    pipeline = build_xgb_pipeline()
    assert "preprocessor" in pipeline.named_steps
    assert "classifier" in pipeline.named_steps
    clf = pipeline.named_steps["classifier"]
    assert clf.__class__.__name__ == "XGBClassifier"


def test_train_xgboost_learns_signal() -> None:
    """XGBoost doit atteindre AUC > 0.65 sur un signal apprenable."""
    df = _synthetic_dataset(n=1500, seed=42)
    train, val, test = split_chronological(df, train_ratio=0.7, val_ratio=0.15)
    model = train_xgboost(
        x_train=train[ALL_FEATURE_COLS],
        y_train=train["target"],
        x_val=val[ALL_FEATURE_COLS],
        y_val=val["target"],
    )
    metrics = evaluate(model, test, test["target"])
    assert metrics.roc_auc > 0.65, f"AUC trop faible : {metrics.roc_auc:.3f}"
    assert metrics.f1 > 0


def test_xgb_vs_baseline_on_same_split() -> None:
    """XGBoost doit avoir AUC >= baseline - 0.05 sur le même dataset."""
    df = _synthetic_dataset(n=1500, seed=7)
    train, val, test = split_chronological(df, train_ratio=0.7, val_ratio=0.15)

    baseline = train_baseline(train[ALL_FEATURE_COLS], train["target"])
    xgb = train_xgboost(
        x_train=train[ALL_FEATURE_COLS],
        y_train=train["target"],
        x_val=val[ALL_FEATURE_COLS],
        y_val=val["target"],
    )

    b_metrics = evaluate(baseline, test, test["target"])
    x_metrics = evaluate(xgb, test, test["target"])

    assert x_metrics.roc_auc >= b_metrics.roc_auc - 0.05, (
        f"XGBoost AUC ({x_metrics.roc_auc:.3f}) "
        f"bien inférieur au baseline ({b_metrics.roc_auc:.3f})"
    )


def test_save_xgb_model(tmp_path: Path) -> None:
    df = _synthetic_dataset(n=300)
    train, val, _ = split_chronological(df, train_ratio=0.7, val_ratio=0.15)
    model = train_xgboost(
        x_train=train[ALL_FEATURE_COLS],
        y_train=train["target"],
        x_val=val[ALL_FEATURE_COLS],
        y_val=val["target"],
    )
    out = tmp_path / "xgb.joblib"
    save_model(model, out)
    assert out.exists()
    assert out.stat().st_size > 0
