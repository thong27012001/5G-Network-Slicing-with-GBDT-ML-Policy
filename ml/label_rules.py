"""SLA labeling rules shared by offline training and online inference."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml.feature_schema import SLA_LABEL_TO_ID, WARN_SAFETY_THRESHOLD


def _normalized_min_safety(actual: pd.Series, threshold: pd.Series) -> pd.Series:
    return (actual - threshold) / np.maximum(1 - threshold, 1e-6)


def _normalized_max_safety(actual: pd.Series, threshold: pd.Series) -> pd.Series:
    return (threshold - actual) / np.maximum(threshold, 1e-6)


def append_sla_labels(
    frame: pd.DataFrame,
    warn_safety_threshold: float = WARN_SAFETY_THRESHOLD,
) -> pd.DataFrame:
    """Attach SLA-derived current labels to a state frame."""
    frame = frame.copy()
    safety_columns = {
        "connected_ratio_safety": _normalized_min_safety(
            frame["connected_clients_ratio"],
            frame["min_connected_ratio"],
        ),
        "coverage_ratio_safety": _normalized_min_safety(
            frame["coverage_ratio"],
            frame["min_coverage_ratio"],
        ),
        "block_ratio_safety": _normalized_max_safety(
            frame["block_ratio"],
            frame["max_block_ratio"],
        ),
        "handover_ratio_safety": _normalized_max_safety(
            frame["handover_ratio"],
            frame["max_handover_ratio"],
        ),
        "avg_slice_load_ratio_safety": _normalized_max_safety(
            frame["avg_slice_load_ratio"],
            frame["max_avg_slice_load_ratio"],
        ),
        "avg_latency_ms_safety": _normalized_max_safety(
            frame["avg_latency_ms"],
            frame["max_avg_latency_ms"],
        ),
        "p95_latency_ms_safety": _normalized_max_safety(
            frame["p95_latency_ms"],
            frame["max_p95_latency_ms"],
        ),
        "latency_violation_ratio_safety": _normalized_max_safety(
            frame["latency_violation_ratio"],
            frame["max_latency_violation_ratio"],
        ),
    }
    metric_aliases = {
        "connected_ratio_safety": "connected_clients_ratio",
        "coverage_ratio_safety": "coverage_ratio",
        "block_ratio_safety": "block_ratio",
        "handover_ratio_safety": "handover_ratio",
        "avg_slice_load_ratio_safety": "avg_slice_load_ratio",
        "avg_latency_ms_safety": "avg_latency_ms",
        "p95_latency_ms_safety": "p95_latency_ms",
        "latency_violation_ratio_safety": "latency_violation_ratio",
    }

    for column, values in safety_columns.items():
        frame[column] = values

    safety_column_names = list(safety_columns.keys())
    safety_matrix = frame[safety_column_names]
    frame["current_sla_margin_score"] = safety_matrix.min(axis=1)
    frame["current_sla_breach_count"] = safety_matrix.lt(0).sum(axis=1)
    frame["current_sla_near_breach_count"] = safety_matrix.lt(warn_safety_threshold).sum(axis=1)
    worst_metric_index = np.argmin(safety_matrix.to_numpy(), axis=1)
    frame["current_sla_bottleneck_metric"] = [
        metric_aliases[safety_column_names[index]] for index in worst_metric_index
    ]

    current_violation = frame["current_sla_breach_count"] > 0
    current_warn = (~current_violation) & (frame["current_sla_margin_score"] < warn_safety_threshold)

    frame["current_sla_label"] = np.select(
        [current_violation, current_warn],
        ["violation", "warn"],
        default="normal",
    )
    frame["current_sla_label_id"] = frame["current_sla_label"].map(SLA_LABEL_TO_ID).astype(int)
    frame["current_sla_violation"] = current_violation.astype(int)
    return frame


def shift_future_sla_labels(
    frame: pd.DataFrame,
    group_columns: list[str] | tuple[str, ...],
    horizon: int = 1,
) -> pd.DataFrame:
    """Shift current SLA labels into a future-horizon training target."""
    frame = frame.copy()
    grouped = frame.groupby(list(group_columns))
    frame["next_sla_violation"] = grouped["current_sla_violation"].shift(-horizon)
    frame["next_sla_label"] = grouped["current_sla_label"].shift(-horizon)
    frame["next_sla_label_id"] = grouped["current_sla_label_id"].shift(-horizon)
    frame["next_sla_margin_score"] = grouped["current_sla_margin_score"].shift(-horizon)
    frame["next_sla_breach_count"] = grouped["current_sla_breach_count"].shift(-horizon)
    frame["next_sla_near_breach_count"] = grouped["current_sla_near_breach_count"].shift(-horizon)
    frame["next_sla_bottleneck_metric"] = grouped["current_sla_bottleneck_metric"].shift(-horizon)

    frame = frame.dropna(subset=["next_sla_violation", "next_sla_label", "next_sla_label_id"]).copy()
    frame["next_sla_violation"] = frame["next_sla_violation"].astype(int)
    frame["next_sla_label_id"] = frame["next_sla_label_id"].astype(int)
    return frame


def add_any_violation_in_horizon(
    frame: pd.DataFrame,
    group_columns: list[str] | tuple[str, ...],
    horizons: tuple[int, ...] | list[int] = (3, 5),
) -> pd.DataFrame:
    """Append `next_sla_violation_any_h{H}` and severity targets for each horizon.

    For each row at time t and each H in `horizons`, the target is 1 if any of the
    next H windows (t+1..t+H) is labeled violation (per the simulator's current_sla_violation).
    Severity target is the worst (most negative) margin score over the same window.

    The frame is then trimmed to rows where the largest horizon target is defined,
    so all `next_sla_violation_any_h{H}` columns are non-NaN.
    """
    if "current_sla_violation" not in frame.columns or "current_sla_margin_score" not in frame.columns:
        raise ValueError(
            "add_any_violation_in_horizon requires `current_sla_violation` and "
            "`current_sla_margin_score` columns. Run append_sla_labels first."
        )
    horizons = sorted({int(h) for h in horizons if int(h) > 0})
    if not horizons:
        raise ValueError("`horizons` must contain at least one positive integer.")

    frame = frame.copy()
    grouped = frame.groupby(list(group_columns))

    for horizon in horizons:
        future_violations = []
        future_severities = []
        for step in range(1, horizon + 1):
            future_violations.append(grouped["current_sla_violation"].shift(-step))
            future_severities.append(-grouped["current_sla_margin_score"].shift(-step))
        violation_target = pd.concat(future_violations, axis=1).max(axis=1)
        severity_target = pd.concat(future_severities, axis=1).max(axis=1)
        frame[f"next_sla_violation_any_h{horizon}"] = violation_target
        frame[f"next_sla_severity_max_h{horizon}"] = severity_target

    largest_horizon = max(horizons)
    keep_column = f"next_sla_violation_any_h{largest_horizon}"
    frame = frame.dropna(subset=[keep_column]).copy()

    for horizon in horizons:
        column = f"next_sla_violation_any_h{horizon}"
        frame[column] = frame[column].astype(int)

    return frame
