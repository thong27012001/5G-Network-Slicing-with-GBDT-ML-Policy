from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import pandas as pd

from integration.closed_loop_runner import run_online_baseline, run_online_closed_loop
from evaluate_policy_guardrails import evaluate_strict_guardrails, _write_report as _write_guardrail_report
from organize_pipeline_outputs import organize_pipeline_outputs


GLOBAL_METRICS = [
    "connected_clients_ratio",
    "coverage_ratio",
    "block_ratio",
    "handover_ratio",
    "avg_slice_load_ratio",
    "total_bandwidth_usage",
    "avg_latency_ms",
    "p95_latency_ms",
    "latency_violation_ratio",
]

SLICE_ORDER = ["URLLC", "eMBB", "mMTC"]
SLICE_COLORS = {
    "URLLC": "#c23b22",
    "eMBB": "#1f77b4",
    "mMTC": "#2ca02c",
}

plt.rcParams.update(
    {
        "font.family": "serif",
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.titleweight": "bold",
        "axes.labelsize": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "grid.alpha": 0.3,
        "grid.linestyle": "--",
        "savefig.bbox": "tight",
        "savefig.dpi": 300,
    }
)

METRICS_HIGHER_IS_BETTER = {
    "connected_clients_ratio",
    "coverage_ratio",
    "total_bandwidth_usage",
    "bandwidth_jain_fairness",
    "bandwidth_jain_fairness_min",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parent


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _resolve_config_path(repo_root: Path, args: argparse.Namespace) -> Path:
    if args.config:
        return Path(args.config)
    if args.scenario:
        return repo_root / "slicesim" / f"scenario-{args.scenario}-output.yml"
    raise ValueError("Provide either --config or --scenario.")


def _read_csv(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path)


def _jain_fairness(values) -> float:
    cleaned = [max(float(value), 0.0) for value in values if pd.notna(value)]
    if not cleaned:
        return 0.0
    squared_sum = sum(value * value for value in cleaned)
    if squared_sum <= 0:
        return 0.0
    return (sum(cleaned) ** 2) / (len(cleaned) * squared_sum)


def _global_metric_series(state_frame: pd.DataFrame) -> pd.DataFrame:
    if state_frame.empty:
        return pd.DataFrame(columns=["time"] + GLOBAL_METRICS)
    return (
        state_frame.sort_values("time")
        .drop_duplicates(subset=["time"])
        [["time"] + GLOBAL_METRICS]
        .reset_index(drop=True)
    )


def _global_metric_summary(state_frame: pd.DataFrame) -> dict[str, float]:
    metric_series = _global_metric_series(state_frame)
    summary = {
        metric: float(metric_series[metric].mean()) if metric in metric_series.columns and not metric_series.empty else 0.0
        for metric in GLOBAL_METRICS
    }
    if not state_frame.empty and "current_sla_violation" in state_frame.columns:
        per_time = state_frame.groupby("time", as_index=False)["current_sla_violation"].mean()
        summary["avg_state_sla_violation_share"] = float(per_time["current_sla_violation"].mean())
    else:
        summary["avg_state_sla_violation_share"] = 0.0
    summary.update(_bandwidth_fairness_summary(state_frame))
    return summary


def _slice_bandwidth_series(state_frame: pd.DataFrame) -> pd.DataFrame:
    if state_frame.empty:
        return pd.DataFrame(columns=["time", "slice_name", "bandwidth_usage_bps", "bandwidth_usage_mbps"])
    series = (
        state_frame.groupby(["time", "slice_name"], as_index=False)["slice_used_diff"]
        .sum()
        .rename(columns={"slice_used_diff": "bandwidth_usage_bps"})
    )
    series["bandwidth_usage_mbps"] = series["bandwidth_usage_bps"] / 1_000_000.0
    return series


def _bandwidth_fairness_summary(state_frame: pd.DataFrame) -> dict[str, float]:
    if state_frame.empty:
        return {"bandwidth_jain_fairness": 0.0, "bandwidth_jain_fairness_min": 0.0}
    bandwidth = _slice_bandwidth_series(state_frame)
    if bandwidth.empty:
        return {"bandwidth_jain_fairness": 0.0, "bandwidth_jain_fairness_min": 0.0}
    pivot = (
        bandwidth.pivot_table(
            index="time",
            columns="slice_name",
            values="bandwidth_usage_mbps",
            aggfunc="sum",
            fill_value=0.0,
        )
        .reindex(columns=SLICE_ORDER, fill_value=0.0)
        .sort_index()
    )
    fairness = pivot.apply(lambda row: _jain_fairness(row.tolist()), axis=1)
    if fairness.empty:
        return {"bandwidth_jain_fairness": 0.0, "bandwidth_jain_fairness_min": 0.0}
    return {
        "bandwidth_jain_fairness": float(fairness.mean()),
        "bandwidth_jain_fairness_min": float(fairness.min()),
    }


def _slice_bandwidth_diagnostics(state_frame: pd.DataFrame) -> pd.DataFrame:
    bandwidth = _slice_bandwidth_series(state_frame)
    if bandwidth.empty:
        return pd.DataFrame(
            columns=[
                "slice_name",
                "avg_bandwidth_share",
                "zero_bandwidth_window_share",
            ]
        )
    totals = bandwidth.groupby("time", as_index=False)["bandwidth_usage_mbps"].sum().rename(
        columns={"bandwidth_usage_mbps": "total_bandwidth_usage_mbps"}
    )
    bandwidth = bandwidth.merge(totals, on="time", how="left")
    bandwidth["bandwidth_share"] = bandwidth.apply(
        lambda row: row["bandwidth_usage_mbps"] / row["total_bandwidth_usage_mbps"]
        if row["total_bandwidth_usage_mbps"] > 0
        else 0.0,
        axis=1,
    )
    bandwidth["zero_bandwidth_window"] = bandwidth["bandwidth_usage_mbps"] <= 1e-12
    return bandwidth.groupby("slice_name", as_index=False).agg(
        avg_bandwidth_share=("bandwidth_share", "mean"),
        zero_bandwidth_window_share=("zero_bandwidth_window", "mean"),
    )


def _slice_sla_violation_series(state_frame: pd.DataFrame) -> pd.DataFrame:
    if state_frame.empty or "current_sla_violation" not in state_frame.columns:
        return pd.DataFrame(columns=["time", "slice_name", "sla_violation_share"])
    return (
        state_frame.groupby(["time", "slice_name"], as_index=False)["current_sla_violation"]
        .mean()
        .rename(columns={"current_sla_violation": "sla_violation_share"})
    )


def _slice_sla_margin_summary(state_frame: pd.DataFrame) -> pd.DataFrame:
    if state_frame.empty or "current_sla_margin_score" not in state_frame.columns:
        return pd.DataFrame(columns=["slice_name", "avg_sla_safety_margin"])
    return state_frame.groupby("slice_name", as_index=False).agg(
        avg_sla_safety_margin=("current_sla_margin_score", "mean"),
    )


def _slice_client_summary(client_summary: pd.DataFrame) -> pd.DataFrame:
    if client_summary.empty:
        return pd.DataFrame(
            columns=[
                "slice_name",
                "total_request_count",
                "total_completed_requests",
                "completion_ratio",
                "avg_served_bandwidth",
                "avg_completion_latency_ms",
                "avg_first_service_latency_ms",
                "completion_latency_violation_ratio",
                "first_service_latency_violation_ratio",
                "request_latency_violation_event_ratio",
            ]
        )

    grouped = client_summary.groupby("slice_name", as_index=False).agg(
        total_request_count=("total_request_count", "sum"),
        total_completed_requests=("total_completed_requests", "sum"),
        total_consume_time=("total_consume_time", "sum"),
        total_usage=("total_usage", "sum"),
        total_latency_ms=("total_latency_ms", "sum"),
        total_first_service_latency_ms=("total_first_service_latency_ms", "sum"),
        completion_latency_violation_count=("completion_latency_violation_count", "sum"),
        first_service_latency_violation_count=("first_service_latency_violation_count", "sum"),
    )

    grouped["completion_ratio"] = grouped.apply(
        lambda row: row["total_completed_requests"] / row["total_request_count"]
        if row["total_request_count"] > 0
        else 0.0,
        axis=1,
    )
    grouped["avg_served_bandwidth"] = grouped.apply(
        lambda row: row["total_usage"] / row["total_consume_time"]
        if row["total_consume_time"] > 0
        else 0.0,
        axis=1,
    )
    grouped["avg_completion_latency_ms"] = grouped.apply(
        lambda row: row["total_latency_ms"] / row["total_completed_requests"]
        if row["total_completed_requests"] > 0
        else 0.0,
        axis=1,
    )
    grouped["avg_first_service_latency_ms"] = grouped.apply(
        lambda row: row["total_first_service_latency_ms"] / row["total_request_count"]
        if row["total_request_count"] > 0
        else 0.0,
        axis=1,
    )
    grouped["completion_latency_violation_ratio"] = grouped.apply(
        lambda row: row["completion_latency_violation_count"] / row["total_completed_requests"]
        if row["total_completed_requests"] > 0
        else 0.0,
        axis=1,
    )
    grouped["first_service_latency_violation_ratio"] = grouped.apply(
        lambda row: row["first_service_latency_violation_count"] / row["total_request_count"]
        if row["total_request_count"] > 0
        else 0.0,
        axis=1,
    )
    grouped["request_latency_violation_event_ratio"] = grouped.apply(
        lambda row: (
            row["completion_latency_violation_count"] + row["first_service_latency_violation_count"]
        )
        / (row["total_completed_requests"] + row["total_request_count"])
        if (row["total_completed_requests"] + row["total_request_count"]) > 0
        else 0.0,
        axis=1,
    )
    return grouped


def _slice_latency_summary(latency_series: pd.DataFrame, value_column: str) -> pd.DataFrame:
    if latency_series.empty:
        recorded_column = value_column.replace("avg_", "avg_recorded_")
        return pd.DataFrame(columns=["slice_name", value_column, recorded_column])

    all_windows = latency_series.groupby("slice_name", as_index=False)[value_column].mean()
    recorded_column = value_column.replace("avg_", "avg_recorded_")
    positive_only = latency_series[latency_series[value_column] > 0]
    if positive_only.empty:
        all_windows[recorded_column] = 0.0
        return all_windows

    recorded_only = positive_only.groupby("slice_name", as_index=False)[value_column].mean().rename(
        columns={value_column: recorded_column}
    )
    return all_windows.merge(recorded_only, on="slice_name", how="left").fillna({recorded_column: 0.0})


def _per_slice_summary(
    state_frame: pd.DataFrame,
    client_summary: pd.DataFrame,
    completion_latency_series: pd.DataFrame,
    first_service_latency_series: pd.DataFrame,
) -> pd.DataFrame:
    usage_summary = _slice_bandwidth_series(state_frame).groupby("slice_name", as_index=False).agg(
        avg_bandwidth_usage_mbps=("bandwidth_usage_mbps", "mean"),
    )
    bandwidth_diagnostics = _slice_bandwidth_diagnostics(state_frame)
    sla_summary = _slice_sla_violation_series(state_frame).groupby("slice_name", as_index=False).agg(
        avg_state_sla_violation_share=("sla_violation_share", "mean"),
    )
    sla_margin_summary = _slice_sla_margin_summary(state_frame)
    client_agg = _slice_client_summary(client_summary)
    completion_summary = _slice_latency_summary(completion_latency_series, "avg_completion_latency_ms")
    first_service_summary = _slice_latency_summary(first_service_latency_series, "avg_first_service_latency_ms")

    summary = usage_summary.merge(sla_summary, on="slice_name", how="outer")
    summary = summary.merge(sla_margin_summary, on="slice_name", how="outer")
    summary = summary.merge(bandwidth_diagnostics, on="slice_name", how="outer")
    summary = summary.merge(
        client_agg[
            [
                "slice_name",
                "completion_ratio",
                "avg_served_bandwidth",
                "avg_completion_latency_ms",
                "avg_first_service_latency_ms",
                "completion_latency_violation_ratio",
                "first_service_latency_violation_ratio",
                "request_latency_violation_event_ratio",
            ]
        ],
        on="slice_name",
        how="outer",
        suffixes=("", "_client"),
    )
    summary = summary.merge(
        completion_summary.rename(columns={"avg_completion_latency_ms": "avg_completion_latency_ms_series"}),
        on="slice_name",
        how="outer",
    )
    summary = summary.merge(
        first_service_summary.rename(columns={"avg_first_service_latency_ms": "avg_first_service_latency_ms_series"}),
        on="slice_name",
        how="outer",
    )

    summary["avg_completion_latency_ms"] = summary["avg_completion_latency_ms_series"].fillna(
        summary["avg_completion_latency_ms"]
    )
    summary["avg_first_service_latency_ms"] = summary["avg_first_service_latency_ms_series"].fillna(
        summary["avg_first_service_latency_ms"]
    )
    summary = summary.drop(
        columns=[
            column
            for column in ["avg_completion_latency_ms_series", "avg_first_service_latency_ms_series"]
            if column in summary.columns
        ]
    )

    for column in summary.columns:
        if column != "slice_name":
            summary[column] = summary[column].fillna(0.0)

    summary["slice_name"] = pd.Categorical(summary["slice_name"], categories=SLICE_ORDER, ordered=True)
    return summary.sort_values("slice_name").reset_index(drop=True)


def _comparison_table(baseline: dict[str, float], ml: dict[str, float]) -> pd.DataFrame:
    rows = []
    for metric in baseline:
        baseline_value = float(baseline.get(metric, 0.0))
        ml_value = float(ml.get(metric, 0.0))
        delta = ml_value - baseline_value
        delta_pct = (delta / baseline_value * 100.0) if baseline_value not in (0.0, -0.0) else 0.0
        rows.append(
            {
                "metric": metric,
                "baseline": baseline_value,
                "ml_policy": ml_value,
                "delta_ml_minus_baseline": delta,
                "delta_pct": delta_pct,
            }
        )
    return pd.DataFrame(rows)


def _per_slice_comparison_table(baseline: pd.DataFrame, ml: pd.DataFrame) -> pd.DataFrame:
    merged = baseline.merge(ml, on="slice_name", how="outer", suffixes=("_baseline", "_ml"))
    numeric_columns = [column for column in merged.columns if column != "slice_name"]
    for column in numeric_columns:
        merged[column] = merged[column].fillna(0.0)

    comparison_rows = []
    tracked_metrics = [
        "avg_bandwidth_usage_mbps",
        "avg_served_bandwidth",
        "avg_completion_latency_ms",
        "avg_first_service_latency_ms",
        "avg_recorded_first_service_latency_ms",
        "avg_bandwidth_share",
        "zero_bandwidth_window_share",
        "completion_ratio",
        "completion_latency_violation_ratio",
        "first_service_latency_violation_ratio",
        "request_latency_violation_event_ratio",
        "avg_state_sla_violation_share",
        "avg_sla_safety_margin",
    ]
    for _, row in merged.iterrows():
        item = {"slice_name": row["slice_name"]}
        for metric in tracked_metrics:
            base_col = f"{metric}_baseline"
            ml_col = f"{metric}_ml"
            item[f"{metric}_baseline"] = float(row.get(base_col, 0.0))
            item[f"{metric}_ml"] = float(row.get(ml_col, 0.0))
            item[f"{metric}_delta"] = item[f"{metric}_ml"] - item[f"{metric}_baseline"]
        baseline_margin = item["avg_sla_safety_margin_baseline"]
        margin_delta = item["avg_sla_safety_margin_delta"]
        item["avg_sla_safety_margin_improvement_pct"] = (
            margin_delta / abs(baseline_margin) * 100.0 if abs(baseline_margin) > 1e-12 else 0.0
        )
        comparison_rows.append(item)
    return pd.DataFrame(comparison_rows)


def _per_base_station_summary(state_frame: pd.DataFrame) -> pd.DataFrame:
    """Aggregate simulator state into BTS-level KPI summary.

    Latency columns in the current state frame are global per-window values, so
    this summary only uses fields that are explicitly keyed by base_station_id.
    """
    columns = [
        "base_station_id",
        "avg_bandwidth_usage_mbps",
        "avg_capacity_mbps",
        "avg_load_ratio",
        "avg_remaining_capacity_ratio",
        "avg_request_count_per_window",
        "total_request_count",
        "avg_requested_usage_mbps_per_window",
        "avg_clients_seen_per_window",
        "avg_connected_events_per_window",
        "avg_disconnected_events_per_window",
        "avg_state_sla_violation_share",
        "avg_sla_safety_margin",
        "avg_sla_breach_count_per_window",
    ]
    if state_frame.empty or "base_station_id" not in state_frame.columns:
        return pd.DataFrame(columns=columns)

    frame = state_frame.copy()
    numeric_defaults = {
        "slice_used_diff": 0.0,
        "slice_init_capacity": 0.0,
        "slice_capacity_level": 0.0,
        "base_station_capacity": 0.0,
        "request_count": 0.0,
        "requested_usage_sum": 0.0,
        "clients_seen": 0.0,
        "connected_events": 0.0,
        "disconnected_events": 0.0,
        "current_sla_violation": 0.0,
        "current_sla_margin_score": 0.0,
        "current_sla_breach_count": 0.0,
    }
    for column, default in numeric_defaults.items():
        if column not in frame.columns:
            frame[column] = default
        frame[column] = frame[column].fillna(default).astype(float)

    grouped = (
        frame.groupby(["time", "base_station_id"], as_index=False)
        .agg(
            bandwidth_usage_bps=("slice_used_diff", "sum"),
            slice_capacity_bps=("slice_init_capacity", "sum"),
            remaining_capacity_bps=("slice_capacity_level", "sum"),
            base_station_capacity_bps=("base_station_capacity", "max"),
            request_count=("request_count", "sum"),
            requested_usage_sum=("requested_usage_sum", "sum"),
            clients_seen=("clients_seen", "sum"),
            connected_events=("connected_events", "sum"),
            disconnected_events=("disconnected_events", "sum"),
            state_sla_violation_share=("current_sla_violation", "mean"),
            sla_safety_margin=("current_sla_margin_score", "mean"),
            sla_breach_count=("current_sla_breach_count", "sum"),
        )
        .copy()
    )
    grouped["load_ratio"] = grouped.apply(
        lambda row: row["bandwidth_usage_bps"] / row["base_station_capacity_bps"]
        if row["base_station_capacity_bps"] > 0
        else 0.0,
        axis=1,
    )
    grouped["remaining_capacity_ratio"] = grouped.apply(
        lambda row: row["remaining_capacity_bps"] / row["slice_capacity_bps"]
        if row["slice_capacity_bps"] > 0
        else 0.0,
        axis=1,
    )

    summary = grouped.groupby("base_station_id", as_index=False).agg(
        avg_bandwidth_usage_mbps=("bandwidth_usage_bps", lambda value: float(value.mean()) / 1_000_000.0),
        avg_capacity_mbps=("base_station_capacity_bps", lambda value: float(value.mean()) / 1_000_000.0),
        avg_load_ratio=("load_ratio", "mean"),
        avg_remaining_capacity_ratio=("remaining_capacity_ratio", "mean"),
        avg_request_count_per_window=("request_count", "mean"),
        total_request_count=("request_count", "sum"),
        avg_requested_usage_mbps_per_window=("requested_usage_sum", lambda value: float(value.mean()) / 1_000_000.0),
        avg_clients_seen_per_window=("clients_seen", "mean"),
        avg_connected_events_per_window=("connected_events", "mean"),
        avg_disconnected_events_per_window=("disconnected_events", "mean"),
        avg_state_sla_violation_share=("state_sla_violation_share", "mean"),
        avg_sla_safety_margin=("sla_safety_margin", "mean"),
        avg_sla_breach_count_per_window=("sla_breach_count", "mean"),
    )
    for column in columns:
        if column not in summary.columns:
            summary[column] = 0.0
    return summary[columns].sort_values("base_station_id").reset_index(drop=True)


def _per_base_station_comparison_table(baseline: pd.DataFrame, ml: pd.DataFrame) -> pd.DataFrame:
    merged = baseline.merge(ml, on="base_station_id", how="outer", suffixes=("_baseline", "_ml"))
    numeric_columns = [column for column in merged.columns if column != "base_station_id"]
    for column in numeric_columns:
        merged[column] = merged[column].fillna(0.0)

    tracked_metrics = [
        "avg_bandwidth_usage_mbps",
        "avg_capacity_mbps",
        "avg_load_ratio",
        "avg_remaining_capacity_ratio",
        "avg_request_count_per_window",
        "total_request_count",
        "avg_requested_usage_mbps_per_window",
        "avg_clients_seen_per_window",
        "avg_connected_events_per_window",
        "avg_disconnected_events_per_window",
        "avg_state_sla_violation_share",
        "avg_sla_safety_margin",
        "avg_sla_breach_count_per_window",
    ]
    rows = []
    for _, row in merged.iterrows():
        item = {"base_station_id": row["base_station_id"]}
        for metric in tracked_metrics:
            baseline_value = float(row.get(f"{metric}_baseline", 0.0))
            ml_value = float(row.get(f"{metric}_ml", 0.0))
            item[f"{metric}_baseline"] = baseline_value
            item[f"{metric}_ml"] = ml_value
            item[f"{metric}_delta"] = ml_value - baseline_value
            item[f"{metric}_delta_pct"] = (
                item[f"{metric}_delta"] / baseline_value * 100.0 if abs(baseline_value) > 1e-12 else 0.0
            )
        rows.append(item)
    return pd.DataFrame(rows).sort_values("base_station_id").reset_index(drop=True)


def _per_base_station_slice_summary(state_frame: pd.DataFrame) -> pd.DataFrame:
    """Aggregate simulator state into BTS-and-slice SLA summary."""
    keys = ["base_station_id", "slice_name"]
    columns = [
        *keys,
        "avg_bandwidth_usage_mbps",
        "avg_slice_capacity_mbps",
        "avg_slice_load_ratio",
        "avg_remaining_capacity_ratio",
        "avg_request_count_per_window",
        "total_request_count",
        "avg_requested_usage_mbps_per_window",
        "avg_clients_seen_per_window",
        "avg_state_sla_violation_share",
        "avg_sla_safety_margin",
        "avg_sla_breach_count_per_window",
    ]
    if state_frame.empty or not set(keys).issubset(state_frame.columns):
        return pd.DataFrame(columns=columns)

    frame = state_frame.copy()
    numeric_defaults = {
        "slice_used_diff": 0.0,
        "slice_init_capacity": 0.0,
        "slice_capacity_level": 0.0,
        "request_count": 0.0,
        "requested_usage_sum": 0.0,
        "clients_seen": 0.0,
        "current_sla_violation": 0.0,
        "current_sla_margin_score": 0.0,
        "current_sla_breach_count": 0.0,
    }
    for column, default in numeric_defaults.items():
        if column not in frame.columns:
            frame[column] = default
        frame[column] = frame[column].fillna(default).astype(float)

    grouped = (
        frame.groupby(["time", *keys], as_index=False)
        .agg(
            bandwidth_usage_bps=("slice_used_diff", "sum"),
            slice_capacity_bps=("slice_init_capacity", "sum"),
            remaining_capacity_bps=("slice_capacity_level", "sum"),
            request_count=("request_count", "sum"),
            requested_usage_sum=("requested_usage_sum", "sum"),
            clients_seen=("clients_seen", "sum"),
            state_sla_violation_share=("current_sla_violation", "mean"),
            sla_safety_margin=("current_sla_margin_score", "mean"),
            sla_breach_count=("current_sla_breach_count", "sum"),
        )
        .copy()
    )
    grouped["slice_load_ratio"] = grouped.apply(
        lambda row: row["bandwidth_usage_bps"] / row["slice_capacity_bps"]
        if row["slice_capacity_bps"] > 0
        else 0.0,
        axis=1,
    )
    grouped["remaining_capacity_ratio"] = grouped.apply(
        lambda row: row["remaining_capacity_bps"] / row["slice_capacity_bps"]
        if row["slice_capacity_bps"] > 0
        else 0.0,
        axis=1,
    )

    summary = grouped.groupby(keys, as_index=False).agg(
        avg_bandwidth_usage_mbps=("bandwidth_usage_bps", lambda value: float(value.mean()) / 1_000_000.0),
        avg_slice_capacity_mbps=("slice_capacity_bps", lambda value: float(value.mean()) / 1_000_000.0),
        avg_slice_load_ratio=("slice_load_ratio", "mean"),
        avg_remaining_capacity_ratio=("remaining_capacity_ratio", "mean"),
        avg_request_count_per_window=("request_count", "mean"),
        total_request_count=("request_count", "sum"),
        avg_requested_usage_mbps_per_window=("requested_usage_sum", lambda value: float(value.mean()) / 1_000_000.0),
        avg_clients_seen_per_window=("clients_seen", "mean"),
        avg_state_sla_violation_share=("state_sla_violation_share", "mean"),
        avg_sla_safety_margin=("sla_safety_margin", "mean"),
        avg_sla_breach_count_per_window=("sla_breach_count", "mean"),
    )
    for column in columns:
        if column not in summary.columns:
            summary[column] = 0.0
    return summary[columns].sort_values(keys).reset_index(drop=True)


def _per_base_station_slice_comparison_table(baseline: pd.DataFrame, ml: pd.DataFrame) -> pd.DataFrame:
    keys = ["base_station_id", "slice_name"]
    merged = baseline.merge(ml, on=keys, how="outer", suffixes=("_baseline", "_ml"))
    numeric_columns = [column for column in merged.columns if column not in keys]
    for column in numeric_columns:
        merged[column] = merged[column].fillna(0.0)

    tracked_metrics = [
        "avg_bandwidth_usage_mbps",
        "avg_slice_capacity_mbps",
        "avg_slice_load_ratio",
        "avg_remaining_capacity_ratio",
        "avg_request_count_per_window",
        "total_request_count",
        "avg_requested_usage_mbps_per_window",
        "avg_clients_seen_per_window",
        "avg_state_sla_violation_share",
        "avg_sla_safety_margin",
        "avg_sla_breach_count_per_window",
    ]
    rows = []
    for _, row in merged.iterrows():
        item = {key: row[key] for key in keys}
        for metric in tracked_metrics:
            baseline_value = float(row.get(f"{metric}_baseline", 0.0))
            ml_value = float(row.get(f"{metric}_ml", 0.0))
            item[f"{metric}_baseline"] = baseline_value
            item[f"{metric}_ml"] = ml_value
            item[f"{metric}_delta"] = ml_value - baseline_value
            item[f"{metric}_delta_pct"] = (
                item[f"{metric}_delta"] / baseline_value * 100.0 if abs(baseline_value) > 1e-12 else 0.0
            )
        rows.append(item)
    return pd.DataFrame(rows).sort_values(keys).reset_index(drop=True)


def _markdown_table(frame: pd.DataFrame, float_digits: int = 4) -> str:
    if frame.empty:
        return "| _Empty_ |\n|---|\n| _No data_ |"

    display = frame.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: f"{value:.{float_digits}f}")
    header = "| " + " | ".join(display.columns) + " |"
    separator = "|" + "|".join(["---"] * len(display.columns)) + "|"
    rows = ["| " + " | ".join(str(value) for value in row) + " |" for row in display.itertuples(index=False, name=None)]
    return "\n".join([header, separator] + rows)


def _build_tradeoff_notes(per_slice_comparison: pd.DataFrame) -> list[str]:
    if per_slice_comparison.empty:
        return ["No trade-off summary was generated because the comparison tables are empty."]

    index = per_slice_comparison.set_index("slice_name")
    notes: list[str] = []

    if "URLLC" in index.index:
        row = index.loc["URLLC"]
        notes.append(
            "URLLC completion latency changed by "
            f"{row['avg_completion_latency_ms_delta']:.2f} ms and SLA safety margin changed by "
            f"{row['avg_sla_safety_margin_delta']:.4f} "
            f"({row['avg_sla_safety_margin_improvement_pct']:+.1f}%)."
        )
    if "eMBB" in index.index:
        row = index.loc["eMBB"]
        notes.append(
            "eMBB average bandwidth usage changed by "
            f"{row['avg_bandwidth_usage_mbps_delta']:.3f} Mbps and completion ratio changed by "
            f"{row['completion_ratio_delta']:.4f}."
        )
    if "mMTC" in index.index:
        row = index.loc["mMTC"]
        notes.append(
            "mMTC first-service latency changed by "
            f"{row['avg_first_service_latency_ms_delta']:.2f} ms and completion ratio changed by "
            f"{row['completion_ratio_delta']:.4f}."
        )

    if "URLLC" in index.index:
        row = index.loc["URLLC"]
        notes.append(
            "URLLC recorded first-service latency changed by "
            f"{row['avg_recorded_first_service_latency_ms_delta']:.2f} ms on windows with actual first-service events."
        )

    if "URLLC" in index.index and "eMBB" in index.index:
        urllc = index.loc["URLLC"]
        embb = index.loc["eMBB"]
        notes.append(
            "Classic trade-off snapshot: if URLLC improved by "
            f"{-urllc['avg_completion_latency_ms_delta']:.2f} ms in latency, "
            f"eMBB bandwidth moved by {embb['avg_bandwidth_usage_mbps_delta']:.3f} Mbps."
        )
    if "eMBB" in index.index:
        embb = index.loc["eMBB"]
        if embb.get("zero_bandwidth_window_share_ml", 0.0) > 0.50:
            notes.append(
                "eMBB shows a high zero-bandwidth window share under the ML policy, which is a starvation signal."
            )
    return notes


def _slice_ratio_summary_from_state(state_frame: pd.DataFrame, value_name: str) -> pd.DataFrame:
    if state_frame.empty or "slice_init_capacity" not in state_frame.columns:
        return pd.DataFrame(columns=["slice_name", value_name])
    frame = state_frame.copy()
    frame[value_name] = frame.apply(
        lambda row: row["slice_init_capacity"] / row["base_station_capacity"]
        if row.get("base_station_capacity", 0) > 0
        else 0.0,
        axis=1,
    )
    return frame.groupby("slice_name", as_index=False)[value_name].mean()


def _action_ratio_time_series(actions: pd.DataFrame) -> pd.DataFrame:
    columns = ["time", "slice_name", "avg_target_ratio", "avg_scheduling_weight", "avg_admission_guard_factor"]
    if actions.empty or "target_ratio" not in actions.columns:
        return pd.DataFrame(columns=columns)
    frame = actions.copy()
    frame["time"] = frame["effective_time"]
    return frame.groupby(["time", "slice_name"], as_index=False).agg(
        avg_target_ratio=("target_ratio", "mean"),
        avg_scheduling_weight=("scheduling_weight", "mean"),
        avg_admission_guard_factor=("admission_guard_factor", "mean"),
    )


def _resource_allocation_summary(
    baseline_state: pd.DataFrame,
    ml_state: pd.DataFrame,
    ml_actions: pd.DataFrame,
) -> pd.DataFrame:
    baseline_ratio = _slice_ratio_summary_from_state(baseline_state, "baseline_state_ratio")
    ml_state_ratio = _slice_ratio_summary_from_state(ml_state, "ml_state_ratio")

    if ml_actions.empty:
        action_summary = pd.DataFrame(
            columns=[
                "slice_name",
                "ml_action_target_ratio_mean",
                "ml_action_target_ratio_min",
                "ml_action_target_ratio_max",
                "ml_scheduling_weight_mean",
                "ml_admission_guard_factor_mean",
            ]
        )
    else:
        action_summary = ml_actions.groupby("slice_name", as_index=False).agg(
            ml_action_target_ratio_mean=("target_ratio", "mean"),
            ml_action_target_ratio_min=("target_ratio", "min"),
            ml_action_target_ratio_max=("target_ratio", "max"),
            ml_scheduling_weight_mean=("scheduling_weight", "mean"),
            ml_admission_guard_factor_mean=("admission_guard_factor", "mean"),
        )

    summary = baseline_ratio.merge(ml_state_ratio, on="slice_name", how="outer")
    summary = summary.merge(action_summary, on="slice_name", how="outer")
    for column in summary.columns:
        if column != "slice_name":
            summary[column] = summary[column].fillna(0.0)
    if "baseline_state_ratio" in summary.columns and "ml_action_target_ratio_mean" in summary.columns:
        summary["target_ratio_delta_vs_baseline_state"] = (
            summary["ml_action_target_ratio_mean"] - summary["baseline_state_ratio"]
        )
    summary["slice_name"] = pd.Categorical(summary["slice_name"], categories=SLICE_ORDER, ordered=True)
    return summary.sort_values("slice_name").reset_index(drop=True)


def _plot_action_distribution(actions: pd.DataFrame, output_path: Path) -> None:
    series = _action_ratio_time_series(actions)
    if series.empty:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "No ML action data", ha="center", va="center")
        ax.axis("off")
        fig.tight_layout()
        fig.savefig(output_path, dpi=220)
        plt.close(fig)
        return

    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
    for slice_name in SLICE_ORDER:
        color = SLICE_COLORS.get(slice_name)
        slice_series = series[series["slice_name"] == slice_name]
        axes[0].plot(
            slice_series["time"],
            slice_series["avg_target_ratio"],
            label=slice_name,
            color=color,
            linewidth=1.8,
        )
        axes[1].plot(
            slice_series["time"],
            slice_series["avg_scheduling_weight"],
            label=slice_name,
            color=color,
            linewidth=1.8,
        )

    axes[0].set_title("ML Target Resource Ratio By Slice")
    axes[0].set_ylabel("target ratio")
    axes[1].set_title("ML Scheduling Weight By Slice")
    axes[1].set_ylabel("weight")
    axes[1].set_xlabel("Effective time")
    for axis in axes:
        axis.grid(alpha=0.25)
        axis.legend(ncol=3, fontsize=8)
    fig.tight_layout()
    fig.savefig(output_path, dpi=220)
    plt.close(fig)


def _plot_policy_comparison(
    baseline_bandwidth: pd.DataFrame,
    ml_bandwidth: pd.DataFrame,
    baseline_completion_latency: pd.DataFrame,
    ml_completion_latency: pd.DataFrame,
    baseline_sla_violation: pd.DataFrame,
    ml_sla_violation: pd.DataFrame,
    output_path: Path,
) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(14, 14), sharex=True)

    for slice_name in SLICE_ORDER:
        color = SLICE_COLORS.get(slice_name, None)

        base_bandwidth_slice = baseline_bandwidth[baseline_bandwidth["slice_name"] == slice_name]
        ml_bandwidth_slice = ml_bandwidth[ml_bandwidth["slice_name"] == slice_name]
        axes[0].plot(
            base_bandwidth_slice["time"],
            base_bandwidth_slice["bandwidth_usage_mbps"],
            linestyle="--",
            linewidth=1.8,
            color=color,
            label=f"{slice_name} baseline",
        )
        axes[0].plot(
            ml_bandwidth_slice["time"],
            ml_bandwidth_slice["bandwidth_usage_mbps"],
            linestyle="-",
            linewidth=1.8,
            color=color,
            label=f"{slice_name} ML",
        )

        base_latency_slice = baseline_completion_latency[baseline_completion_latency["slice_name"] == slice_name]
        ml_latency_slice = ml_completion_latency[ml_completion_latency["slice_name"] == slice_name]
        axes[1].plot(
            base_latency_slice["time"],
            base_latency_slice["avg_completion_latency_ms"],
            linestyle="--",
            linewidth=1.8,
            color=color,
            label=f"{slice_name} baseline",
        )
        axes[1].plot(
            ml_latency_slice["time"],
            ml_latency_slice["avg_completion_latency_ms"],
            linestyle="-",
            linewidth=1.8,
            color=color,
            label=f"{slice_name} ML",
        )

        base_sla_slice = baseline_sla_violation[baseline_sla_violation["slice_name"] == slice_name]
        ml_sla_slice = ml_sla_violation[ml_sla_violation["slice_name"] == slice_name]
        axes[2].plot(
            base_sla_slice["time"],
            base_sla_slice["sla_violation_share"],
            linestyle="--",
            linewidth=1.8,
            color=color,
            label=f"{slice_name} baseline",
        )
        axes[2].plot(
            ml_sla_slice["time"],
            ml_sla_slice["sla_violation_share"],
            linestyle="-",
            linewidth=1.8,
            color=color,
            label=f"{slice_name} ML",
        )

    axes[0].set_title("Per-Slice Bandwidth Usage")
    axes[0].set_ylabel("Mbps")
    axes[1].set_title("Per-Slice Completion Latency")
    axes[1].set_ylabel("ms")
    axes[2].set_title("Per-Slice State SLA Proxy Share")
    axes[2].set_ylabel("proxy share")
    axes[2].set_xlabel("Time window")

    for axis in axes:
        axis.grid(alpha=0.25)
        axis.legend(ncol=2, fontsize=8, loc="upper right")

    fig.tight_layout()
    fig.savefig(output_path, dpi=220)
    plt.close(fig)


def _plot_global_kpi_bars(global_comparison: pd.DataFrame, output_path: Path) -> None:
    if global_comparison.empty:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "No global KPI data", ha="center", va="center")
        ax.axis("off")
        fig.tight_layout()
        fig.savefig(output_path, dpi=220)
        plt.close(fig)
        return

    plot_frame = global_comparison.copy()
    plot_frame["metric_label"] = plot_frame["metric"].replace(
        {
            "connected_clients_ratio": "Connected",
            "coverage_ratio": "Coverage",
            "block_ratio": "Block",
            "handover_ratio": "Handover",
            "avg_slice_load_ratio": "Avg Load",
            "total_bandwidth_usage": "Total BW",
            "avg_latency_ms": "Avg Latency",
            "p95_latency_ms": "P95 Latency",
            "latency_violation_ratio": "Latency Viol.",
            "avg_state_sla_violation_share": "State SLA Viol.",
            "bandwidth_jain_fairness": "Jain Fairness",
            "bandwidth_jain_fairness_min": "Min Jain Fair.",
        }
    )

    fig, axes = plt.subplots(2, 1, figsize=(14, 9), gridspec_kw={"height_ratios": [3, 2]})
    x = range(len(plot_frame))
    width = 0.38

    axes[0].bar(
        [idx - width / 2 for idx in x],
        plot_frame["baseline"],
        width=width,
        label="Baseline",
        color="#7f8c8d",
    )
    axes[0].bar(
        [idx + width / 2 for idx in x],
        plot_frame["ml_policy"],
        width=width,
        label="ML Policy",
        color="#2e86de",
    )
    axes[0].set_xticks(list(x))
    axes[0].set_xticklabels(plot_frame["metric_label"], rotation=25, ha="right")
    axes[0].set_title("Global KPI Comparison")
    axes[0].grid(axis="y", alpha=0.25)
    axes[0].legend()

    colors = [
        "#27ae60"
        if (
            (row["metric"] in METRICS_HIGHER_IS_BETTER and row["delta_ml_minus_baseline"] >= 0)
            or (row["metric"] not in METRICS_HIGHER_IS_BETTER and row["delta_ml_minus_baseline"] <= 0)
        )
        else "#c0392b"
        for _, row in plot_frame.iterrows()
    ]
    axes[1].bar(plot_frame["metric_label"], plot_frame["delta_pct"], color=colors)
    axes[1].axhline(0, color="black", linewidth=1)
    axes[1].set_title("Relative Change of ML vs Baseline")
    axes[1].set_ylabel("%")
    axes[1].grid(axis="y", alpha=0.25)
    axes[1].tick_params(axis="x", rotation=25)

    fig.tight_layout()
    fig.savefig(output_path, dpi=220)
    plt.close(fig)


def _save_figure_variants(fig, output_path: Path, *, png_dpi: int = 200, export_svg: bool = True) -> None:
    fig.savefig(output_path, dpi=png_dpi)
    if export_svg and output_path.suffix.lower() == ".png":
        fig.savefig(output_path.with_suffix(".svg"))


def _read_sla_reference(sla_path: Path | None) -> pd.DataFrame:
    if sla_path is None or not Path(sla_path).exists():
        return pd.DataFrame()
    frame = pd.read_csv(sla_path)
    if "slice_name" not in frame.columns:
        return pd.DataFrame()
    return frame.set_index("slice_name")


def _ordered_slices(frame: pd.DataFrame) -> pd.DataFrame:
    ordered = frame.copy()
    ordered["slice_name"] = pd.Categorical(ordered["slice_name"], categories=SLICE_ORDER, ordered=True)
    return ordered.sort_values("slice_name").reset_index(drop=True)


def _format_metric_value(value: float, metric: str) -> str:
    if pd.isna(value):
        return "n/a"
    if metric.endswith("_ratio") or "violation" in metric:
        return f"{100.0 * value:.1f}%"
    if "latency" in metric:
        return f"{value:.3g} ms"
    if "bandwidth" in metric:
        return f"{value:.0f}"
    return f"{value:.3g}"


def _annotate_bars(ax, bars, values, metric: str, *, log_scale: bool = False) -> None:
    finite_values = [float(value) for value in values if pd.notna(value)]
    y_span = max(finite_values) if finite_values else 1.0
    for bar, raw_value in zip(bars, values):
        if pd.isna(raw_value):
            continue
        height = max(float(bar.get_height()), 1e-9)
        y = height * 1.12 if log_scale else height + max(y_span * 0.025, 0.01)
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            y,
            _format_metric_value(float(raw_value), metric),
            ha="center",
            va="bottom",
            fontsize=8,
            rotation=90 if log_scale else 0,
        )


def _plot_slice_reference_segments(
    ax,
    frame: pd.DataFrame,
    sla_ref: pd.DataFrame,
    sla_column: str,
    *,
    scale: float = 1.0,
    label: str = "SLA",
) -> None:
    if sla_ref.empty or sla_column not in sla_ref.columns:
        return
    for index, slice_name in enumerate(frame["slice_name"].astype(str)):
        if slice_name not in sla_ref.index:
            continue
        value = pd.to_numeric(pd.Series([sla_ref.loc[slice_name, sla_column]]), errors="coerce").iloc[0]
        if pd.isna(value) or value <= 0:
            continue
        value = float(value) * scale
        color = SLICE_COLORS.get(slice_name, "#555555")
        ax.hlines(value, index - 0.46, index + 0.46, color=color, linestyle=":", linewidth=1.6, alpha=0.85)
        ax.text(index + 0.48, value, label, color=color, fontsize=7, va="center")


def _set_log_ylim_with_reference(
    ax,
    frame: pd.DataFrame,
    metric: str,
    sla_ref: pd.DataFrame,
    sla_column: str | None = None,
    *,
    sla_scale: float = 1.0,
) -> None:
    values: list[float] = []
    for suffix in ["baseline", "ml"]:
        column = f"{metric}_{suffix}"
        if column in frame.columns:
            values.extend(pd.to_numeric(frame[column], errors="coerce").dropna().astype(float).tolist())
    if sla_column and not sla_ref.empty and sla_column in sla_ref.columns:
        values.extend((pd.to_numeric(sla_ref[sla_column], errors="coerce") * sla_scale).dropna().astype(float).tolist())

    positive_values = [value for value in values if value > 0]
    if not positive_values:
        return
    lower = max(min(positive_values) * 0.45, 1e-6)
    upper = max(positive_values) * 2.2
    ax.set_ylim(lower, upper)


def _grouped_policy_bars(
    ax,
    frame: pd.DataFrame,
    metric: str,
    title: str,
    ylabel: str,
    *,
    log_scale: bool = False,
    ylim: tuple[float, float] | None = None,
) -> tuple[list, list]:
    width = 0.34
    baseline_values = frame[f"{metric}_baseline"].astype(float).fillna(0.0).tolist()
    ml_values = frame[f"{metric}_ml"].astype(float).fillna(0.0).tolist()
    baseline_display = [max(value, 1e-6) if log_scale else value for value in baseline_values]
    ml_display = [max(value, 1e-6) if log_scale else value for value in ml_values]
    x = list(range(len(frame)))
    slice_colors = [SLICE_COLORS.get(str(name), "#777777") for name in frame["slice_name"]]

    baseline_bars = ax.bar(
        [idx - width / 2 for idx in x],
        baseline_display,
        width=width,
        label="Baseline",
        color=slice_colors,
        alpha=0.28,
        edgecolor="#303030",
        linewidth=1.0,
        hatch="//",
    )
    ml_bars = ax.bar(
        [idx + width / 2 for idx in x],
        ml_display,
        width=width,
        label="ML Policy",
        color=slice_colors,
        alpha=0.92,
        edgecolor="#303030",
        linewidth=0.8,
    )
    ax.set_xticks(x)
    ax.set_xticklabels(frame["slice_name"].astype(str))
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y")
    if log_scale:
        ax.set_yscale("log")
    if ylim is not None:
        ax.set_ylim(*ylim)
    _annotate_bars(ax, baseline_bars, baseline_values, metric, log_scale=log_scale)
    _annotate_bars(ax, ml_bars, ml_values, metric, log_scale=log_scale)
    return baseline_bars, ml_bars


def _relative_improvement_percent(baseline: float, ml_value: float, *, higher_is_better: bool) -> float:
    if pd.isna(baseline) or pd.isna(ml_value):
        return float("nan")
    baseline = float(baseline)
    ml_value = float(ml_value)
    if abs(baseline) < 1e-12:
        if abs(ml_value) < 1e-12:
            return 0.0
        return 100.0 if (higher_is_better and ml_value > 0) else -100.0
    raw_delta = (ml_value - baseline) / abs(baseline) * 100.0
    return raw_delta if higher_is_better else -raw_delta


def _plot_improvement_heatmap(ax, frame: pd.DataFrame) -> None:
    metrics = [
        ("avg_bandwidth_usage_mbps", "Bandwidth", True),
        ("avg_completion_latency_ms", "Completion latency", False),
        ("avg_first_service_latency_ms", "First-service latency", False),
        ("completion_ratio", "Completion ratio", True),
        ("avg_sla_safety_margin", "SLA safety margin", True),
    ]
    matrix = []
    for metric, _, higher_is_better in metrics:
        row = []
        for slice_name in SLICE_ORDER:
            slice_row = frame[frame["slice_name"].astype(str) == slice_name]
            if slice_row.empty:
                row.append(float("nan"))
                continue
            slice_row = slice_row.iloc[0]
            row.append(
                _relative_improvement_percent(
                    slice_row.get(f"{metric}_baseline", float("nan")),
                    slice_row.get(f"{metric}_ml", float("nan")),
                    higher_is_better=higher_is_better,
                )
            )
        matrix.append(row)

    heatmap = pd.DataFrame(matrix, index=[label for _, label, _ in metrics], columns=SLICE_ORDER)
    finite_values = heatmap.to_numpy()
    finite_values = finite_values[pd.notna(finite_values)]
    max_abs = max(float(abs(finite_values).max()), 1.0) if len(finite_values) else 1.0
    max_abs = min(max_abs, 100.0)
    image = ax.imshow(heatmap.clip(-100.0, 100.0), cmap="RdYlGn", vmin=-max_abs, vmax=max_abs, aspect="auto")
    ax.set_xticks(range(len(SLICE_ORDER)))
    ax.set_xticklabels(SLICE_ORDER)
    ax.set_yticks(range(len(heatmap.index)))
    ax.set_yticklabels(heatmap.index)
    ax.set_title("E. Direction-Aware Improvement Heatmap (green = better)")
    for row_index, metric_label in enumerate(heatmap.index):
        for col_index, slice_name in enumerate(SLICE_ORDER):
            value = heatmap.loc[metric_label, slice_name]
            if pd.isna(value):
                text = "n/a"
            else:
                text = f"{value:+.1f}%"
            ax.text(col_index, row_index, text, ha="center", va="center", fontsize=9, color="#111111")
    cbar = ax.figure.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label("Improvement (%)")


def _plot_sla_margin_improvement_bars(ax, frame: pd.DataFrame) -> None:
    values = frame["avg_sla_safety_margin_improvement_pct"].astype(float).fillna(0.0).tolist()
    colors = ["#1f8f4d" if value >= 0 else "#c0392b" for value in values]
    x = list(range(len(frame)))
    bars = ax.bar(x, values, color=colors, edgecolor="#303030", linewidth=0.8, alpha=0.90)
    ax.axhline(0, color="#111111", linewidth=1.0)
    ax.set_xticks(x)
    ax.set_xticklabels(frame["slice_name"].astype(str))
    ax.set_title("SLA Safety Margin Improvement (higher is better)")
    ax.set_ylabel("Improvement (%)")
    ax.grid(axis="y")

    finite_values = [abs(float(value)) for value in values if pd.notna(value)]
    y_span = max(finite_values) if finite_values else 1.0
    padding = max(y_span * 0.25, 5.0)
    lower = min(min(values, default=0.0) - padding, -padding)
    upper = max(max(values, default=0.0) + padding, padding)
    ax.set_ylim(lower, upper)

    for bar, value, row in zip(bars, values, frame.itertuples(index=False)):
        y = value + (padding * 0.18 if value >= 0 else -padding * 0.18)
        va = "bottom" if value >= 0 else "top"
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            y,
            f"{value:+.1f}%",
            ha="center",
            va=va,
            fontsize=8,
        )
        baseline_margin = float(getattr(row, "avg_sla_safety_margin_baseline", 0.0))
        ml_margin = float(getattr(row, "avg_sla_safety_margin_ml", 0.0))
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            lower + padding * 0.16,
            f"B={baseline_margin:.3f}\nML={ml_margin:.3f}",
            ha="center",
            va="bottom",
            fontsize=7,
            color="#303030",
        )


def _policy_legend_handles() -> list[Patch]:
    return [
        Patch(facecolor="#bdbdbd", edgecolor="#303030", hatch="//", label="Baseline"),
        Patch(facecolor="#303030", edgecolor="#303030", label="ML Policy"),
    ]


def _slice_legend_handles() -> list[Patch]:
    return [
        Patch(facecolor=SLICE_COLORS[slice_name], edgecolor="#303030", label=slice_name)
        for slice_name in SLICE_ORDER
    ]


def _first_service_legend_handles() -> list[plt.Line2D]:
    return [
        plt.Line2D([0], [0], marker="D", color="none", markeredgecolor="#111111", markerfacecolor="none", label="Baseline first-service"),
        plt.Line2D([0], [0], marker="o", color="none", markeredgecolor="#111111", markerfacecolor="#111111", label="ML first-service"),
    ]


def _plot_latency_first_service_markers(ax, plot_frame: pd.DataFrame) -> None:
    width = 0.34
    x = list(range(len(plot_frame)))
    for policy, marker, offset, face in [
        ("baseline", "D", -width / 2, "none"),
        ("ml", "o", width / 2, "#111111"),
    ]:
        col = f"avg_first_service_latency_ms_{policy}"
        if col not in plot_frame.columns:
            continue
        ax.scatter(
            [idx + offset for idx in x],
            plot_frame[col].astype(float).clip(lower=1e-6),
            marker=marker,
            s=36,
            facecolors=face,
            edgecolors="#111111",
            linewidths=1.0,
            zorder=5,
            label=f"{'Baseline' if policy == 'baseline' else 'ML'} first-service",
        )


def _panel_output_paths(output_path: Path) -> dict[str, Path]:
    return {
        "throughput": output_path.with_name(f"{output_path.stem}_throughput.png"),
        "latency": output_path.with_name(f"{output_path.stem}_latency.png"),
        "completion_ratio": output_path.with_name(f"{output_path.stem}_completion_ratio.png"),
        "sla_margin_improvement": output_path.with_name(f"{output_path.stem}_sla_margin_improvement.png"),
        "improvement_heatmap": output_path.with_name(f"{output_path.stem}_improvement_heatmap.png"),
    }


def _place_panel_legend(fig, ax, handles: list, *, ncol: int) -> None:
    ax.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.16),
        frameon=False,
        ncol=ncol,
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.12, 1, 1))


def _plot_per_slice_panel_images(plot_frame: pd.DataFrame, output_path: Path, sla_ref: pd.DataFrame) -> dict[str, str]:
    panel_paths = _panel_output_paths(output_path)

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    _grouped_policy_bars(
        ax,
        plot_frame,
        "avg_bandwidth_usage_mbps",
        "Throughput per Slice (Mbps, log-scale, higher is better)",
        "Mbps",
        log_scale=True,
    )
    _plot_slice_reference_segments(
        ax,
        plot_frame,
        sla_ref,
        "observed_init_capacity_median_bps",
        scale=1e-6,
        label="capacity ref",
    )
    _set_log_ylim_with_reference(
        ax,
        plot_frame,
        "avg_bandwidth_usage_mbps",
        sla_ref,
        "observed_init_capacity_median_bps",
        sla_scale=1e-6,
    )
    _place_panel_legend(fig, ax, _policy_legend_handles(), ncol=2)
    _save_figure_variants(fig, panel_paths["throughput"], export_svg=False)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    _grouped_policy_bars(
        ax,
        plot_frame,
        "avg_completion_latency_ms",
        "Completion Latency (ms, log-scale, lower is better)",
        "ms",
        log_scale=True,
    )
    _plot_slice_reference_segments(ax, plot_frame, sla_ref, "max_avg_latency_ms", label="SLA avg")
    _plot_latency_first_service_markers(ax, plot_frame)
    _set_log_ylim_with_reference(ax, plot_frame, "avg_completion_latency_ms", sla_ref, "max_avg_latency_ms")
    _place_panel_legend(fig, ax, _policy_legend_handles() + _first_service_legend_handles(), ncol=2)
    _save_figure_variants(fig, panel_paths["latency"], export_svg=False)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    _grouped_policy_bars(
        ax,
        plot_frame,
        "completion_ratio",
        "Completion Ratio (higher is better)",
        "ratio",
        ylim=(0, 1.08),
    )
    _plot_slice_reference_segments(ax, plot_frame, sla_ref, "min_connected_ratio", label="min ref")
    _place_panel_legend(fig, ax, _policy_legend_handles(), ncol=2)
    _save_figure_variants(fig, panel_paths["completion_ratio"], export_svg=False)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    _plot_sla_margin_improvement_bars(ax, plot_frame)
    fig.tight_layout()
    _save_figure_variants(fig, panel_paths["sla_margin_improvement"], export_svg=False)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    _plot_improvement_heatmap(ax, plot_frame)
    fig.tight_layout()
    _save_figure_variants(fig, panel_paths["improvement_heatmap"], export_svg=False)
    plt.close(fig)

    return {name: str(path) for name, path in panel_paths.items()}


def _plot_per_slice_bars(per_slice_comparison: pd.DataFrame, output_path: Path, sla_path: Path | None = None) -> dict[str, str]:
    if per_slice_comparison.empty:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "No per-slice data", ha="center", va="center")
        ax.axis("off")
        fig.tight_layout()
        _save_figure_variants(fig, output_path)
        plt.close(fig)
        return {}

    plot_frame = _ordered_slices(per_slice_comparison)
    sla_ref = _read_sla_reference(sla_path)

    fig = plt.figure(figsize=(15, 13))
    grid = fig.add_gridspec(3, 2, height_ratios=[1.0, 1.0, 1.15], hspace=0.38, wspace=0.22)
    ax_throughput = fig.add_subplot(grid[0, 0])
    ax_latency = fig.add_subplot(grid[0, 1])
    ax_completion = fig.add_subplot(grid[1, 0])
    ax_violation = fig.add_subplot(grid[1, 1])
    ax_heatmap = fig.add_subplot(grid[2, :])

    _grouped_policy_bars(
        ax_throughput,
        plot_frame,
        "avg_bandwidth_usage_mbps",
        "A. Throughput per Slice (Mbps, log-scale, higher is better)",
        "Mbps",
        log_scale=True,
    )
    _plot_slice_reference_segments(
        ax_throughput,
        plot_frame,
        sla_ref,
        "observed_init_capacity_median_bps",
        scale=1e-6,
        label="capacity ref",
    )
    _set_log_ylim_with_reference(
        ax_throughput,
        plot_frame,
        "avg_bandwidth_usage_mbps",
        sla_ref,
        "observed_init_capacity_median_bps",
        sla_scale=1e-6,
    )

    _grouped_policy_bars(
        ax_latency,
        plot_frame,
        "avg_completion_latency_ms",
        "B. Completion Latency (ms, log-scale, lower is better)",
        "ms",
        log_scale=True,
    )
    _plot_slice_reference_segments(
        ax_latency,
        plot_frame,
        sla_ref,
        "max_avg_latency_ms",
        label="SLA avg",
    )
    _plot_latency_first_service_markers(ax_latency, plot_frame)
    _set_log_ylim_with_reference(ax_latency, plot_frame, "avg_completion_latency_ms", sla_ref, "max_avg_latency_ms")

    _grouped_policy_bars(
        ax_completion,
        plot_frame,
        "completion_ratio",
        "C. Completion Ratio (higher is better)",
        "ratio",
        ylim=(0, 1.08),
    )
    _plot_slice_reference_segments(
        ax_completion,
        plot_frame,
        sla_ref,
        "min_connected_ratio",
        label="min ref",
    )

    _plot_sla_margin_improvement_bars(ax_violation, plot_frame)

    _plot_improvement_heatmap(ax_heatmap, plot_frame)

    fig.legend(
        handles=_policy_legend_handles() + _slice_legend_handles() + _first_service_legend_handles(),
        loc="upper center",
        ncol=8,
        frameon=False,
        bbox_to_anchor=(0.5, 0.965),
    )
    fig.suptitle("Per-Slice Baseline vs ML Comparison", fontsize=15, fontweight="bold", y=0.995)
    fig.subplots_adjust(left=0.07, right=0.95, bottom=0.07, top=0.84, hspace=0.48, wspace=0.25)
    _save_figure_variants(fig, output_path)
    plt.close(fig)
    return _plot_per_slice_panel_images(plot_frame, output_path, sla_ref)


def _write_report(
    output_dir: Path,
    report_payload: dict,
    global_comparison: pd.DataFrame,
    per_slice_comparison: pd.DataFrame,
    per_base_station_comparison: pd.DataFrame,
    per_base_station_slice_comparison: pd.DataFrame,
    resource_allocation_summary: pd.DataFrame,
) -> tuple[Path, Path]:
    report_json_path = output_dir / "baseline_vs_ml_report.json"
    report_md_path = output_dir / "baseline_vs_ml_report.md"

    report_json_path.write_text(json.dumps(report_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def _rel_artifact(path_value: str) -> str:
        if not path_value:
            return ""
        path = Path(path_value)
        try:
            return path.resolve().relative_to(output_dir.resolve()).as_posix()
        except ValueError:
            return path.name

    tradeoff_lines = "\n".join(f"- {line}" for line in report_payload["tradeoff_notes"])
    plot_global = Path(report_payload["artifacts"]["plot_global_kpi"]).name
    plot_slice = Path(report_payload["artifacts"]["plot_per_slice_bars"]).name
    plot_timeseries = Path(report_payload["artifacts"]["plot_timeseries"]).name
    plot_action_distribution = Path(report_payload["artifacts"]["plot_action_distribution"]).name
    ml_policy_graph = _rel_artifact(report_payload["artifacts"]["ml"].get("policy_graph_path", ""))
    ml_policy_graph_section = (
        f"### ML Policy Simulation Snapshot\n\n![ML policy simulation]({ml_policy_graph})\n"
        if ml_policy_graph
        else ""
    )
    ml_policy_graph_artifact = (
        f"- ML policy simulation graph: `{report_payload['artifacts']['ml'].get('policy_graph_path', '')}`"
        if ml_policy_graph
        else ""
    )
    panel_labels = {
        "throughput": "Throughput per Slice",
        "latency": "Latency per Slice",
        "completion_ratio": "Completion Ratio",
        "sla_margin_improvement": "SLA Safety Margin Improvement",
        "improvement_heatmap": "Improvement Heatmap",
    }
    panel_paths = report_payload["artifacts"].get("plot_per_slice_panel_images", {})
    panel_sections = "\n".join(
        f"#### {panel_labels.get(name, name)}\n\n![{panel_labels.get(name, name)}]({Path(path).name})"
        for name, path in panel_paths.items()
    )
    panel_artifacts = "\n".join(
        f"- Per-slice panel plot ({panel_labels.get(name, name)}): `{path}`"
        for name, path in panel_paths.items()
    )
    report_md = f"""# Baseline vs ML Policy Report

## Run Summary

- Timestamp: `{report_payload['run']['timestamp']}`
- Config: `{report_payload['run']['config_path']}`
- Model: `{report_payload['run']['model_dir']}`
- Controller type: `{report_payload['run'].get('controller_type', 'gbdt')}`
- Controller preset: `{report_payload['run']['controller_preset']}`
- Broker enabled: `{report_payload['run']['use_broker']}`
- Broker preset: `{report_payload['run']['broker_preset']}`
- Seed: `{report_payload['run']['seed']}`

## Global KPI Comparison

{_markdown_table(global_comparison, float_digits=4)}

## Per-Slice Summary

{_markdown_table(per_slice_comparison, float_digits=4)}

## Per-Base-Station Summary

{_markdown_table(per_base_station_comparison, float_digits=4)}

## Per-Base-Station Slice SLA Summary

{_markdown_table(per_base_station_slice_comparison, float_digits=4)}

## Resource Allocation Summary

{_markdown_table(resource_allocation_summary, float_digits=4)}

## Visual Comparison

### Global KPI View

![Global KPI comparison]({plot_global})

### Per-Slice View

![Per-slice comparison]({plot_slice})

### Per-Slice Panel Images

{panel_sections}

### Per-Slice Time-Series View

![Per-slice time-series comparison]({plot_timeseries})

### ML Action Distribution

![ML action distribution]({plot_action_distribution})

{ml_policy_graph_section}

## Metric Notes

- `avg_state_sla_violation_share` is the per-slice state-level SLA violation ratio averaged from simulator state frames.
- `avg_sla_safety_margin` is the average distance to the active SLA boundary. Higher is better; negative means violation.
- `avg_sla_safety_margin_improvement_pct` is `(ML margin - baseline margin) / abs(baseline margin) * 100`.
- `request_latency_violation_event_ratio`, `completion_latency_violation_ratio`, and `first_service_latency_violation_ratio` are client-level latency-only metrics.
- A latency value of `0` can mean no recorded latency event for that slice/window. Check `completion_ratio` and request/completion counts before interpreting it as perfect latency.
- `bandwidth_jain_fairness` is Jain's fairness index over per-slice bandwidth usage per time window. Higher is more balanced, with `1.0` meaning equal usage across slices.

## Trade-off Notes

{tradeoff_lines}

## Artifacts

- Baseline raw states: `{report_payload['artifacts']['baseline']['raw_state_path']}`
- ML raw states: `{report_payload['artifacts']['ml']['raw_state_path']}`
- ML broker forecasts: `{report_payload['artifacts']['ml'].get('broker_forecast_path', '')}`
- ML broker feedback: `{report_payload['artifacts']['ml'].get('broker_feedback_path', '')}`
- Comparison CSV (global): `{report_payload['artifacts']['global_comparison_csv']}`
- Comparison CSV (per-slice): `{report_payload['artifacts']['per_slice_comparison_csv']}`
- Comparison CSV (per-base-station): `{report_payload['artifacts']['per_base_station_comparison_csv']}`
- Comparison CSV (per-base-station-slice): `{report_payload['artifacts']['per_base_station_slice_comparison_csv']}`
- Resource allocation CSV: `{report_payload['artifacts']['resource_allocation_summary_csv']}`
- ML action time-series CSV: `{report_payload['artifacts']['ml_action_ratio_timeseries_csv']}`
- Global KPI plot: `{report_payload['artifacts']['plot_global_kpi']}`
- Per-slice bar plot: `{report_payload['artifacts']['plot_per_slice_bars']}`
- Per-slice vector plot (SVG): `{report_payload['artifacts'].get('plot_per_slice_bars_svg', '')}`
{panel_artifacts}
- Per-slice time-series plot: `{report_payload['artifacts']['plot_timeseries']}`
- ML action distribution plot: `{report_payload['artifacts']['plot_action_distribution']}`
{ml_policy_graph_artifact}
"""
    report_md_path.write_text(report_md, encoding="utf-8")
    return report_json_path, report_md_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run baseline and ML closed-loop on the same scenario, then export a compact comparison report."
    )
    parser.add_argument("--scenario", help="Scenario name such as light, medium, or heavy.")
    parser.add_argument("--config", help="Full path to the simulator config. Overrides --scenario.")
    parser.add_argument(
        "--sla-path",
        default=str(_repo_root() / "sla_reference_table.csv"),
        help="Path to the SLA reference CSV.",
    )
    parser.add_argument(
        "--model-dir",
        required=True,
        help="Path to the trained GBDT model directory.",
    )
    parser.add_argument(
        "--controller-type",
        default="gbdt",
        choices=["gbdt", "admm"],
        help="Controller implementation used by the ML closed-loop run.",
    )
    parser.add_argument(
        "--controller-preset",
        default="balanced",
        help="Controller preset used by the ML closed-loop run.",
    )
    parser.add_argument(
        "--use-broker",
        action="store_true",
        help="Enable the forecasting-aware slice broker above the ML controller.",
    )
    parser.add_argument(
        "--broker-preset",
        default="forecasting_balanced",
        help="Broker preset used when --use-broker is enabled.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed shared by baseline and ML runs.")
    parser.add_argument(
        "--output-dir",
        help="Directory for comparison artifacts. Default: artifacts/comparisons/<auto-generated>",
    )
    parser.add_argument(
        "--pipeline-output-root",
        default="final_output",
        help=(
            "Root directory for the structured pipeline package. "
            "Default: final_output. Set to an empty string to disable."
        ),
    )
    parser.add_argument(
        "--pipeline-run-date",
        help="Optional date token for the structured pipeline folder. Accepts DD/MM/YY, DD-MM-YY, or YYYY-MM-DD.",
    )
    parser.add_argument(
        "--overwrite-pipeline-output",
        action="store_true",
        help="Overwrite the structured pipeline folder if it already exists.",
    )
    parser.add_argument(
        "--strict-guardrail",
        action="store_true",
        help=(
            "After generating comparison files, require ML to improve SLA safety margin "
            "and not regress throughput, latency, block, connected, or completion KPIs."
        ),
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    repo_root = _repo_root()
    config_path = _resolve_config_path(repo_root, args)
    if not config_path.exists():
        raise FileNotFoundError(f"Missing config file: {config_path}")

    sla_path = Path(args.sla_path)
    model_dir = Path(args.model_dir)
    if not sla_path.exists():
        raise FileNotFoundError(f"Missing SLA reference file: {sla_path}")
    if not model_dir.exists():
        raise FileNotFoundError(f"Missing model directory: {model_dir}")

    scenario_label = args.scenario or config_path.stem
    output_dir = Path(args.output_dir) if args.output_dir else (
        repo_root / "artifacts" / "comparisons" / f"{scenario_label}_baseline_vs_ml_{_timestamp()}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    baseline_dir = output_dir / "baseline_run"
    ml_dir = output_dir / "ml_run"

    print(f"Running baseline scenario from {config_path} ...")
    baseline_paths = run_online_baseline(
        config_path=config_path,
        sla_path=sla_path,
        output_dir=baseline_dir,
        seed=args.seed,
        render_graph=True,
        graph_policy_label="Baseline Policy",
    )

    print(f"Running ML closed-loop scenario from {config_path} ...")
    ml_paths = run_online_closed_loop(
        config_path=config_path,
        sla_path=sla_path,
        model_dir=model_dir,
        output_dir=ml_dir,
        seed=args.seed,
        controller_type=args.controller_type,
        controller_preset=args.controller_preset,
        use_broker=args.use_broker,
        broker_preset=args.broker_preset,
        render_graph=True,
        graph_policy_label=f"ML Policy ({args.controller_preset})",
    )

    baseline_state = _read_csv(baseline_paths["raw_state_path"])
    ml_state = _read_csv(ml_paths["raw_state_path"])
    baseline_client_summary = _read_csv(baseline_paths["client_summary_path"])
    ml_client_summary = _read_csv(ml_paths["client_summary_path"])
    baseline_completion_latency = _read_csv(baseline_paths["slice_completion_latency_path"])
    ml_completion_latency = _read_csv(ml_paths["slice_completion_latency_path"])
    baseline_first_service_latency = _read_csv(baseline_paths["slice_first_service_latency_path"])
    ml_first_service_latency = _read_csv(ml_paths["slice_first_service_latency_path"])
    ml_actions = _read_csv(ml_paths["action_path"]) if Path(ml_paths["action_path"]).exists() else pd.DataFrame()

    baseline_global = _global_metric_summary(baseline_state)
    ml_global = _global_metric_summary(ml_state)
    global_comparison = _comparison_table(baseline_global, ml_global)

    baseline_per_slice = _per_slice_summary(
        baseline_state,
        baseline_client_summary,
        baseline_completion_latency,
        baseline_first_service_latency,
    )
    ml_per_slice = _per_slice_summary(
        ml_state,
        ml_client_summary,
        ml_completion_latency,
        ml_first_service_latency,
    )
    per_slice_comparison = _per_slice_comparison_table(baseline_per_slice, ml_per_slice)
    baseline_per_base_station = _per_base_station_summary(baseline_state)
    ml_per_base_station = _per_base_station_summary(ml_state)
    per_base_station_comparison = _per_base_station_comparison_table(
        baseline_per_base_station,
        ml_per_base_station,
    )
    baseline_per_base_station_slice = _per_base_station_slice_summary(baseline_state)
    ml_per_base_station_slice = _per_base_station_slice_summary(ml_state)
    per_base_station_slice_comparison = _per_base_station_slice_comparison_table(
        baseline_per_base_station_slice,
        ml_per_base_station_slice,
    )
    resource_allocation_summary = _resource_allocation_summary(baseline_state, ml_state, ml_actions)
    ml_action_ratio_timeseries = _action_ratio_time_series(ml_actions)

    global_comparison_csv = output_dir / "global_kpi_comparison.csv"
    per_slice_comparison_csv = output_dir / "per_slice_comparison.csv"
    per_base_station_comparison_csv = output_dir / "per_base_station_comparison.csv"
    per_base_station_slice_comparison_csv = output_dir / "per_base_station_slice_comparison.csv"
    resource_allocation_summary_csv = output_dir / "resource_allocation_summary.csv"
    ml_action_ratio_timeseries_csv = output_dir / "ml_action_ratio_timeseries.csv"
    global_comparison.to_csv(global_comparison_csv, index=False)
    per_slice_comparison.to_csv(per_slice_comparison_csv, index=False)
    per_base_station_comparison.to_csv(per_base_station_comparison_csv, index=False)
    per_base_station_slice_comparison.to_csv(per_base_station_slice_comparison_csv, index=False)
    resource_allocation_summary.to_csv(resource_allocation_summary_csv, index=False)
    ml_action_ratio_timeseries.to_csv(ml_action_ratio_timeseries_csv, index=False)

    plot_global_kpi_path = output_dir / "baseline_vs_ml_global_kpis.png"
    plot_per_slice_bars_path = output_dir / "baseline_vs_ml_per_slice_bars.png"
    plot_timeseries_path = output_dir / "baseline_vs_ml_timeseries.png"
    plot_action_distribution_path = output_dir / "ml_action_distribution.png"
    _plot_global_kpi_bars(global_comparison, plot_global_kpi_path)
    per_slice_panel_paths = _plot_per_slice_bars(per_slice_comparison, plot_per_slice_bars_path, sla_path=sla_path)
    _plot_policy_comparison(
        baseline_bandwidth=_slice_bandwidth_series(baseline_state),
        ml_bandwidth=_slice_bandwidth_series(ml_state),
        baseline_completion_latency=baseline_completion_latency,
        ml_completion_latency=ml_completion_latency,
        baseline_sla_violation=_slice_sla_violation_series(baseline_state),
        ml_sla_violation=_slice_sla_violation_series(ml_state),
        output_path=plot_timeseries_path,
    )
    _plot_action_distribution(ml_actions, plot_action_distribution_path)

    tradeoff_notes = _build_tradeoff_notes(per_slice_comparison)

    report_payload = {
        "run": {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "config_path": str(config_path),
            "model_dir": str(model_dir),
            "controller_type": args.controller_type,
            "controller_preset": args.controller_preset,
            "use_broker": args.use_broker,
            "broker_preset": args.broker_preset if args.use_broker else None,
            "seed": args.seed,
        },
        "artifacts": {
            "baseline": {key: str(value) for key, value in baseline_paths.items()},
            "ml": {key: str(value) for key, value in ml_paths.items()},
            "global_comparison_csv": str(global_comparison_csv),
            "per_slice_comparison_csv": str(per_slice_comparison_csv),
            "per_base_station_comparison_csv": str(per_base_station_comparison_csv),
            "per_base_station_slice_comparison_csv": str(per_base_station_slice_comparison_csv),
            "resource_allocation_summary_csv": str(resource_allocation_summary_csv),
            "ml_action_ratio_timeseries_csv": str(ml_action_ratio_timeseries_csv),
            "plot_global_kpi": str(plot_global_kpi_path),
            "plot_per_slice_bars": str(plot_per_slice_bars_path),
            "plot_per_slice_bars_svg": str(plot_per_slice_bars_path.with_suffix(".svg")),
            "plot_per_slice_panel_images": per_slice_panel_paths,
            "plot_timeseries": str(plot_timeseries_path),
            "plot_action_distribution": str(plot_action_distribution_path),
        },
        "tradeoff_notes": tradeoff_notes,
    }

    report_json_path, report_md_path = _write_report(
        output_dir=output_dir,
        report_payload=report_payload,
        global_comparison=global_comparison,
        per_slice_comparison=per_slice_comparison,
        per_base_station_comparison=per_base_station_comparison,
        per_base_station_slice_comparison=per_base_station_slice_comparison,
        resource_allocation_summary=resource_allocation_summary,
    )

    guardrail_payload = None
    guardrail_json_path = None
    guardrail_md_path = None
    if args.strict_guardrail:
        guardrail_payload = evaluate_strict_guardrails(output_dir)
        guardrail_json_path, guardrail_md_path = _write_guardrail_report(output_dir, guardrail_payload)

    print("\nComparison completed.")
    print(f"- Global comparison CSV: {global_comparison_csv}")
    print(f"- Per-slice comparison CSV: {per_slice_comparison_csv}")
    print(f"- Per-base-station comparison CSV: {per_base_station_comparison_csv}")
    print(f"- Per-base-station-slice comparison CSV: {per_base_station_slice_comparison_csv}")
    print(f"- Resource allocation CSV: {resource_allocation_summary_csv}")
    print(f"- ML action time-series CSV: {ml_action_ratio_timeseries_csv}")
    print(f"- Global KPI plot: {plot_global_kpi_path}")
    print(f"- Per-slice bar plot: {plot_per_slice_bars_path}")
    for panel_name, panel_path in per_slice_panel_paths.items():
        print(f"- Per-slice {panel_name} panel: {panel_path}")
    print(f"- Time-series plot: {plot_timeseries_path}")
    print(f"- ML action distribution plot: {plot_action_distribution_path}")
    print(f"- Report JSON: {report_json_path}")
    print(f"- Report Markdown: {report_md_path}")
    if args.strict_guardrail:
        print(f"- Strict guardrail JSON: {guardrail_json_path}")
        print(f"- Strict guardrail Markdown: {guardrail_md_path}")
        print(f"- Strict guardrail passed: {guardrail_payload['passed']}")

    if args.pipeline_output_root:
        pipeline_output_dir = organize_pipeline_outputs(
            scenario=scenario_label,
            comparison_dir=output_dir,
            model_dir=model_dir,
            output_root=args.pipeline_output_root,
            run_date=args.pipeline_run_date,
            overwrite=args.overwrite_pipeline_output,
        )
        print(f"- Structured pipeline output: {pipeline_output_dir}")

    if args.strict_guardrail and not guardrail_payload["passed"]:
        raise SystemExit("Strict guardrail failed; do not treat this run as final.")


if __name__ == "__main__":
    main()
