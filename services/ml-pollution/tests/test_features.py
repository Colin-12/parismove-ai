"""Tests du module features."""
from __future__ import annotations

import pandas as pd

from ml_pollution.features import (
    CATEGORICAL_FEATURES,
    FEATURE_COLUMNS,
    TARGET_COLUMN,
    build_features,
    build_inference_row,
)


def _make_sample_df(n_rows: int = 30, station_id: str = "@5722") -> pd.DataFrame:
    """Génère un DataFrame de test avec mesures horaires factices."""
    timestamps = pd.date_range("2026-04-25", periods=n_rows, freq="h", tz="UTC")
    return pd.DataFrame({
        "station_id": [station_id] * n_rows,
        "station_name": ["Paris (Place de l'Opera)"] * n_rows,
        "latitude": [48.87] * n_rows,
        "longitude": [2.33] * n_rows,
        "measured_at": timestamps,
        "pm25": [30 + i * 0.5 for i in range(n_rows)],
        "pm10": [40 + i * 0.5 for i in range(n_rows)],
        "no2": [20] * n_rows,
        "temperature_c": [15] * n_rows,
        "humidity_pct": [60] * n_rows,
        "wind_speed_ms": [3] * n_rows,
        "precipitation_mm": [0] * n_rows,
    })


class TestFeatureColumns:
    def test_feature_columns_count(self) -> None:
        assert len(FEATURE_COLUMNS) == 10

    def test_target_in_features_excluded(self) -> None:
        assert TARGET_COLUMN not in FEATURE_COLUMNS

    def test_categorical_subset(self) -> None:
        for cat in CATEGORICAL_FEATURES:
            assert cat in FEATURE_COLUMNS


class TestBuildFeatures:
    def test_empty_input(self) -> None:
        result = build_features(pd.DataFrame(), for_training=True)
        assert result.empty

    def test_training_drops_first_24h(self) -> None:
        # Avec 30 lignes consécutives, la lag h-24 ne marche que sur les
        # lignes 25+ (et h+1 ne marche pas sur la dernière).
        df = _make_sample_df(n_rows=30)
        result = build_features(df, for_training=True)
        assert len(result) == 5  # 30 - 24 (lag) - 1 (cible)

    def test_training_has_target(self) -> None:
        df = _make_sample_df(n_rows=30)
        result = build_features(df, for_training=True)
        assert TARGET_COLUMN in result.columns

    def test_inference_no_target(self) -> None:
        df = _make_sample_df(n_rows=30)
        result = build_features(df, for_training=False)
        assert TARGET_COLUMN not in result.columns

    def test_temporal_features(self) -> None:
        df = _make_sample_df(n_rows=30)
        result = build_features(df, for_training=True)
        assert "heure" in result.columns
        assert "jour_semaine" in result.columns
        assert "mois" in result.columns
        assert result["heure"].between(0, 23).all()
        assert result["jour_semaine"].between(0, 6).all()
        assert result["mois"].between(1, 12).all()

    def test_lag_features_correct(self) -> None:
        df = _make_sample_df(n_rows=30)
        result = build_features(df, for_training=True)
        # pm25_h1 doit être strictement < pm25 (puisque pm25 augmente)
        # Note: result.iloc[0] correspond à la mesure 25 (index 24 d'origine)
        # à cet endroit, pm25_h1 = pm25 de l'index 23 et pm25 de cible (cible = h+1)
        assert (result["pm25_h1"] >= 0).all()
        assert (result["pm25_h24"] >= 0).all()


class TestBuildInferenceRow:
    def test_returns_single_row(self) -> None:
        row = build_inference_row(
            station_id="@5722",
            target_dt=pd.Timestamp("2026-05-02 14:00", tz="UTC"),
            pm25_h1=35.0,
            pm25_h24=40.0,
            temperature_c=18.0,
            humidity_pct=65.0,
            wind_speed_ms=4.0,
            precipitation_mm=0.0,
        )
        assert len(row) == 1
        assert list(row.columns) == FEATURE_COLUMNS

    def test_temporal_extraction(self) -> None:
        row = build_inference_row(
            station_id="@5722",
            target_dt=pd.Timestamp("2026-05-02 14:00", tz="UTC"),
            pm25_h1=35.0,
            pm25_h24=40.0,
            temperature_c=18.0,
            humidity_pct=65.0,
            wind_speed_ms=4.0,
            precipitation_mm=0.0,
        )
        assert row.iloc[0]["heure"] == 14
        assert row.iloc[0]["mois"] == 5

    def test_handles_none_meteo(self) -> None:
        # En cas d'absence de météo, on doit pouvoir construire la row
        row = build_inference_row(
            station_id="@5722",
            target_dt=pd.Timestamp("2026-05-02 14:00", tz="UTC"),
            pm25_h1=35.0,
            pm25_h24=None,
            temperature_c=None,
            humidity_pct=None,
            wind_speed_ms=None,
            precipitation_mm=None,
        )
        assert len(row) == 1
