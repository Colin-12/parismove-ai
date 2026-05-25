"""Tests train — placeholders, à compléter dans la PR baseline."""
from __future__ import annotations

import pytest

from ml_traffic.train import evaluate, split_chronological, train_baseline


def test_split_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        split_chronological(None, 0.70, 0.15)  # type: ignore[arg-type]


def test_train_baseline_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        train_baseline(None, None)  # type: ignore[arg-type]


def test_evaluate_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        evaluate(None, None, None)  # type: ignore[arg-type]
