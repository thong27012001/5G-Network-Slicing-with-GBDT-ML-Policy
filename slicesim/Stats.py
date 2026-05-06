import csv
import math
from pathlib import Path


class Stats:
    def __init__(self, env, base_stations, clients, area: tuple, prb_config: dict | None = None):
        """
        Khởi tạo bộ thu thập thống kê cho mô phỏng.
        """
        self.env = env
        self.base_stations = base_stations
        self.clients = clients
        self.area = area
        #self.graph = graph

        # Thống kê.
        self.total_connected_users_ratio = []
        self.total_used_bw = []
        self.avg_slice_load_ratio = []
        self.avg_slice_client_count = []
        self.coverage_ratio = []
        self.connect_attempt = [0]
        self.block_count = [0]
        self.handover_count = [0]
        self.avg_latency_ms = []
        self.p95_latency_ms = []
        self.latency_violation_ratio = []
        self._window_latency_samples = []
        self._window_latency_violations = 0
        self.slice_names = sorted(
            {
                network_slice.name
                for base_station in base_stations
                for network_slice in base_station.slices
            }
        )
        self.slice_avg_latency_ms = {slice_name: [] for slice_name in self.slice_names}
        self._window_slice_latency_samples = {slice_name: [] for slice_name in self.slice_names}
        self.slice_avg_first_service_latency_ms = {slice_name: [] for slice_name in self.slice_names}
        self._window_slice_first_service_latency_samples = {slice_name: [] for slice_name in self.slice_names}
        self._window_slice_bs_counters = {}
        self.latest_window_slice_bs_counters = {}
        self.latest_window_metric_values = {}
        self.latest_collection_time = None

        # PRB / resource allocation proxy metrics (NetSim-inspired).
        # NOTE: This is a bandwidth-based proxy, NOT true PHY PRB. See docs/prb_proxy_metrics.md.
        self._prb_config = prb_config or {}
        self._prb_per_slice_history: list[dict] = []
        self._prb_per_ue_history: list[dict] = []
        self._window_block_per_slice_bs: dict[tuple, int] = {}
        self._window_block_per_client: dict[int, int] = {}
        self._window_per_ue_latency_samples: dict[int, list[float]] = {}
        self._prb_window_index = -1
    
    def get_stats(self) -> tuple:
        """
        Trả về toàn bộ thống kê đã thu thập dưới dạng tuple.
        """
        sample_count = len(self.total_connected_users_ratio)
        return (
            self.total_connected_users_ratio,
            self.total_used_bw,
            self.avg_slice_load_ratio,
            self.avg_slice_client_count,
            self.coverage_ratio,
            self.block_count[:sample_count],
            self.handover_count[:sample_count],
            self.avg_latency_ms,
            self.p95_latency_ms,
            self.latency_violation_ratio,
        )

    def collect(self):
        """
        Thu thập thống kê ở mỗi bước mô phỏng.
        """
        if not self.connect_attempt:
            self.connect_attempt.append(0)
        if not self.block_count:
            self.block_count.append(0)
        if not self.handover_count:
            self.handover_count.append(0)

        yield self.env.timeout(0.25)
        while True:
            # Chuẩn hóa block/handover theo số lần thử kết nối trong mỗi chu kỳ thống kê.
            self.block_count[-1] /= self.connect_attempt[-1] if self.connect_attempt[-1] != 0 else 1
            self.handover_count[-1] /= self.connect_attempt[-1] if self.connect_attempt[-1] != 0 else 1

            # Chụp lại ảnh chụp trạng thái mạng ở thời điểm hiện tại.
            self.total_connected_users_ratio.append(self.get_total_connected_users_ratio())
            self.total_used_bw.append(self.get_total_used_bw())
            self.avg_slice_load_ratio.append(self.get_avg_slice_load_ratio())
            self.avg_slice_client_count.append(self.get_avg_slice_client_count())
            self.coverage_ratio.append(self.get_coverage_ratio())
            self.avg_latency_ms.append(self.get_avg_latency_ms())
            self.p95_latency_ms.append(self.get_p95_latency_ms())
            self.latency_violation_ratio.append(self.get_latency_violation_ratio())
            for slice_name in self.slice_names:
                self.slice_avg_latency_ms[slice_name].append(self.get_avg_latency_ms_for_slice(slice_name))
                self.slice_avg_first_service_latency_ms[slice_name].append(
                    self.get_avg_first_service_latency_ms_for_slice(slice_name)
                )
            self.latest_collection_time = float(self.env.now)
            self.latest_window_metric_values = {
                "connected_clients_ratio": self.total_connected_users_ratio[-1],
                "coverage_ratio": self.coverage_ratio[-1],
                "block_ratio": self.block_count[-1],
                "handover_ratio": self.handover_count[-1],
                "avg_slice_load_ratio": self.avg_slice_load_ratio[-1],
                "total_bandwidth_usage": self.total_used_bw[-1],
                "avg_latency_ms": self.avg_latency_ms[-1],
                "p95_latency_ms": self.p95_latency_ms[-1],
                "latency_violation_ratio": self.latency_violation_ratio[-1],
            }
            self.latest_window_slice_bs_counters = self.get_window_counter_snapshot()

            # PRB snapshot must run BEFORE we clear window-scoped trackers below, since it
            # reads `_window_block_per_slice_bs`, `_window_per_ue_latency_samples`, and the
            # per-slice latency samples accumulated this window.
            self._prb_window_index += 1
            self._record_prb_window_snapshot()

            self.connect_attempt.append(0)
            self.block_count.append(0)
            self.handover_count.append(0)
            self._window_latency_samples = []
            self._window_latency_violations = 0
            self._window_slice_latency_samples = {slice_name: [] for slice_name in self.slice_names}
            self._window_slice_first_service_latency_samples = {
                slice_name: [] for slice_name in self.slice_names
            }
            self._window_slice_bs_counters = {}
            self._window_block_per_slice_bs = {}
            self._window_block_per_client = {}
            self._window_per_ue_latency_samples = {}
            yield self.env.timeout(1)

    def get_total_connected_users_ratio(self) -> float:
        """
        Tính tỷ lệ user đang kết nối trên tổng số user nằm trong vùng phủ.
        """
        t, cc = 0, 0
        for c in self.clients:
            if self.is_client_in_coverage(c):
                t += c.connected
                cc += 1
        # for bs in self.base_stations:
        #     for sl in bs.slices:
        #         t += sl.connected_users
        return t/cc if cc != 0 else 0

    def get_total_used_bw(self) -> float:
        """
        Tính tổng băng thông đang được sử dụng trên tất cả slice và base station.
        """
        t = 0
        for bs in self.base_stations:
            for sl in bs.slices:
                t += sl.capacity.capacity - sl.capacity.level
        return t

    def get_avg_slice_load_ratio(self) -> float:
        """
        Tính tỷ lệ tải trung bình trên tất cả slice.
        """
        t, c = 0, 0
        for bs in self.base_stations:
            for sl in bs.slices:
                c += sl.capacity.capacity
                t += sl.capacity.capacity - sl.capacity.level
                #c += 1
                #t += (sl.capacity.capacity - sl.capacity.level) / sl.capacity.capacity
        return t/c if c !=0 else 0

    def get_avg_slice_client_count(self) -> float:
        """
        Tính số client trung bình trên mỗi slice.
        """
        t, c = 0, 0
        for bs in self.base_stations:
            for sl in bs.slices:
                c += 1
                t += sl.connected_users
        return t/c if c !=0 else 0
    
    def get_coverage_ratio(self) -> float:
        """
        Tính tỷ lệ client nằm trong vùng phủ và có kết nối tới base station.
        """
        t, cc = 0, 0
        for c in self.clients:
            if self.is_client_in_coverage(c):
                cc += 1
                if c.base_station is not None and c.base_station.coverage.is_in_coverage(c.x, c.y):
                    t += 1
        return t/cc if cc !=0 else 0

    def incr_connect_attempt(self, client) -> None:
        # Chỉ tính các sự kiện nằm trong vùng bản đồ thống kê đã cấu hình.
        if self.is_client_in_coverage(client):
            self.connect_attempt[-1] += 1

    def incr_block_count(self, client) -> None:
        if self.is_client_in_coverage(client):
            self.block_count[-1] += 1

    def incr_handover_count(self, client) -> None:
        if self.is_client_in_coverage(client):
            self.handover_count[-1] += 1

    def _get_window_bucket(self, slice_name: str, base_station_id: int):
        key = (slice_name, base_station_id)
        if key not in self._window_slice_bs_counters:
            self._window_slice_bs_counters[key] = {
                "client_ids": set(),
                "connected_events": 0,
                "disconnected_events": 0,
                "already_disconnected_events": 0,
                "request_count": 0,
                "requested_usage_sum": 0.0,
                "requested_usage_max": 0.0,
                "distance_samples": [],
            }
        return self._window_slice_bs_counters[key]

    def record_request(self, client, requested_usage: float, network_slice=None, base_station=None) -> None:
        network_slice = network_slice or client.get_slice()
        base_station = base_station or client.base_station
        if network_slice is None or base_station is None:
            return
        bucket = self._get_window_bucket(network_slice.name, base_station.pk)
        bucket["client_ids"].add(client.pk)
        bucket["request_count"] += 1
        bucket["requested_usage_sum"] += float(requested_usage)
        bucket["requested_usage_max"] = max(bucket["requested_usage_max"], float(requested_usage))
        bucket["distance_samples"].append(
            math.dist((client.x, client.y), (base_station.coverage.center[0], base_station.coverage.center[1]))
        )

    def record_connection_event(self, client, event: str, network_slice=None, base_station=None) -> None:
        network_slice = network_slice or client.get_slice()
        base_station = base_station or client.base_station
        if network_slice is None or base_station is None:
            return
        bucket = self._get_window_bucket(network_slice.name, base_station.pk)
        bucket["client_ids"].add(client.pk)
        bucket["distance_samples"].append(
            math.dist((client.x, client.y), (base_station.coverage.center[0], base_station.coverage.center[1]))
        )
        if event == "connected to":
            bucket["connected_events"] += 1
        elif event == "disconnected from":
            bucket["disconnected_events"] += 1
        elif event == "already disconnected":
            bucket["already_disconnected_events"] += 1

    def get_window_counter_snapshot(self) -> dict:
        snapshot = {}
        for key, bucket in self._window_slice_bs_counters.items():
            snapshot[key] = {
                "clients_seen": len(bucket["client_ids"]),
                "connected_events": bucket["connected_events"],
                "disconnected_events": bucket["disconnected_events"],
                "already_disconnected_events": bucket["already_disconnected_events"],
                "request_count": bucket["request_count"],
                "requested_usage_sum": bucket["requested_usage_sum"],
                "requested_usage_max": bucket["requested_usage_max"],
                "requested_usage_mean": (
                    bucket["requested_usage_sum"] / bucket["request_count"]
                    if bucket["request_count"] > 0
                    else 0.0
                ),
                "mean_distance_to_bs": (
                    sum(bucket["distance_samples"]) / len(bucket["distance_samples"])
                    if bucket["distance_samples"]
                    else 0.0
                ),
                "max_distance_to_bs": max(bucket["distance_samples"]) if bucket["distance_samples"] else 0.0,
            }
        return snapshot

    def record_latency(self, client, latency_ms: float, is_violation: bool, slice_name: str | None = None) -> None:
        if self.is_client_in_coverage(client):
            self._window_latency_samples.append(float(latency_ms))
            self._window_latency_violations += int(is_violation)
            if slice_name in self._window_slice_latency_samples:
                self._window_slice_latency_samples[slice_name].append(float(latency_ms))
            # Per-UE latency tracking for opt-in PRB per-UE CSV. Only collect when enabled to
            # avoid memory churn for large client populations.
            if self._prb_config.get("per_ue", False):
                self._window_per_ue_latency_samples.setdefault(client.pk, []).append(float(latency_ms))

    def record_first_service_latency(
        self,
        client,
        latency_ms: float,
        is_violation: bool,
        slice_name: str | None = None,
    ) -> None:
        if self.is_client_in_coverage(client) and slice_name in self._window_slice_first_service_latency_samples:
            self._window_slice_first_service_latency_samples[slice_name].append(float(latency_ms))

    def get_avg_latency_ms(self) -> float:
        if not self._window_latency_samples:
            return 0.0
        return sum(self._window_latency_samples) / len(self._window_latency_samples)

    def get_p95_latency_ms(self) -> float:
        if not self._window_latency_samples:
            return 0.0
        ordered = sorted(self._window_latency_samples)
        index = max(0, math.ceil(0.95 * len(ordered)) - 1)
        return ordered[index]

    def get_latency_violation_ratio(self) -> float:
        if not self._window_latency_samples:
            return 0.0
        return self._window_latency_violations / len(self._window_latency_samples)

    def get_avg_latency_ms_for_slice(self, slice_name: str) -> float:
        samples = self._window_slice_latency_samples.get(slice_name, [])
        if not samples:
            return 0.0
        return sum(samples) / len(samples)

    def get_slice_latency_stats(self) -> dict[str, list[float]]:
        return {slice_name: list(values) for slice_name, values in self.slice_avg_latency_ms.items()}

    def get_avg_first_service_latency_ms_for_slice(self, slice_name: str) -> float:
        samples = self._window_slice_first_service_latency_samples.get(slice_name, [])
        if not samples:
            return 0.0
        return sum(samples) / len(samples)

    def get_slice_first_service_latency_stats(self) -> dict[str, list[float]]:
        return {
            slice_name: list(values)
            for slice_name, values in self.slice_avg_first_service_latency_ms.items()
        }

    def is_client_in_coverage(self, client) -> bool:
        xs, ys = self.area
        return True if xs[0] <= client.x <= xs[1] and ys[0] <= client.y <= ys[1] else False

    # ----- PRB / resource allocation proxy (NetSim-inspired) -----
    # See docs/prb_proxy_metrics.md for limitations: bandwidth-based proxy, no PHY PRB,
    # channel_efficiency = 1.0 in MVP, no SINR/path-loss/numerology yet.

    def record_block_for_client(self, client) -> None:
        """Record an admission-block event AND attribute it to the (BS, slice, client) tuple
        so PRB per-UE / per-slice CSVs can show block_count and is_blocked. Falls back to the
        legacy `incr_block_count(client)` semantics."""
        self.incr_block_count(client)
        sl = client.get_slice()
        bs = client.base_station
        if sl is not None and bs is not None:
            key = (bs.pk, sl.name)
            self._window_block_per_slice_bs[key] = self._window_block_per_slice_bs.get(key, 0) + 1
        self._window_block_per_client[client.pk] = self._window_block_per_client.get(client.pk, 0) + 1

    def _record_prb_window_snapshot(self) -> None:
        """Snapshot per-(BS, slice) and optionally per-UE allocation state at end of window.
        Called from `collect()` BEFORE per-window state is reset."""
        if not self._prb_config.get("enabled", False):
            return
        per_slice = bool(self._prb_config.get("per_slice", True))
        per_ue = bool(self._prb_config.get("per_ue", False))
        if not (per_slice or per_ue):
            return

        channel_efficiency = float(self._prb_config.get("channel_efficiency", 1.0))
        cell_edge_factor = float(self._prb_config.get("cell_edge_factor", 0.90))
        window = self._prb_window_index

        # Aggregate total allocated per BS for slice_ratio_actual computation.
        bs_total_allocated: dict[int, float] = {}
        for bs in self.base_stations:
            total = sum(
                max(float(sl.capacity.capacity) - float(sl.capacity.level), 0.0)
                for sl in bs.slices
            )
            bs_total_allocated[bs.pk] = total

        if per_slice:
            for bs in self.base_stations:
                for sl in bs.slices:
                    avail = float(sl.capacity.capacity)
                    allocated = max(avail - float(sl.capacity.level), 0.0)
                    mapped_ue_count = len(getattr(sl, "connected_clients", set()) or set())
                    requested_bps = mapped_ue_count * float(sl.bandwidth_guaranteed)
                    allocated_mbps = allocated / 1e6
                    requested_mbps = requested_bps / 1e6
                    effective_mbps = allocated_mbps * channel_efficiency
                    unmet_demand_mbps = max(requested_mbps - allocated_mbps, 0.0)
                    allocation_pct = (allocated / avail) if avail > 0 else 0.0
                    total_alloc = bs_total_allocated.get(bs.pk, 0.0)
                    slice_ratio_actual = (allocated / total_alloc) if total_alloc > 0 else 0.0
                    slice_ratio_error = slice_ratio_actual - float(getattr(sl, "ratio", 0.0))
                    # GBR satisfaction
                    gbr_satisfaction_ratio = 0.0
                    if mapped_ue_count > 0 and float(sl.bandwidth_guaranteed) > 0:
                        satisfied = sum(
                            1
                            for c in sl.connected_clients
                            if float(getattr(c, "last_usage", 0.0)) >= float(sl.bandwidth_guaranteed)
                        )
                        gbr_satisfaction_ratio = satisfied / mapped_ue_count
                    block_count = self._window_block_per_slice_bs.get((bs.pk, sl.name), 0)
                    samples = list(self._window_slice_latency_samples.get(sl.name, []))
                    if samples:
                        avg_lat = sum(samples) / len(samples)
                        ordered = sorted(samples)
                        p95_lat = ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]
                    else:
                        avg_lat = 0.0
                        p95_lat = 0.0
                    self._prb_per_slice_history.append({
                        "time_window": window,
                        "bs_id": bs.pk,
                        "slice": sl.name,
                        "mapped_ue_count": mapped_ue_count,
                        "requested_mbps": round(requested_mbps, 6),
                        "allocated_mbps": round(allocated_mbps, 6),
                        "effective_mbps": round(effective_mbps, 6),
                        "unmet_demand_mbps": round(unmet_demand_mbps, 6),
                        "prb_available_proxy": avail,
                        "prb_allocated_proxy": allocated,
                        "allocation_percentage": round(allocation_pct, 6),
                        "slice_ratio_configured": round(float(getattr(sl, "ratio", 0.0)), 6),
                        "slice_ratio_actual": round(slice_ratio_actual, 6),
                        "slice_ratio_error": round(slice_ratio_error, 6),
                        "gbr_satisfaction_ratio": round(gbr_satisfaction_ratio, 6),
                        "block_count": block_count,
                        "avg_latency_ms": round(avg_lat, 6),
                        "p95_latency_ms": round(p95_lat, 6),
                    })

        if per_ue:
            for c in self.clients:
                if not self.is_client_in_coverage(c):
                    continue
                if c.base_station is None:
                    continue
                sl = c.get_slice()
                if sl is None:
                    continue
                last_usage = float(getattr(c, "last_usage", 0.0))
                avail = float(sl.capacity.capacity)
                requested_bps = float(sl.bandwidth_guaranteed)
                allocated_mbps = last_usage / 1e6
                requested_mbps = requested_bps / 1e6
                effective_mbps = allocated_mbps * channel_efficiency
                allocation_pct = (last_usage / avail) if avail > 0 else 0.0
                d = math.dist(
                    (float(c.x), float(c.y)),
                    (float(c.base_station.coverage.center[0]), float(c.base_station.coverage.center[1])),
                )
                is_cell_edge = int(d > float(c.base_station.coverage.radius) * cell_edge_factor)
                is_blocked = int(self._window_block_per_client.get(c.pk, 0) > 0)
                ue_samples = self._window_per_ue_latency_samples.get(c.pk, [])
                latency_ms = (sum(ue_samples) / len(ue_samples)) if ue_samples else 0.0
                self._prb_per_ue_history.append({
                    "time_window": window,
                    "bs_id": c.base_station.pk,
                    "client_id": c.pk,
                    "slice": sl.name,
                    "requested_mbps": round(requested_mbps, 6),
                    "allocated_mbps": round(allocated_mbps, 6),
                    "effective_mbps": round(effective_mbps, 6),
                    "channel_efficiency": channel_efficiency,
                    "prb_available_proxy": avail,
                    "prb_allocated_proxy": last_usage,
                    "allocation_percentage": round(allocation_pct, 6),
                    "is_cell_edge": is_cell_edge,
                    "is_blocked": is_blocked,
                    "latency_ms": round(latency_ms, 6),
                })

    def export_prb_csv(self, output_dir) -> dict:
        """Write prb_per_slice.csv (always when per_slice=True) and prb_per_ue.csv (when
        per_ue=True). Returns {<name>: <path>} for artifacts written."""
        artifacts: dict[str, str] = {}
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        if self._prb_config.get("per_slice", True) and self._prb_per_slice_history:
            target = out_path / "prb_per_slice.csv"
            fieldnames = list(self._prb_per_slice_history[0].keys())
            with target.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self._prb_per_slice_history)
            artifacts["prb_per_slice"] = str(target)
        if self._prb_config.get("per_ue", False) and self._prb_per_ue_history:
            target = out_path / "prb_per_ue.csv"
            fieldnames = list(self._prb_per_ue_history[0].keys())
            with target.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self._prb_per_ue_history)
            artifacts["prb_per_ue"] = str(target)
        return artifacts

