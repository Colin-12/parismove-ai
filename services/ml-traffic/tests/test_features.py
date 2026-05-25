"""Tests features — placeholders, à compléter dans la PR baseline."""
from __future__ import annotations

import pytest

from ml_traffic.features import (
    aggregate_hourly_by_line,
    build_features,
    build_target,
)


def test_aggregate_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        aggregate_hourly_by_line(None)  # type: ignore[arg-type]


def test_build_target_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        build_target(None, 60, 120, 2, 1)  # type: ignore[arg-type]


def test_build_features_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        build_features(None)  # type: ignore[arg-type]
