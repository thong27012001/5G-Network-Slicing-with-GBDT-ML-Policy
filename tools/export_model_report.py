"""Export a self-contained global GBDT model report.

The production model is fixed across simulation seeds. This report is therefore
global to the model artifact and is written next to the FINAL_OUTPUT folders.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import joblib
import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import auc, roc_curve


SLICE_ORDER = ("URLLC", "eMBB", "mMTC")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _resolve(repo_root: Path, value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = repo_root / path
    return path


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_div(num: float, den: float) -> float:
    return float(num / den) if den else float("nan")


def _precision_recall_f1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    f1 = _safe_div(2 * precision * recall, precision + recall) if not (
        np.isnan(precision) or np.isnan(recall)
    ) else float("nan")
    return precision, recall, f1


def _base_pipeline(model: Any) -> Any:
    if hasattr(model, "named_steps"):
        return model
    if hasattr(model, "calibrated_classifiers_") and model.calibrated_classifiers_:
        inner = model.calibrated_classifiers_[0]
        base = getattr(inner, "estimator", None) or getattr(inner, "base_estimator", None) or inner
        if hasattr(base, "named_steps"):
            return base
    return model


def _feature_importance(model_path: Path, feature_columns_path: Path) -> pd.DataFrame:
    model = joblib.load(model_path)
    feature_columns = json.loads(feature_columns_path.read_text(encoding="utf-8"))
    pipeline = _base_pipeline(model)

    if not hasattr(pipeline, "named_steps") or "gbdt" not in pipeline.named_steps:
        return pd.DataFrame(columns=["feature", "importance"])

    importances = getattr(pipeline.named_steps["gbdt"], "feature_importances_", None)
    if importances is None:
        return pd.DataFrame(columns=["feature", "importance"])

    names: list[str]
    preprocessor = pipeline.named_steps.get("preprocessor")
    try:
        names = list(preprocessor.get_feature_names_out()) if preprocessor else []
        names = [name.split("__", 1)[-1] for name in names]
    except Exception:
        names = []

    if len(names) != len(importances):
        names = [f"f{i}" for i in range(len(importances))]

    return (
        pd.DataFrame({"feature": names, "importance": importances})
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )


def _plot_feature_importance(frame: pd.DataFrame, output_path: Path, top_n: int = 15) -> None:
    if frame.empty:
        return
    top = frame.head(top_n).iloc[::-1]
    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    ax.barh(top["feature"], top["importance"], color="#1f77b4", alpha=0.9)
    ax.set_xlabel("Built-in GBDT feature importance")
    ax.set_title(f"Top-{top_n} Feature Importance (horizon h=1)")
    ax.grid(axis="x", linestyle="--", alpha=0.35)
    fig.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def _plot_overall_metrics(frame: pd.DataFrame, output_path: Path) -> None:
    if frame.empty:
        return
    plot_frame = frame.sort_values("horizon").copy()
    x = np.arange(len(plot_frame))
    width = 0.35

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    accuracy = pd.to_numeric(plot_frame["accuracy"], errors="coerce").to_numpy()
    roc_auc = pd.to_numeric(plot_frame["roc_auc"], errors="coerce").to_numpy()
    bars_acc = ax.bar(x - width / 2, accuracy, width, label="Accuracy", color="#4c78a8")
    bars_auc = ax.bar(x + width / 2, roc_auc, width, label="ROC-AUC", color="#f58518")

    for bars in (bars_acc, bars_auc):
        for bar in bars:
            value = bar.get_height()
            if not np.isnan(value):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    min(value + 0.01, 1.04),
                    f"{value:.4f}",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                )

    ax.set_xticks(x)
    ax.set_xticklabels([f"h={int(h)}" for h in plot_frame["horizon"]])
    ax.set_ylim(0.90, 1.01)
    ax.set_ylabel("Score")
    ax.set_title("GBDT Offline Metrics by Prediction Horizon")
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def _plot_precision_recall(
    frame: pd.DataFrame,
    output_path: Path,
    *,
    title_prefix: str = "",
) -> None:
    if frame.empty:
        return
    horizons = sorted(frame["horizon"].dropna().unique().tolist())
    fig, axes = plt.subplots(len(horizons), 1, figsize=(8.5, 3.2 * len(horizons)), sharex=True)
    if len(horizons) == 1:
        axes = [axes]

    metrics = ["precision", "recall", "f1"]
    colors = {"precision": "#4c78a8", "recall": "#54a24b", "f1": "#e45756"}
    width = 0.23
    x = np.arange(len(SLICE_ORDER))

    for ax, horizon in zip(axes, horizons):
        sub = frame[frame["horizon"] == horizon].set_index("slice_name").reindex(SLICE_ORDER)
        for idx, metric in enumerate(metrics):
            values = pd.to_numeric(sub[metric], errors="coerce").to_numpy()
            heights = np.nan_to_num(values, nan=0.0)
            bars = ax.bar(
                x + (idx - 1) * width,
                heights,
                width,
                label=metric.upper(),
                color=colors[metric],
                alpha=0.9,
            )
            for bar, value in zip(bars, values):
                label = "N/A" if np.isnan(value) else f"{value:.2f}"
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    min(bar.get_height() + 0.03, 1.05),
                    label,
                    ha="center",
                    va="bottom",
                    fontsize=8,
                )
        prefix = f"{title_prefix} " if title_prefix else ""
        ax.set_title(f"{prefix}Precision / Recall / F1 by Slice (h={int(horizon)})")
        ax.set_ylim(0, 1.12)
        ax.grid(axis="y", linestyle="--", alpha=0.35)
        ax.legend(loc="lower right", ncol=3)

    axes[-1].set_xticks(x)
    axes[-1].set_xticklabels(SLICE_ORDER)
    axes[-1].set_xlabel("Slice")
    fig.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def _plot_confusion_matrices(
    frame: pd.DataFrame,
    output_path: Path,
    *,
    title: str = "Confusion Matrices by Horizon and Slice",
) -> None:
    if frame.empty:
        return
    horizons = sorted(frame["horizon"].dropna().unique().tolist())
    fig, axes = plt.subplots(
        len(horizons),
        len(SLICE_ORDER),
        figsize=(4.0 * len(SLICE_ORDER), 3.3 * len(horizons)),
        squeeze=False,
    )

    max_count = max(
        int(frame[["tp", "fp", "fn", "tn"]].max().max()),
        1,
    )
    for row_idx, horizon in enumerate(horizons):
        for col_idx, slice_name in enumerate(SLICE_ORDER):
            ax = axes[row_idx][col_idx]
            match = frame[(frame["horizon"] == horizon) & (frame["slice_name"] == slice_name)]
            if match.empty:
                ax.axis("off")
                continue
            item = match.iloc[0]
            matrix = np.array(
                [
                    [int(item["tn"]), int(item["fp"])],
                    [int(item["fn"]), int(item["tp"])],
                ]
            )
            ax.imshow(matrix, cmap="Blues", vmin=0, vmax=max_count)
            for i in range(2):
                for j in range(2):
                    ax.text(j, i, str(matrix[i, j]), ha="center", va="center", fontsize=10)
            ax.set_xticks([0, 1])
            ax.set_xticklabels(["Pred 0", "Pred 1"])
            ax.set_yticks([0, 1])
            ax.set_yticklabels(["True 0", "True 1"])
            ax.set_title(f"h={int(horizon)} | {slice_name}")

    fig.suptitle(title, y=1.01)
    fig.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def _resolve_dataset_path(repo_root: Path, metadata: dict[str, Any]) -> Path | None:
    raw_path = metadata.get("dataset")
    if not raw_path:
        return None

    path = Path(raw_path)
    candidates = [path]
    if not path.is_absolute():
        candidates.append(repo_root / path)

    # Older artifacts may contain absolute paths from the original training
    # checkout. Keep common relative fallbacks so the report can still be
    # regenerated after the repo is moved.
    candidates.extend(
        [
            repo_root / "artifacts" / "multihorizon_training" / "datasets_anyh_135" / path.name,
            repo_root / "datasets" / path.name,
            repo_root / path.name,
        ]
    )

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _test_mask_from_split_info(dataset: pd.DataFrame, split_info: dict[str, Any]) -> pd.Series:
    mask = pd.Series(False, index=dataset.index)
    strategy = split_info.get("split_strategy")
    if "time" not in dataset.columns:
        return mask

    if strategy == "stratified_time":
        for summary in split_info.get("slice_summaries", []):
            group_mask = pd.Series(True, index=dataset.index)
            if "scenario_name" in dataset.columns and summary.get("scenario_name") not in {None, "__global__"}:
                group_mask &= dataset["scenario_name"].astype(str) == str(summary.get("scenario_name"))
            if "slice_name" in dataset.columns and summary.get("slice_name") is not None:
                group_mask &= dataset["slice_name"].astype(str) == str(summary.get("slice_name"))
            group_mask &= pd.to_numeric(dataset["time"], errors="coerce").between(
                float(summary.get("test_time_min")),
                float(summary.get("test_time_max")),
                inclusive="both",
            )
            mask |= group_mask
        return mask

    if strategy == "time":
        for summary in split_info.get("scenario_summaries", []):
            group_mask = pd.Series(True, index=dataset.index)
            if "scenario_name" in dataset.columns and summary.get("scenario_name") not in {None, "__global__"}:
                group_mask &= dataset["scenario_name"].astype(str) == str(summary.get("scenario_name"))
            group_mask &= pd.to_numeric(dataset["time"], errors="coerce").between(
                float(summary.get("test_time_min")),
                float(summary.get("test_time_max")),
                inclusive="both",
            )
            mask |= group_mask
        return mask

    return mask


def _evaluation_predictions(
    repo_root: Path,
    h_dir: Path,
    metadata: dict[str, Any],
    horizon: int,
    *,
    scope: str = "test",
) -> pd.DataFrame:
    model_path = h_dir / "model.joblib"
    feature_columns_path = h_dir / "feature_columns.json"
    if not model_path.exists() or not feature_columns_path.exists():
        return pd.DataFrame()

    dataset_path = _resolve_dataset_path(repo_root, metadata)
    if dataset_path is None:
        return pd.DataFrame()

    target_column = metadata.get("target_column")
    if not target_column:
        return pd.DataFrame()

    dataset = pd.read_csv(dataset_path)
    feature_columns = json.loads(feature_columns_path.read_text(encoding="utf-8"))
    required_columns = [*feature_columns, target_column]
    missing_columns = [column for column in required_columns if column not in dataset.columns]
    if missing_columns:
        return pd.DataFrame()

    if scope == "test":
        eval_mask = _test_mask_from_split_info(dataset, metadata.get("split_info", {}))
        if not bool(eval_mask.any()):
            return pd.DataFrame()
        eval_frame = dataset.loc[eval_mask].copy()
    elif scope == "full_dataset_diagnostic":
        eval_frame = dataset.copy()
    else:
        raise ValueError("scope must be 'test' or 'full_dataset_diagnostic'.")

    model = joblib.load(model_path)
    y_prob = model.predict_proba(eval_frame[feature_columns])[:, 1]
    threshold_info = metadata.get("threshold_tuning", {})
    threshold_by_slice = threshold_info.get("threshold_by_slice", {})
    default_threshold = float(threshold_info.get("default_threshold", 0.5))
    if "slice_name" in eval_frame.columns:
        thresholds = eval_frame["slice_name"].map(threshold_by_slice).fillna(default_threshold).astype(float)
    else:
        thresholds = pd.Series(default_threshold, index=eval_frame.index)

    columns = {
        "horizon": horizon,
        "scope": scope,
        "scenario_name": eval_frame.get("scenario_name", pd.Series("N/A", index=eval_frame.index)).astype(str),
        "slice_name": eval_frame.get("slice_name", pd.Series("N/A", index=eval_frame.index)).astype(str),
        "time": eval_frame.get("time", pd.Series(np.nan, index=eval_frame.index)),
        "y_true": pd.to_numeric(eval_frame[target_column], errors="coerce").fillna(0).astype(int),
        "y_prob": y_prob,
        "threshold": thresholds.to_numpy(dtype=float),
    }
    result = pd.DataFrame(columns)
    result["y_pred"] = (result["y_prob"] >= result["threshold"]).astype(int)
    return result


def _metrics_from_predictions(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if frame.empty:
        return pd.DataFrame()

    for (scope, horizon, slice_name), group in frame.groupby(["scope", "horizon", "slice_name"], sort=True):
        y_true = pd.to_numeric(group["y_true"], errors="coerce").fillna(0).astype(int)
        y_pred = pd.to_numeric(group["y_pred"], errors="coerce").fillna(0).astype(int)
        tp = int(((y_pred == 1) & (y_true == 1)).sum())
        fp = int(((y_pred == 1) & (y_true == 0)).sum())
        fn = int(((y_pred == 0) & (y_true == 1)).sum())
        tn = int(((y_pred == 0) & (y_true == 0)).sum())
        precision, recall, f1 = _precision_recall_f1(tp, fp, fn)
        auc_value = float("nan")
        if y_true.nunique() > 1:
            _, _, roc_auc_frame = _roc_summary_for_group(y_true, pd.to_numeric(group["y_prob"], errors="coerce"))
            auc_value = roc_auc_frame
        positive_times = group.loc[y_true == 1, "time"]
        rows.append(
            {
                "scope": scope,
                "horizon": int(horizon),
                "slice_name": str(slice_name),
                "support": int(len(group)),
                "positive_rows": int(y_true.sum()),
                "positive_rate": float(y_true.mean()) if len(group) else float("nan"),
                "positive_time_min": float(positive_times.min()) if not positive_times.empty else float("nan"),
                "positive_time_max": float(positive_times.max()) if not positive_times.empty else float("nan"),
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "tn": tn,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "roc_auc": auc_value,
            }
        )
    return pd.DataFrame(rows)


def _roc_summary_for_group(y_true: pd.Series, y_prob: pd.Series) -> tuple[np.ndarray, np.ndarray, float]:
    valid_mask = y_prob.notna()
    y_true = y_true[valid_mask]
    y_prob = y_prob[valid_mask]
    if y_true.nunique() < 2:
        return np.array([]), np.array([]), float("nan")
    fpr, tpr, _ = roc_curve(y_true, y_prob)
    return fpr, tpr, float(auc(fpr, tpr))


def _roc_curve_points(evaluation_frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if evaluation_frame.empty:
        return pd.DataFrame()

    for horizon, group in evaluation_frame.groupby("horizon", sort=True):
        y_true = pd.to_numeric(group["y_true"], errors="coerce").fillna(0).astype(int)
        y_prob = pd.to_numeric(group["y_prob"], errors="coerce")
        valid_mask = y_prob.notna()
        y_true = y_true[valid_mask]
        y_prob = y_prob[valid_mask]
        if y_true.nunique() < 2:
            continue

        fpr, tpr, thresholds = roc_curve(y_true, y_prob)
        roc_auc = auc(fpr, tpr)
        for idx, (fpr_value, tpr_value, threshold) in enumerate(zip(fpr, tpr, thresholds)):
            rows.append(
                {
                    "horizon": int(horizon),
                    "point_index": int(idx),
                    "fpr": float(fpr_value),
                    "tpr": float(tpr_value),
                    "threshold": float(threshold),
                    "roc_auc": float(roc_auc),
                }
            )
    return pd.DataFrame(rows)


def _plot_roc_curves(points: pd.DataFrame, output_path: Path) -> None:
    if points.empty:
        return

    fig, ax = plt.subplots(figsize=(6.8, 5.4))
    for horizon, group in points.groupby("horizon", sort=True):
        group = group.sort_values("point_index")
        roc_auc = float(group["roc_auc"].iloc[0])
        ax.plot(group["fpr"], group["tpr"], linewidth=2, label=f"h={int(horizon)} (AUC={roc_auc:.4f})")

    ax.plot([0, 1], [0, 1], linestyle="--", color="gray", linewidth=1, label="Random baseline")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("ROC Curves by Prediction Horizon")
    ax.grid(linestyle="--", alpha=0.35)
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def _format_float(value: Any, digits: int = 4) -> str:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "N/A"
    if np.isnan(value):
        return "N/A"
    return f"{value:.{digits}f}"


def _markdown_table(frame: pd.DataFrame, columns: list[str]) -> str:
    if frame.empty:
        return "No data available."
    rows = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for _, row in frame[columns].iterrows():
        values = []
        for value in row.tolist():
            if isinstance(value, float):
                values.append(_format_float(value))
            else:
                values.append(str(value))
        rows.append("| " + " | ".join(values) + " |")
    return "\n".join(rows)


def _dataclass_to_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return {}


def _write_controller_rule(
    output_dir: Path,
    controller_preset: str | None,
    broker_preset: str | None,
) -> None:
    repo_root = str(_repo_root())
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    controller_row: dict[str, Any] = {"controller_preset": controller_preset or "N/A"}
    broker_row: dict[str, Any] = {"broker_preset": broker_preset or "N/A"}

    try:
        from control.controller_schema import get_controller_preset

        controller = get_controller_preset(controller_preset or "balanced_ml_v3_gentle")
        controller_row.update(_dataclass_to_dict(controller))
        constraints = controller_row.pop("constraints", {}) or {}
        for key, value in constraints.items():
            controller_row[f"constraints.{key}"] = value
    except Exception as exc:
        controller_row["load_error"] = str(exc)

    try:
        from broker.broker_schema import get_broker_config

        broker = get_broker_config(broker_preset or "forecasting_balanced")
        broker_row.update(_dataclass_to_dict(broker))
    except Exception as exc:
        broker_row["load_error"] = str(exc)

    pd.DataFrame([controller_row]).to_csv(output_dir / "controller_rule_parameters.csv", index=False)
    pd.DataFrame([broker_row]).to_csv(output_dir / "broker_rule_parameters.csv", index=False)

    rule_text = f"""# Controller Rule

The model report is global, but this section records the controller and broker
rule used by the release runner.

## Closed-Loop Decision Flow

1. The online state frame is converted into the same feature schema used during training.
2. The multi-horizon GBDT model predicts SLA-violation risk for each `(slice, base station)` row.
3. Horizon risks are blended using the weights in `horizon_models.json`.
4. Per-slice thresholds from model metadata convert calibrated probability into a warning/active-risk signal.
5. The controller maps risk, load, latency pressure, and slice priority into runtime actions.
6. The broker optionally smooths/adjusts the controller action using short-window demand forecast and safety feedback.

## Controller Formula

The controller uses the preset `{controller_row.get('name', controller_preset or 'N/A')}`.

```text
urgency_score =
    alpha_risk * predicted_sla_risk
  + beta_load * slice_load
  + gamma_latency * latency_pressure
  + delta_priority * slice_priority_weight

target_ratio = bounded_simplex_normalize(urgency_score)
scheduling_weight = priority_weight * (1 + scheduling gains from risk/latency/load)
admission_guard = clamp(1 + admission_risk_gain * risk + admission_block_gain * block_ratio)
```

Important controller parameters:

- `alpha_risk`: `{controller_row.get('alpha_risk', 'N/A')}`
- `beta_load`: `{controller_row.get('beta_load', 'N/A')}`
- `gamma_latency`: `{controller_row.get('gamma_latency', 'N/A')}`
- `delta_priority`: `{controller_row.get('delta_priority', 'N/A')}`
- `scheduling_risk_gain`: `{controller_row.get('scheduling_risk_gain', 'N/A')}`
- `scheduling_latency_gain`: `{controller_row.get('scheduling_latency_gain', 'N/A')}`
- `scheduling_load_gain`: `{controller_row.get('scheduling_load_gain', 'N/A')}`
- `admission_risk_gain`: `{controller_row.get('admission_risk_gain', 'N/A')}`
- `admission_block_gain`: `{controller_row.get('admission_block_gain', 'N/A')}`
- `risk_probability_ceiling`: `{controller_row.get('risk_probability_ceiling', 'N/A')}`
- `max_step_change`: `{controller_row.get('constraints.max_step_change', 'N/A')}`
- `admission_guard_ceiling`: `{controller_row.get('constraints.admission_guard_ceiling', 'N/A')}`
- `min_ratio_by_slice`: `{controller_row.get('constraints.min_ratio_by_slice', 'N/A')}`

## Broker Rule

The broker uses the preset `{broker_row.get('name', broker_preset or 'N/A')}`.

Important broker parameters:

- `observed_window`: `{broker_row.get('observed_window', 'N/A')}`
- `forecast_horizon`: `{broker_row.get('forecast_horizon', 'N/A')}`
- `forecast_blend`: `{broker_row.get('forecast_blend', 'N/A')}`
- `smoothing_alpha`: `{broker_row.get('smoothing_alpha', 'N/A')}`
- `scheduling_forecast_gain`: `{broker_row.get('scheduling_forecast_gain', 'N/A')}`
- `admission_forecast_gain`: `{broker_row.get('admission_forecast_gain', 'N/A')}`
- `target_ratio_ema_alpha`: `{broker_row.get('target_ratio_ema_alpha', 'N/A')}`
- `fairness_floor_by_slice`: `{broker_row.get('fairness_floor_by_slice', 'N/A')}`
"""
    (output_dir / "controller_rule.md").write_text(rule_text, encoding="utf-8")


def export_model_report(
    model_dir: str | Path,
    output_dir: str | Path,
    *,
    scenario: str | None = None,
    controller_preset: str | None = None,
    broker_preset: str | None = None,
) -> Path:
    repo_root = _repo_root()
    model_dir = _resolve(repo_root, model_dir)
    output_dir = _resolve(repo_root, output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = _read_json(model_dir / "horizon_models.json")
    models = manifest.get("models", [])

    overall_rows: list[dict[str, Any]] = []
    per_slice_rows: list[dict[str, Any]] = []
    confusion_rows: list[dict[str, Any]] = []
    evaluation_frames: list[pd.DataFrame] = []
    diagnostic_evaluation_frames: list[pd.DataFrame] = []

    for item in models:
        horizon = int(item.get("horizon", 0))
        h_dir = model_dir / str(item.get("path", f"h{horizon}"))
        metadata = _read_json(h_dir / "metadata.json")
        threshold_info = metadata.get("threshold_tuning", {}).get("slices", {})

        overall_rows.append(
            {
                "horizon": horizon,
                "target_column": item.get("target_column") or metadata.get("target_column"),
                "blend_weight": item.get("weight"),
                "accuracy": item.get("accuracy"),
                "roc_auc": item.get("roc_auc"),
                "calibration": metadata.get("calibration", {}).get("method", metadata.get("calibration_method")),
                "split_strategy": metadata.get("split_strategy"),
                "sample_weight_mode": metadata.get("sample_weight_mode"),
                "transition_weight_multiplier": metadata.get("transition_reweight", {}).get("multiplier"),
            }
        )

        for slice_name in SLICE_ORDER:
            info = threshold_info.get(slice_name, {})
            tp = int(info.get("tp", 0))
            fp = int(info.get("fp", 0))
            fn = int(info.get("fn", 0))
            tn = int(info.get("tn", 0))
            precision, recall, f1 = _precision_recall_f1(tp, fp, fn)
            row = {
                "horizon": horizon,
                "slice_name": slice_name,
                "threshold": info.get("threshold", item.get("thresholds", {}).get(slice_name, 0.5)),
                "support": int(info.get("support", tp + fp + fn + tn)),
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "tn": tn,
                "precision": precision,
                "recall": recall,
                "f1": f1,
            }
            per_slice_rows.append(row)
            confusion_rows.append(row)

        evaluation_frame = _evaluation_predictions(repo_root, h_dir, metadata, horizon, scope="test")
        if not evaluation_frame.empty:
            evaluation_frames.append(evaluation_frame)
        diagnostic_frame = _evaluation_predictions(
            repo_root,
            h_dir,
            metadata,
            horizon,
            scope="full_dataset_diagnostic",
        )
        if not diagnostic_frame.empty:
            diagnostic_evaluation_frames.append(diagnostic_frame)

    overall = pd.DataFrame(overall_rows)
    per_slice = pd.DataFrame(per_slice_rows)
    confusion = pd.DataFrame(confusion_rows)[
        ["horizon", "slice_name", "threshold", "tp", "fp", "fn", "tn", "support"]
    ] if confusion_rows else pd.DataFrame()
    evaluation_predictions = (
        pd.concat(evaluation_frames, ignore_index=True)
        if evaluation_frames
        else pd.DataFrame()
    )
    diagnostic_predictions = (
        pd.concat(diagnostic_evaluation_frames, ignore_index=True)
        if diagnostic_evaluation_frames
        else pd.DataFrame()
    )
    roc_points = _roc_curve_points(evaluation_predictions)
    diagnostic_metrics = _metrics_from_predictions(diagnostic_predictions)

    overall.to_csv(output_dir / "model_overall_metrics.csv", index=False)
    per_slice.to_csv(output_dir / "model_per_slice_metrics.csv", index=False)
    confusion.to_csv(output_dir / "model_confusion_matrices.csv", index=False)
    if not evaluation_predictions.empty:
        evaluation_predictions.to_csv(output_dir / "model_evaluation_predictions.csv", index=False)
    if not diagnostic_predictions.empty:
        diagnostic_predictions.to_csv(output_dir / "model_diagnostic_predictions.csv", index=False)
    if not diagnostic_metrics.empty:
        diagnostic_metrics.to_csv(output_dir / "model_diagnostic_metrics.csv", index=False)
        _plot_precision_recall(
            diagnostic_metrics.rename(columns={"scope": "evaluation_scope"}),
            output_dir / "diagnostic_precision_recall_f1_by_slice.png",
            title_prefix="Diagnostic",
        )
        _plot_confusion_matrices(
            diagnostic_metrics[["horizon", "slice_name", "tp", "fp", "fn", "tn"]].copy(),
            output_dir / "diagnostic_confusion_matrices.png",
            title="Diagnostic Confusion Matrices by Horizon and Slice",
        )
    if not roc_points.empty:
        roc_points.to_csv(output_dir / "roc_curve_points.csv", index=False)
        _plot_roc_curves(roc_points, output_dir / "roc_curves_by_horizon.png")
    _plot_overall_metrics(overall, output_dir / "roc_auc_accuracy_by_horizon.png")
    _plot_precision_recall(per_slice, output_dir / "precision_recall_f1_by_slice.png", title_prefix="Strict Holdout")
    _plot_confusion_matrices(confusion, output_dir / "confusion_matrices.png", title="Strict Holdout Confusion Matrices by Horizon and Slice")
    _write_controller_rule(output_dir, controller_preset, broker_preset)
    (output_dir / "horizon_models.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    fi_df = pd.DataFrame(columns=["feature", "importance"])
    h1_dir = model_dir / "h1"
    if (h1_dir / "model.joblib").exists() and (h1_dir / "feature_columns.json").exists():
        fi_df = _feature_importance(h1_dir / "model.joblib", h1_dir / "feature_columns.json")
        fi_df.to_csv(output_dir / "feature_importance_h1.csv", index=False)
        _plot_feature_importance(fi_df, output_dir / "feature_importance_top15.png")

    scenario_rows = manifest.get("scenario_summaries", [])
    total_rows = sum(int(row.get("rows", 0)) for row in scenario_rows)
    scenario_text = ", ".join(
        f"{row.get('scenario_name')} ({row.get('rows')} rows)" for row in scenario_rows
    ) or "N/A"

    top_features = fi_df.head(10).copy()
    top_feature_text = _markdown_table(top_features, ["feature", "importance"]) if not top_features.empty else "N/A"
    diagnostic_metric_text = (
        _markdown_table(
            diagnostic_metrics,
            [
                "scope",
                "horizon",
                "slice_name",
                "support",
                "positive_rows",
                "positive_rate",
                "positive_time_min",
                "positive_time_max",
                "precision",
                "recall",
                "f1",
                "roc_auc",
            ],
        )
        if not diagnostic_metrics.empty
        else "N/A"
    )

    report = f"""# 07 Model Report

This report describes the GBDT SLA-risk model used by the closed-loop ML policy.
The model is global to the artifact directory and does not retrain per simulation seed.

## Model Scope

- Model directory: `{model_dir}`
- Model type: `{manifest.get('type', 'multi_horizon_gbdt')}`
- Target mode: `{manifest.get('target_mode', 'N/A')}`
- Dataset version: `{manifest.get('dataset_version', 'N/A')}`
- Training scenarios: {scenario_text}
- Total training rows recorded in manifest: `{total_rows}`
- Current simulation scenario context: `{scenario or 'N/A'}`

## Overall Horizon Metrics

{_markdown_table(overall, ['horizon', 'target_column', 'blend_weight', 'accuracy', 'roc_auc', 'calibration'])}

Visual output: `roc_auc_accuracy_by_horizon.png`.

ROC curve output: `roc_curves_by_horizon.png`. The curve is regenerated from
the saved test split when the training dataset referenced by the model metadata
is available; the raw plotted points are exported to `roc_curve_points.csv`.

## Precision, Recall, F1, and Confusion Matrix

The per-slice metrics below are reconstructed from the threshold-tuning
confusion counts saved in each horizon metadata file.

{_markdown_table(per_slice, ['horizon', 'slice_name', 'threshold', 'support', 'precision', 'recall', 'f1', 'tp', 'fp', 'fn', 'tn'])}

Visual outputs: `precision_recall_f1_by_slice.png` and `confusion_matrices.png`.

## Diagnostic Event-Support Evaluation

The strict holdout split is still the official offline evaluation. However,
eMBB and mMTC positive samples appear only in the early warmup/event window of
the current training scenarios, so the tail holdout has zero positive rows for
those slices. This is why their strict precision/recall/F1 are `N/A`.

The table below is an additional diagnostic pass over the full labelled dataset
to confirm that the saved model can still recognize the available eMBB/mMTC
event rows. It is useful for sanity checking and report explanation, but it
should not be described as an independent holdout score.

{diagnostic_metric_text}

Diagnostic visual outputs: `diagnostic_precision_recall_f1_by_slice.png` and
`diagnostic_confusion_matrices.png`.

## Feature Importance

Feature importance is extracted from the horizon-1 GBDT estimator.

{top_feature_text}

## Threshold and Controller Rule

- Threshold tuning is cost-aware per slice. FN/FP costs are stored in each `h*/metadata.json`.
- Decision thresholds are read from model metadata. If a slice does not define a threshold, the default is `0.5`.
- Multi-horizon inference blends submodel risks using the weights in `horizon_models.json`.
- Controller preset: `{controller_preset or 'N/A'}`.
- Broker preset: `{broker_preset or 'N/A'}`.
- Runtime action schema: `target_ratio`, `scheduling_weight`, and `admission_guard_factor`.
- Below-threshold action scaling is stored in model metadata as `below_threshold_action_scale` when available.
- Detailed controller and broker parameters are exported to `controller_rule.md`,
  `controller_rule_parameters.csv`, and `broker_rule_parameters.csv`.

## Files

- `model_overall_metrics.csv`: accuracy and ROC-AUC by horizon.
- `roc_auc_accuracy_by_horizon.png`: visual summary of accuracy and ROC-AUC.
- `roc_curves_by_horizon.png`: ROC curve by prediction horizon with AUC in the legend.
- `roc_curve_points.csv`: FPR/TPR/threshold points used to draw the ROC curves.
- `model_evaluation_predictions.csv`: reconstructed test-fold labels and probabilities used for ROC.
- `model_per_slice_metrics.csv`: precision/recall/F1 and confusion counts by horizon and slice.
- `precision_recall_f1_by_slice.png`: visual summary of precision/recall/F1 by slice.
- `model_confusion_matrices.csv`: compact TP/FP/FN/TN table.
- `confusion_matrices.png`: visual confusion matrices by horizon and slice.
- `model_diagnostic_metrics.csv`: full-dataset diagnostic metrics with positive-support timing.
- `model_diagnostic_predictions.csv`: labels and probabilities used for diagnostic metrics.
- `diagnostic_precision_recall_f1_by_slice.png`: diagnostic precision/recall/F1 plot.
- `diagnostic_confusion_matrices.png`: diagnostic confusion matrices.
- `feature_importance_h1.csv`: full horizon-1 feature importance table.
- `feature_importance_top15.png`: top feature-importance plot.
- `controller_rule.md`: closed-loop controller and broker rule explanation.
- `controller_rule_parameters.csv`: exported controller preset parameters.
- `broker_rule_parameters.csv`: exported broker preset parameters.
"""
    (output_dir / "model_report.md").write_text(report, encoding="utf-8")

    return output_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export a self-contained GBDT model report.")
    parser.add_argument("--model-dir", default="models/sla_risk_gbdt")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--scenario")
    parser.add_argument("--controller-preset")
    parser.add_argument("--broker-preset")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    output_dir = export_model_report(
        args.model_dir,
        args.output_dir,
        scenario=args.scenario,
        controller_preset=args.controller_preset,
        broker_preset=args.broker_preset,
    )
    print(f"Model report exported to: {output_dir}")


if __name__ == "__main__":
    main()
