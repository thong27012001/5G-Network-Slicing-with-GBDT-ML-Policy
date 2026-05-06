"""Dataset and state-frame builders for the slicing simulator."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ml.feature_schema import (
    METRIC_SHEETS,
    TEMPORAL_DELTA_COLUMNS,
    TEMPORAL_GROUP_COLUMNS,
    TEMPORAL_LAGS,
    TEMPORAL_ROLLING_COLUMNS,
    TEMPORAL_SOURCE_COLUMNS,
    canonicalize_base_station_id,
)
from ml.label_rules import append_sla_labels, shift_future_sla_labels


def load_metric_sheets(excel_path: Path) -> pd.DataFrame:
    metrics = None
    for name in METRIC_SHEETS:
        df = pd.read_excel(excel_path, sheet_name=name)[["sample_index", "value"]]
        df = df.rename(columns={"sample_index": "time", "value": name})
        metrics = df if metrics is None else metrics.merge(df, on="time", how="outer")
    return metrics


def add_temporal_features(
    frame: pd.DataFrame,
    group_columns: list[str] | tuple[str, ...] = TEMPORAL_GROUP_COLUMNS,
    lags: tuple[int, ...] = TEMPORAL_LAGS,
    rolling_window: int = 3,
) -> pd.DataFrame:
    frame = frame.copy()
    grouped = frame.groupby(list(group_columns), group_keys=False)
    generated_features = {}

    for column in TEMPORAL_SOURCE_COLUMNS:
        for lag in lags:
            generated_features[f"{column}_lag{lag}"] = grouped[column].shift(lag)

    for column in TEMPORAL_DELTA_COLUMNS:
        generated_features[f"{column}_delta_1"] = frame[column] - grouped[column].shift(1)
        generated_features[f"{column}_delta_{rolling_window}"] = (
            frame[column] - grouped[column].shift(rolling_window)
        )

    for column, aggregations in TEMPORAL_ROLLING_COLUMNS.items():
        for aggregation in aggregations:
            feature_name = f"{column}_roll{rolling_window}_{aggregation}"
            if aggregation == "mean":
                generated_features[feature_name] = grouped[column].transform(
                    lambda s: s.rolling(rolling_window, min_periods=1).mean()
                )
            elif aggregation == "max":
                generated_features[feature_name] = grouped[column].transform(
                    lambda s: s.rolling(rolling_window, min_periods=1).max()
                )
            elif aggregation == "min":
                generated_features[feature_name] = grouped[column].transform(
                    lambda s: s.rolling(rolling_window, min_periods=1).min()
                )
            elif aggregation == "sum":
                generated_features[feature_name] = grouped[column].transform(
                    lambda s: s.rolling(rolling_window, min_periods=1).sum()
                )
            else:
                raise ValueError(f"Unsupported rolling aggregation: {aggregation}")

    temporal_frame = pd.DataFrame(generated_features, index=frame.index)
    frame = pd.concat([frame, temporal_frame], axis=1)
    frame["window_index"] = grouped.cumcount()
    frame["observed_windows_per_group"] = grouped["time"].transform("count")

    max_lag = max(lags)
    return frame[frame["window_index"] >= max_lag].copy()


def build_state_frame(
    excel_path: Path,
    sla_path: Path,
    include_temporal_features: bool = False,
    temporal_lags: tuple[int, ...] = TEMPORAL_LAGS,
    rolling_window: int = 3,
) -> pd.DataFrame:
    """Build a labeled current-state frame without future-horizon targets."""
    connection_events = pd.read_excel(excel_path, sheet_name="ConnectionEvents")
    requests = pd.read_excel(excel_path, sheet_name="Requests")
    metrics = load_metric_sheets(excel_path)
    sla_reference = pd.read_csv(sla_path)

    if "base_station_id" in connection_events.columns:
        connection_events["base_station_id"] = connection_events["base_station_id"].map(canonicalize_base_station_id)
    if "base_station_id" in requests.columns:
        requests["base_station_id"] = requests["base_station_id"].map(canonicalize_base_station_id)

    rows = connection_events[connection_events["slice_name"].notna()].copy()
    rows["distance_to_bs"] = np.sqrt(
        (rows["client_x"] - rows["base_station_center_x"]) ** 2
        + (rows["client_y"] - rows["base_station_center_y"]) ** 2
    )
    rows["slice_load_ratio"] = np.where(
        rows["slice_init_capacity"] > 0,
        rows["slice_used_diff"] / rows["slice_init_capacity"],
        0.0,
    )
    rows["remaining_capacity_ratio"] = np.where(
        rows["slice_init_capacity"] > 0,
        rows["slice_capacity_level"] / rows["slice_init_capacity"],
        0.0,
    )

    request_context = rows[["time", "client_id", "slice_name", "base_station_id"]].drop_duplicates(
        ["time", "client_id"]
    )
    requests = requests.merge(request_context, on=["time", "client_id"], how="left")

    aggregated = rows.groupby(["time", "slice_name", "base_station_id"], as_index=False).agg(
        clients_seen=("client_id", "nunique"),
        connected_events=("event", lambda s: int((s == "connected to").sum())),
        disconnected_events=("event", lambda s: int((s == "disconnected from").sum())),
        already_disconnected_events=("event", lambda s: int((s == "already disconnected").sum())),
        slice_init_capacity=("slice_init_capacity", "median"),
        slice_capacity_level=("slice_capacity_level", "median"),
        slice_used_diff=("slice_used_diff", "median"),
        base_station_capacity=("base_station_capacity", "median"),
        base_station_radius=("base_station_radius", "median"),
        mean_distance_to_bs=("distance_to_bs", "mean"),
        max_distance_to_bs=("distance_to_bs", "max"),
        mean_slice_load_ratio=("slice_load_ratio", "mean"),
        mean_remaining_capacity_ratio=("remaining_capacity_ratio", "mean"),
    )

    request_aggregates = (
        requests.dropna(subset=["slice_name", "base_station_id"])
        .groupby(["time", "slice_name", "base_station_id"], as_index=False)
        .agg(
            request_count=("client_id", "count"),
            requested_usage_sum=("requested_usage", "sum"),
            requested_usage_mean=("requested_usage", "mean"),
            requested_usage_max=("requested_usage", "max"),
        )
    )

    aggregated = aggregated.merge(
        request_aggregates,
        on=["time", "slice_name", "base_station_id"],
        how="left",
    )
    aggregated = aggregated.merge(metrics, on="time", how="left")
    aggregated = aggregated.merge(sla_reference, on="slice_name", how="left")
    aggregated["base_station_id"] = aggregated["base_station_id"].map(canonicalize_base_station_id)

    for column in ["request_count", "requested_usage_sum", "requested_usage_mean", "requested_usage_max"]:
        aggregated[column] = aggregated[column].fillna(0)

    aggregated = append_sla_labels(aggregated)
    aggregated = aggregated.sort_values(TEMPORAL_GROUP_COLUMNS + ["time"]).reset_index(drop=True)

    if include_temporal_features:
        aggregated = add_temporal_features(
            aggregated,
            group_columns=TEMPORAL_GROUP_COLUMNS,
            lags=temporal_lags,
            rolling_window=rolling_window,
        )

    max_priority_rank = aggregated["priority_rank"].max()
    aggregated["sample_weight"] = (max_priority_rank + 1 - aggregated["priority_rank"]).clip(lower=1)
    return aggregated


def build_training_frame(
    excel_path: Path,
    sla_path: Path,
    horizon: int = 1,
    include_temporal_features: bool = False,
    temporal_lags: tuple[int, ...] = TEMPORAL_LAGS,
    rolling_window: int = 3,
) -> pd.DataFrame:
    """Build a future-labeled training frame for supervised learning."""
    aggregated = build_state_frame(
        excel_path,
        sla_path,
        include_temporal_features=include_temporal_features,
        temporal_lags=temporal_lags,
        rolling_window=rolling_window,
    )
    aggregated = aggregated.sort_values(TEMPORAL_GROUP_COLUMNS + ["time"])
    return shift_future_sla_labels(
        aggregated,
        group_columns=TEMPORAL_GROUP_COLUMNS,
        horizon=horizon,
    )
