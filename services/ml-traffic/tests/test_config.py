"""Tests de la couche config."""
from __future__ import annotations

from ml_traffic.config import Settings, get_settings


def test_settings_defaults() -> None:
    """Les valeurs par défaut correspondent aux décisions de l'ADR-010."""
    s = Settings()
    assert s.delay_threshold_s == 60
    assert s.severe_delay_threshold_s == 120
    assert s.severe_count_threshold == 2
    assert s.min_passages_per_line == 200
    assert s.outlier_min_s == -1800
    assert s.outlier_max_s == 3600


def test_settings_split_ratios() -> None:
    """Les ratios de split sont cohérents (70/15/15)."""
    s = Settings()
    assert s.train_ratio + s.val_ratio < 1.0  # test_ratio non-nul
    assert abs(s.train_ratio - 0.70) < 1e-9
    assert abs(s.val_ratio - 0.15) < 1e-9


def test_get_settings_cached() -> None:
    """get_settings() retourne la même instance à chaque appel."""
    a = get_settings()
    b = get_settings()
    assert a is b
