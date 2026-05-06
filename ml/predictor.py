"""Predictor wrapper around persisted GBDT artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ml.feature_schema import PREDICTION_OUTPUT_COLUMNS, SLA_LABEL_TO_ID
from ml.model_registry import load_model_artifacts


class GBDTPredictor:
    """Small inference wrapper that keeps model loading isolated from the simulator."""

    def __init__(self, model_dir):
        self.model_dir = Path(model_dir)
        self.horizon_models = self._load_horizon_models(self.model_dir)
        if self.horizon_models:
            self.model = self.horizon_models[0]["model"]
            self.feature_columns = sorted(
                {feature for item in self.horizon_models for feature in item["feature_columns"]}
            )
            self.metadata = self._merge_horizon_metadata(self.horizon_models)
            self.label_config = self.horizon_models[0]["label_config"]
        else:
            artifacts = load_model_artifacts(self.model_dir)
            self.model = artifacts["model"]
            self.feature_columns = artifacts["feature_columns"]
            self.metadata = artifacts["metadata"]
            self.label_config = artifacts["label_config"]

    @staticmethod
    def _load_horizon_models(model_dir: Path) -> list[dict]:
        manifest_path = model_dir / "horizon_models.json"
        if not manifest_path.exists():
            return []

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        items = []
        for entry in manifest.get("models", []):
            subdir = Path(entry["path"])
            if not subdir.is_absolute():
                subdir = model_dir / subdir
            artifacts = load_model_artifacts(subdir)
            items.append(
                {
                    "horizon": int(entry.get("horizon", artifacts["metadata"].get("horizon", 1))),
                    "weight": float(entry.get("weight", 1.0)),
                    "model": artifacts["model"],
                    "feature_columns": artifacts["feature_columns"],
                    "metadata": artifacts["metadata"],
                    "label_config": artifacts["label_config"],
                }
            )
        total_weight = sum(max(item["weight"], 0.0) for item in items)
        if total_weight > 0:
            for item in items:
                item["weight"] = max(item["weight"], 0.0) / total_weight
        return items

    @staticmethod
    def _merge_horizon_metadata(items: list[dict]) -> dict:
        metadata = dict(items[0]["metadata"]) if items else {}
        metadata["multi_horizon"] = {
            "enabled": True,
            "models": [
                {"horizon": item["horizon"], "weight": item["weight"]}
                for item in items
            ],
        }
        # Use h=1 thresholds as the operational default when available.
        h1 = next((item for item in items if item["horizon"] == 1), items[0] if items else None)
        if h1 is not None:
            for key in [
                "decision_thresholds_by_slice",
                "decision_threshold_default",
                "below_threshold_action_scale",
                "threshold_tuning",
            ]:
                if key in h1["metadata"]:
                    metadata[key] = h1["metadata"][key]
        return metadata

    @staticmethod
    def _binary_violation_proba(model, model_input: pd.DataFrame) -> np.ndarray:
        predicted_proba = model.predict_proba(model_input)
        if predicted_proba.shape[1] == 2:
            return predicted_proba[:, 1]

        class_names = list(model.classes_)
        if "violation" in class_names:
            violation_index = class_names.index("violation")
            return predicted_proba[:, violation_index]
        return predicted_proba.max(axis=1)

    def _has_threshold_metadata(self) -> bool:
        threshold_info = self.metadata.get("threshold_tuning", {}) or {}
        return bool(
            self.metadata.get("decision_thresholds_by_slice")
            or "decision_threshold_default" in self.metadata
            or threshold_info.get("enabled")
        )

    def _apply_threshold_metadata(self, output: pd.DataFrame, *, override_label: bool) -> pd.DataFrame:
        thresholds = self.metadata.get("decision_thresholds_by_slice", {}) or {}
        default_threshold = float(self.metadata.get("decision_threshold_default", 0.5))
        below_scale = float(self.metadata.get("below_threshold_action_scale", 0.25))
        has_threshold_metadata = self._has_threshold_metadata()

        if "slice_name" in output.columns and thresholds:
            threshold_series = output["slice_name"].astype(str).map(thresholds).fillna(default_threshold)
        else:
            threshold_series = pd.Series(default_threshold, index=output.index, dtype=float)

        threshold_series = threshold_series.astype(float).clip(0.0, 1.0)
        prob = output["sla_violation_prob"].fillna(0.0).clip(0.0, 1.0)
        exceeded = prob >= threshold_series
        output["sla_violation_threshold"] = threshold_series
        output["sla_violation_threshold_exceeded"] = exceeded.astype(int)
        output["sla_violation_action_score"] = np.where(
            has_threshold_metadata & (~exceeded),
            prob * below_scale,
            prob,
        )
        if override_label or has_threshold_metadata:
            output["predicted_label"] = exceeded.astype(int)
            output["predicted_label_id"] = output["predicted_label"].astype(int)
        return output

    def predict(self, feature_df: pd.DataFrame) -> pd.DataFrame:
        missing_columns = [column for column in self.feature_columns if column not in feature_df.columns]
        if missing_columns:
            raise ValueError(f"Missing feature columns for inference: {missing_columns}")

        output = feature_df.copy()
        if self.horizon_models:
            blended_prob = pd.Series(0.0, index=output.index, dtype=float)
            for item in self.horizon_models:
                model_input = output[item["feature_columns"]].copy()
                horizon_prob = self._binary_violation_proba(item["model"], model_input)
                output[f"sla_violation_prob_h{item['horizon']}"] = horizon_prob
                blended_prob = blended_prob + float(item["weight"]) * horizon_prob
            output["sla_violation_prob"] = blended_prob.clip(0.0, 1.0)
            output = self._apply_threshold_metadata(output, override_label=True)
        else:
            model_input = output[self.feature_columns]
            predicted_label = self.model.predict(model_input)
            output["sla_violation_prob"] = self._binary_violation_proba(self.model, model_input)
            output["predicted_label"] = predicted_label
            output = self._apply_threshold_metadata(output, override_label=False)

            if output["predicted_label"].dtype.kind in {"O", "U", "S"}:
                output["predicted_label_id"] = output["predicted_label"].map(SLA_LABEL_TO_ID).fillna(-1).astype(int)
            else:
                output["predicted_label_id"] = output["predicted_label"].astype(int)

        ordered_columns = [
            column for column in PREDICTION_OUTPUT_COLUMNS if column in output.columns
        ] + [column for column in output.columns if column not in PREDICTION_OUTPUT_COLUMNS]
        return output[ordered_columns]
