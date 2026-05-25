"""Tests de la couche data — placeholders, à compléter dans la PR baseline."""
from __future__ import annotations

import pytest

from ml_traffic.data import clean_outliers, filter_eligible_lines, load_stop_visits


def test_load_stop_visits_not_implemented() -> None:
    """Confirme que la fonction lève NotImplementedError tant que non implémentée."""
    with pytest.raises(NotImplementedError):
        load_stop_visits(None)  # type: ignore[arg-type]


def test_filter_eligible_lines_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        filter_eligible_lines(None, 200)  # type: ignore[arg-type]


def test_clean_outliers_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        clean_outliers(None, -1800, 3600)  # type: ignore[arg-type]
