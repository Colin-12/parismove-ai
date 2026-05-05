"""Tests du module persistence (sauvegarde/chargement du modèle)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from xgboost import XGBRegressor

from ml_pollution.persistence import (
    MODEL_FILENAME,
    load_model,
    model_exists,
    save_model,
)


@pytest.fixture
def trivial_model() -> XGBRegressor:
    """Modèle XGBoost minimal entraîné sur des données factices."""
    rng = np.random.default_rng(42)
    x = rng.random((50, 3))
    y = x.sum(axis=1)
    model = XGBRegressor(n_estimators=5, max_depth=2)
    model.fit(x, y)
    return model


class TestSaveLoad:
    def test_save_creates_files(
        self, tmp_path: Path, trivial_model: XGBRegressor
    ) -> None:
        model_path, meta_path = save_model(
            trivial_model,
            tmp_path,
            metadata={"test": True, "version": "0.1"},
        )
        assert model_path.exists()
        assert meta_path.exists()
        assert model_path.name == MODEL_FILENAME

    def test_load_returns_working_model(
        self, tmp_path: Path, trivial_model: XGBRegressor
    ) -> None:
        save_model(trivial_model, tmp_path, metadata={"test": True})
        loaded, meta = load_model(tmp_path)
        # Le modèle chargé doit faire les mêmes prédictions
        x_test = np.array([[0.5, 0.5, 0.5]])
        original_pred = trivial_model.predict(x_test)
        loaded_pred = loaded.predict(x_test)
        assert np.allclose(original_pred, loaded_pred)
        assert meta["test"] is True

    def test_load_missing_model_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_model(tmp_path)

    def test_model_exists(
        self, tmp_path: Path, trivial_model: XGBRegressor
    ) -> None:
        assert not model_exists(tmp_path)
        save_model(trivial_model, tmp_path, metadata={})
        assert model_exists(tmp_path)

    def test_metadata_includes_saved_at(
        self, tmp_path: Path, trivial_model: XGBRegressor
    ) -> None:
        save_model(
            trivial_model, tmp_path, metadata={"custom_field": 42}
        )
        _model, meta = load_model(tmp_path)
        assert "saved_at" in meta
        assert meta["custom_field"] == 42
        assert meta["model_filename"] == MODEL_FILENAME
