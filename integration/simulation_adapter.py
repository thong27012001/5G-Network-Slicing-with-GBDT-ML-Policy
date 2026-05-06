"""Các adapter giúp simulator và ML/controller được tách lỏng với nhau."""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from ml.feature_builder import build_state_frame
from ml.feature_schema import canonicalize_base_station_id
from ml.label_rules import append_sla_labels
from slicesim.runtime import build_simulation_context, load_config_file


def build_live_state_frame_from_context(
    context,
    sla_reference: pd.DataFrame,
    time_value: int | float | None = None,
) -> pd.DataFrame:
    """Tạo state frame đầy đủ từ context của simulator cho window mới nhất."""
    counters_snapshot = context.stats.latest_window_slice_bs_counters or {}
    metric_values = context.stats.latest_window_metric_values or {}
    collection_time = context.stats.latest_collection_time if time_value is None else time_value
    rows = []

    for base_station in context.base_stations:
        for network_slice in base_station.slices:
            key = (network_slice.name, base_station.pk)
            bucket = counters_snapshot.get(
                key,
                {
                    "clients_seen": 0,
                    "connected_events": 0,
                    "disconnected_events": 0,
                    "already_disconnected_events": 0,
                    "request_count": 0,
                    "requested_usage_sum": 0.0,
                    "requested_usage_mean": 0.0,
                    "requested_usage_max": 0.0,
                    "mean_distance_to_bs": 0.0,
                    "max_distance_to_bs": 0.0,
                },
            )

            matching_clients = [
                client
                for client in context.clients
                if client.base_station is base_station
                and base_station.slices[client.subscribed_slice_index].name == network_slice.name
            ]
            current_distances = [
                math.dist((client.x, client.y), (base_station.coverage.center[0], base_station.coverage.center[1]))
                for client in matching_clients
            ]
            current_clients_seen = len({client.pk for client in matching_clients})
            used_capacity = max(network_slice.init_capacity - network_slice.capacity.level, 0.0)
            remaining_ratio = (
                network_slice.capacity.level / network_slice.init_capacity if network_slice.init_capacity > 0 else 0.0
            )

            rows.append(
                {
                    "time": int(collection_time) if collection_time is not None else 0,
                    "slice_name": network_slice.name,
                    "base_station_id": canonicalize_base_station_id(base_station.pk),
                    "clients_seen": max(bucket["clients_seen"], current_clients_seen),
                    "connected_events": bucket["connected_events"],
                    "disconnected_events": bucket["disconnected_events"],
                    "already_disconnected_events": bucket["already_disconnected_events"],
                    "request_count": bucket["request_count"],
                    "requested_usage_sum": bucket["requested_usage_sum"],
                    "requested_usage_mean": bucket["requested_usage_mean"],
                    "requested_usage_max": bucket["requested_usage_max"],
                    "slice_init_capacity": network_slice.init_capacity,
                    "slice_capacity_level": network_slice.capacity.level,
                    "slice_used_diff": used_capacity,
                    "base_station_capacity": base_station.capacity_bandwidth,
                    "base_station_radius": base_station.coverage.radius,
                    "mean_distance_to_bs": (
                        bucket["mean_distance_to_bs"]
                        if bucket["mean_distance_to_bs"] > 0
                        else (sum(current_distances) / len(current_distances) if current_distances else 0.0)
                    ),
                    "max_distance_to_bs": max(
                        bucket["max_distance_to_bs"],
                        max(current_distances) if current_distances else 0.0,
                    ),
                    "mean_slice_load_ratio": network_slice.get_load_ratio(),
                    "mean_remaining_capacity_ratio": remaining_ratio,
                    "connected_clients_ratio": metric_values.get("connected_clients_ratio", 0.0),
                    "coverage_ratio": metric_values.get("coverage_ratio", 0.0),
                    "block_ratio": metric_values.get("block_ratio", 0.0),
                    "handover_ratio": metric_values.get("handover_ratio", 0.0),
                    "avg_slice_load_ratio": metric_values.get("avg_slice_load_ratio", 0.0),
                    "total_bandwidth_usage": metric_values.get("total_bandwidth_usage", 0.0),
                    "avg_latency_ms": metric_values.get("avg_latency_ms", 0.0),
                    "p95_latency_ms": metric_values.get("p95_latency_ms", 0.0),
                    "latency_violation_ratio": metric_values.get("latency_violation_ratio", 0.0),
                }
            )

    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame

    frame = frame.merge(sla_reference, on="slice_name", how="left")
    frame = append_sla_labels(frame)
    max_priority_rank = frame["priority_rank"].max()
    frame["sample_weight"] = (max_priority_rank + 1 - frame["priority_rank"]).clip(lower=1)
    frame = frame.sort_values(["slice_name", "base_station_id", "time"]).reset_index(drop=True)
    return frame


def build_client_summary_from_context(context) -> pd.DataFrame:
    """Xuất bảng tổng hợp mức client ở cuối lần chạy trực tiếp từ context của simulator."""
    rows = []
    default_slice_names = [network_slice.name for network_slice in context.base_stations[0].slices] if context.base_stations else []

    for client in context.clients:
        if default_slice_names and 0 <= client.subscribed_slice_index < len(default_slice_names):
            slice_name = default_slice_names[client.subscribed_slice_index]
        else:
            slice_name = "unknown"

        avg_completion_latency_ms = (
            client.total_latency_ms / client.total_completed_requests
            if client.total_completed_requests > 0
            else 0.0
        )
        avg_first_service_latency_ms = (
            client.total_first_service_latency_ms / client.total_request_count
            if client.total_request_count > 0
            else 0.0
        )
        avg_served_bandwidth = (
            client.total_usage / client.total_consume_time
            if client.total_consume_time > 0
            else 0.0
        )
        completion_ratio = (
            client.total_completed_requests / client.total_request_count
            if client.total_request_count > 0
            else 0.0
        )
        completion_latency_violation_ratio = (
            client.latency_violation_count / client.total_completed_requests
            if client.total_completed_requests > 0
            else 0.0
        )
        first_service_violation_ratio = (
            client.first_service_latency_violation_count / client.total_request_count
            if client.total_request_count > 0
            else 0.0
        )

        rows.append(
            {
                "client_id": client.pk,
                "slice_name": slice_name,
                "total_connected_time": client.total_connected_time,
                "total_unconnected_time": client.total_unconnected_time,
                "total_request_count": client.total_request_count,
                "total_consume_time": client.total_consume_time,
                "total_usage": client.total_usage,
                "avg_served_bandwidth": avg_served_bandwidth,
                "total_completed_requests": client.total_completed_requests,
                "completion_ratio": completion_ratio,
                "total_latency_ms": client.total_latency_ms,
                "avg_completion_latency_ms": avg_completion_latency_ms,
                "max_completion_latency_ms": client.max_latency_ms,
                "completion_latency_violation_count": client.latency_violation_count,
                "completion_latency_violation_ratio": completion_latency_violation_ratio,
                "total_first_service_latency_ms": client.total_first_service_latency_ms,
                "avg_first_service_latency_ms": avg_first_service_latency_ms,
                "max_first_service_latency_ms": client.max_first_service_latency_ms,
                "first_service_latency_violation_count": client.first_service_latency_violation_count,
                "first_service_latency_violation_ratio": first_service_violation_ratio,
            }
        )

    return pd.DataFrame(rows)


def build_slice_latency_series_from_context(context, *, first_service: bool = False) -> pd.DataFrame:
    """Xuất chuỗi thời gian latency theo từng slice từ bộ thống kê đang chạy."""
    if first_service:
        stats = context.stats.get_slice_first_service_latency_stats()
        value_column = "avg_first_service_latency_ms"
    else:
        stats = context.stats.get_slice_latency_stats()
        value_column = "avg_completion_latency_ms"

    rows = []
    for slice_name, values in stats.items():
        for time_index, value in enumerate(values):
            rows.append(
                {
                    "time": time_index,
                    "slice_name": slice_name,
                    value_column: float(value),
                }
            )
    return pd.DataFrame(rows)


class ReplaySimulationAdapter:
    """Biến output workbook thành các state frame theo time window để dễ troubleshoot tách biệt."""

    def __init__(
        self,
        excel_path: str | Path,
        sla_path: str | Path,
        include_temporal_features: bool = True,
    ) -> None:
        self.excel_path = Path(excel_path)
        self.sla_path = Path(sla_path)
        self.include_temporal_features = include_temporal_features
        self._state_df: pd.DataFrame | None = None

    def load_state_frame(self) -> pd.DataFrame:
        if self._state_df is None:
            self._state_df = build_state_frame(
                self.excel_path,
                self.sla_path,
                include_temporal_features=self.include_temporal_features,
            )
        return self._state_df.copy()

    def iter_windows(self):
        state_df = self.load_state_frame()
        for time_value, group in state_df.groupby("time", sort=True):
            yield time_value, group.copy()

    @staticmethod
    def export_frame(frame: pd.DataFrame, output_path: str | Path) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(output_path, index=False)
        return output_path


class OnlineSimulationAdapter:
    """Chạy simulator theo từng time window và xuất ra live state frame."""

    def __init__(
        self,
        config_path: str | Path,
        sla_path: str | Path,
        seed: int | None = None,
    ) -> None:
        self.config_path = Path(config_path)
        self.sla_path = Path(sla_path)
        self.data = load_config_file(self.config_path)
        self.context = build_simulation_context(self.data, seed=seed)
        self.sla_reference = pd.read_csv(self.sla_path)
        self.context.env.process(self.context.stats.collect())
        self.next_collection_time = 0.25
        self.collection_epsilon = 1e-9
        self.simulation_end = int(self.context.settings["simulation_time"])

    def has_next_window(self) -> bool:
        return self.next_collection_time < self.simulation_end

    def run_one_window(self) -> pd.DataFrame:
        if not self.has_next_window():
            return pd.DataFrame()
        target_time = self.next_collection_time
        self.context.env.run(until=target_time + self.collection_epsilon)
        collection_time = self.context.stats.latest_collection_time
        state_frame = build_live_state_frame_from_context(
            self.context,
            self.sla_reference,
            collection_time if collection_time is not None else target_time,
        )
        self.next_collection_time += 1.0
        return state_frame

    def apply_actions(self, action_df: pd.DataFrame) -> None:
        if action_df.empty:
            return

        base_station_map = {
            canonicalize_base_station_id(base_station.pk): base_station for base_station in self.context.base_stations
        }
        for _, row in action_df.iterrows():
            base_station = base_station_map.get(row["base_station_id"])
            if base_station is None:
                continue
            target_slice = next(
                (network_slice for network_slice in base_station.slices if network_slice.name == row["slice_name"]),
                None,
            )
            if target_slice is None:
                continue
            target_slice.apply_runtime_action(
                target_ratio=row.get("target_ratio"),
                base_station_capacity=base_station.capacity_bandwidth,
                scheduling_weight=row.get("scheduling_weight"),
                admission_guard_factor=row.get("admission_guard_factor"),
            )

    @staticmethod
    def export_frame(frame: pd.DataFrame, output_path: str | Path) -> Path:
        return ReplaySimulationAdapter.export_frame(frame, output_path)
