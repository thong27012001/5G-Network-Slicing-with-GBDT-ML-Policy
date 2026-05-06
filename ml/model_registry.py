"""Persistence helpers for trained ML artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import joblib


def save_model_artifacts(
    model,
    model_dir: str | Path,
    feature_columns: list[str],
    metadata: dict | None = None,
    label_config: dict | None = None,
) -> dict[str, Path]:
    model_dir = Path(model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)

    model_path = model_dir / "model.joblib"
    feature_path = model_dir / "feature_columns.json"
    metadata_path = model_dir / "metadata.json"
    label_config_path = model_dir / "label_config.json"

    joblib.dump(model, model_path)
    feature_path.write_text(json.dumps(feature_columns, indent=2), encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata or {}, indent=2), encoding="utf-8")
    label_config_path.write_text(json.dumps(label_config or {}, indent=2), encoding="utf-8")

    return {
        "model_path": model_path,
        "feature_columns_path": feature_path,
        "metadata_path": metadata_path,
        "label_config_path": label_config_path,
    }


def load_model_artifacts(model_dir: str | Path) -> dict:
    model_dir = Path(model_dir)
    model_path = model_dir / "model.joblib"
    feature_path = model_dir / "feature_columns.json"
    metadata_path = model_dir / "metadata.json"
    label_config_path = model_dir / "label_config.json"

    if not model_path.exists():
        raise FileNotFoundError(f"Missing model artifact: {model_path}")
    if not feature_path.exists():
        raise FileNotFoundError(f"Missing feature schema artifact: {feature_path}")

    metadata = {}
    label_config = {}
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if label_config_path.exists():
        label_config = json.loads(label_config_path.read_text(encoding="utf-8"))

    return {
        "model": joblib.load(model_path),
        "feature_columns": json.loads(feature_path.read_text(encoding="utf-8")),
        "metadata": metadata,
        "label_config": label_config,
    }
