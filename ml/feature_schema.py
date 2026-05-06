"""Shared feature/schema definitions for dataset building and inference."""

METRIC_SHEETS = [
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

SLA_LABEL_TO_ID = {
    "normal": 0,
    "warn": 1,
    "violation": 2,
}

WARN_SAFETY_THRESHOLD = 0.05
TEMPORAL_GROUP_COLUMNS = ["slice_name", "base_station_id"]
TEMPORAL_LAGS = (1, 2, 3)

BASE_FEATURE_COLUMNS = [
    "slice_name",
    "base_station_id",
    "clients_seen",
    "connected_events",
    "disconnected_events",
    "already_disconnected_events",
    "slice_init_capacity",
    "slice_capacity_level",
    "slice_used_diff",
    "base_station_capacity",
    "base_station_radius",
    "mean_distance_to_bs",
    "max_distance_to_bs",
    "mean_slice_load_ratio",
    "mean_remaining_capacity_ratio",
    "request_count",
    "requested_usage_sum",
    "requested_usage_mean",
    "requested_usage_max",
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

CATEGORICAL_FEATURE_COLUMNS = ["slice_name", "base_station_id"]

TEMPORAL_SOURCE_COLUMNS = [
    "clients_seen",
    "connected_events",
    "disconnected_events",
    "already_disconnected_events",
    "request_count",
    "requested_usage_sum",
    "requested_usage_mean",
    "requested_usage_max",
    "slice_capacity_level",
    "slice_used_diff",
    "mean_slice_load_ratio",
    "mean_remaining_capacity_ratio",
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

TEMPORAL_DELTA_COLUMNS = [
    "request_count",
    "requested_usage_sum",
    "slice_capacity_level",
    "slice_used_diff",
    "connected_clients_ratio",
    "block_ratio",
    "handover_ratio",
    "avg_slice_load_ratio",
    "avg_latency_ms",
    "p95_latency_ms",
    "latency_violation_ratio",
]

TEMPORAL_ROLLING_COLUMNS = {
    "request_count": ("mean", "max", "sum"),
    "requested_usage_sum": ("mean", "max", "sum"),
    "slice_capacity_level": ("mean", "min"),
    "connected_clients_ratio": ("mean", "min"),
    "coverage_ratio": ("mean", "min"),
    "block_ratio": ("mean", "max"),
    "handover_ratio": ("mean", "max"),
    "avg_slice_load_ratio": ("mean", "max"),
    "avg_latency_ms": ("mean", "max"),
    "p95_latency_ms": ("mean", "max"),
    "latency_violation_ratio": ("mean", "max"),
}

STATE_IDENTITY_COLUMNS = [
    "time",
    "slice_name",
    "base_station_id",
]

TEMPORAL_COLUMN_MARKERS = (
    "_lag",
    "_delta_",
    "_roll",
)

PREDICTION_OUTPUT_COLUMNS = [
    "time",
    "slice_name",
    "base_station_id",
    "predicted_label",
    "predicted_label_id",
    "sla_violation_prob",
]

ACTION_OUTPUT_COLUMNS = [
    "effective_time",
    "slice_name",
    "base_station_id",
    "current_ratio",
    "raw_target_ratio",
    "target_ratio",
    "scheduling_weight",
    "admission_guard_factor",
    "decision_reason",
]


def canonicalize_base_station_id(value) -> str | None:
    """Normalize base-station identifiers so offline and online pipelines share one schema."""
    if value is None:
        return None

    text = str(value).strip()
    if not text or text.lower() in {"nan", "none"}:
        return None
    if text.startswith("BS_"):
        suffix = text[3:].strip()
        return f"BS_{suffix}" if suffix else None

    try:
        numeric_value = int(float(text))
        return f"BS_{numeric_value}"
    except ValueError:
        return text


def infer_temporal_feature_columns(columns: list[str] | tuple[str, ...]) -> list[str]:
    """Return generated temporal feature columns in stable order."""
    return [
        column
        for column in columns
        if any(marker in column for marker in TEMPORAL_COLUMN_MARKERS)
    ]


def infer_model_feature_columns(columns: list[str] | tuple[str, ...]) -> list[str]:
    """Return base ML columns plus any generated temporal features."""
    feature_columns = [column for column in BASE_FEATURE_COLUMNS if column in columns]
    feature_columns.extend(
        column for column in infer_temporal_feature_columns(columns) if column not in feature_columns
    )
    return feature_columns
