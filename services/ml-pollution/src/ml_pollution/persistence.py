"""Persistance du modèle entraîné + métadonnées.

Format :
    models/
    ├── pm25_xgb.joblib       # le modèle XGBoost
    └── pm25_xgb.meta.json    # métadonnées (date, métriques, n_samples...)
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
from xgboost import XGBRegressor

MODEL_FILENAME = "pm25_xgb.joblib"
META_FILENAME = "pm25_xgb.meta.json"


def save_model(
    model: XGBRegressor,
    model_dir: Path,
    metadata: dict[str, Any],
) -> tuple[Path, Path]:
    """Sauvegarde le modèle et ses métadonnées.

    Returns:
        Tuple (chemin du modèle, chemin des métadonnées)
    """
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / MODEL_FILENAME
    meta_path = model_dir / META_FILENAME

    joblib.dump(model, model_path)

    metadata = dict(metadata)
    metadata["saved_at"] = datetime.now(UTC).isoformat()
    metadata["model_filename"] = MODEL_FILENAME
    meta_path.write_text(
        json.dumps(metadata, indent=2, default=str), encoding="utf-8"
    )

    return model_path, meta_path


def load_model(model_dir: Path) -> tuple[XGBRegressor, dict[str, Any]]:
    """Charge le modèle et ses métadonnées.

    Raises:
        FileNotFoundError: si le modèle n'a jamais été entraîné.
    """
    model_path = model_dir / MODEL_FILENAME
    meta_path = model_dir / META_FILENAME

    if not model_path.exists():
        raise FileNotFoundError(
            f"Aucun modèle entraîné dans {model_dir}. "
            f"Lance `ml-pollution train` d'abord."
        )

    model = joblib.load(model_path)
    metadata: dict[str, Any] = {}
    if meta_path.exists():
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))

    return model, metadata


def model_exists(model_dir: Path) -> bool:
    """Indique si un modèle est déjà entraîné."""
    return (model_dir / MODEL_FILENAME).exists()
