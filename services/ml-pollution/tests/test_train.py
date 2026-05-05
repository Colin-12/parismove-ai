"""Tests de la logique de split et training."""
from __future__ import annotations

import pandas as pd

from ml_pollution.train import chronological_split


class TestChronologicalSplit:
    def test_empty_input(self) -> None:
        df = pd.DataFrame()
        train, test = chronological_split(df)
        assert train.empty
        assert test.empty

    def test_split_ratio_default(self) -> None:
        df = pd.DataFrame({"x": list(range(100))})
        train, test = chronological_split(df, test_ratio=0.2)
        assert len(train) == 80
        assert len(test) == 20

    def test_split_preserves_order(self) -> None:
        df = pd.DataFrame({"x": list(range(100))})
        train, test = chronological_split(df, test_ratio=0.2)
        # Le test set doit être les valeurs LES PLUS RÉCENTES (la fin)
        assert test["x"].min() == 80
        assert test["x"].max() == 99
        assert train["x"].min() == 0
        assert train["x"].max() == 79

    def test_small_dataset_at_least_one_test(self) -> None:
        # Avec peu de data, on garde au moins 1 ligne pour le test
        df = pd.DataFrame({"x": [1, 2, 3]})
        _train, test = chronological_split(df, test_ratio=0.2)
        assert len(test) >= 1
