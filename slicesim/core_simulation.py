"""
Mô-đun core simulation tập trung cho admission, scheduling và latency.

File này gom các engine chạy chính của simulator vào cùng một nơi:
- admission ở mức slice
- admission phía RAN
- scheduling phía RAN
- mô hình hóa latency

Mục tiêu là giúp simulator dễ theo dõi và troubleshoot hơn, đồng thời vẫn giữ
khả năng tương thích với baseline configuration hiện có.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging


@dataclass(slots=True)
class QoSProfile:
    slice_name: str
    delay_tolerance_ms: float
    qos_class: int
    bandwidth_guaranteed: float
    bandwidth_max: float
    arp_priority_level: int | None = None

    @property
    def priority_factor(self) -> float:
        return 1.0 / max(self.qos_class, 1)


@dataclass(slots=True)
class SliceAdmissionDecision:
    accepted: bool
    reason: str
    predicted_first_service_latency_ms: float = 0.0
    quota_blocked: bool = False


class SliceAdmissionEngine:
    """
    Admission ở mức slice theo tinh thần kiểm soát quota kiểu NSAC.

    Hiện tại engine này giữ bộ đếm số session đang hoạt động cho từng slice và
    cho phép đặt giới hạn tùy chọn qua baseline policy mà không cần ép thêm key
    cấu hình mới.
    """

    def __init__(self, baseline_policy: dict | None = None):
        self.baseline_policy = baseline_policy or {}
        self.active_sessions: dict[str, int] = {}

    def get_qos_profile(self, network_slice) -> QoSProfile:
        return QoSProfile(
            slice_name=network_slice.name,
            delay_tolerance_ms=float(network_slice.delay_tolerance),
            qos_class=int(network_slice.qos_class),
            bandwidth_guaranteed=float(network_slice.bandwidth_guaranteed),
            bandwidth_max=float(network_slice.bandwidth_max),
            arp_priority_level=int(network_slice.qos_class),
        )

    def get_max_active_sessions(self, slice_name: str) -> int | None:
        slice_policy = self.baseline_policy.get("slices", {}).get(slice_name, {})
        value = slice_policy.get("max_active_sessions")
        if value in (None, "", 0):
            return None
        return max(int(value), 1)

    def can_accept(self, network_slice) -> SliceAdmissionDecision:
        slice_name = network_slice.name
        active_sessions = self.active_sessions.get(slice_name, 0)
        max_active_sessions = self.get_max_active_sessions(slice_name)
        if max_active_sessions is not None and active_sessions >= max_active_sessions:
            return SliceAdmissionDecision(
                accepted=False,
                reason="slice_session_quota_reached",
                quota_blocked=True,
            )
        return SliceAdmissionDecision(accepted=True, reason="slice_quota_ok")

    def register_connection(self, network_slice) -> None:
        slice_name = network_slice.name
        self.active_sessions[slice_name] = self.active_sessions.get(slice_name, 0) + 1

    def release_connection(self, network_slice) -> None:
        slice_name = network_slice.name
        current = self.active_sessions.get(slice_name, 0)
        self.active_sessions[slice_name] = max(current - 1, 0)


class RanSchedulerEngine:
    """
    Lớp trừu tượng hóa scheduler ở phía RAN.

    Simulator vẫn chạy theo các chu kỳ rời rạc, nhưng quyết định scheduling giờ
    được tính qua engine này thay vì cài trực tiếp trong luồng xử lý của user.
    """

    def __init__(self, baseline_policy: dict | None = None, latency_params: dict | None = None):
        self.baseline_policy = baseline_policy or {}
        self.latency_params = latency_params or {}
        # Cache total scheduling weight per slice within a single sim moment to avoid
        # O(N^2) recomputation when many clients in the same slice query share at the
        # same env.now. Key: id(slice) -> (env_now, total_weight).
        self._weight_sum_cache: dict[int, tuple[float, float]] = {}

    def should_try_immediate_service(self, client, network_slice) -> bool:
        scheduling_policy = self.baseline_policy.get("scheduling", {})
        immediate_service_policy = scheduling_policy.get("immediate_service", {})
        if not immediate_service_policy.get("enabled", True):
            return False
        slice_policy = self.baseline_policy.get("slices", {}).get(network_slice.name, {})
        if "immediate_service_override" in slice_policy:
            return bool(slice_policy["immediate_service_override"])
        qos_threshold = int(
            immediate_service_policy.get(
                "qos_threshold",
                self.latency_params.get("immediate_service_qos_threshold", 2),
            )
        )
        if getattr(network_slice, "runtime_scheduling_weight", 1.0) > 1.15:
            return True
        return network_slice.qos_class <= qos_threshold

    def get_first_service_priority_policy(self) -> dict:
        return self.baseline_policy.get("scheduling", {}).get("first_service_priority", {})

    def get_deadline_priority_policy(self) -> dict:
        return self.baseline_policy.get("scheduling", {}).get("deadline_priority", {})

    def is_first_service_priority_client(self, client, network_slice) -> bool:
        policy = self.get_first_service_priority_policy()
        if not policy.get("enabled", False):
            return False
        protected_slices = set(policy.get("slices", ["URLLC"]))
        if network_slice.name not in protected_slices:
            return False
        return getattr(client, "current_request_first_service_time", None) is None

    def is_deadline_priority_client(self, client, network_slice) -> bool:
        policy = self.get_deadline_priority_policy()
        if not policy.get("enabled", False):
            return False
        protected_slices = set(policy.get("slices", ["URLLC"]))
        if network_slice.name not in protected_slices:
            return False
        if getattr(client, "request_start_time", None) is None:
            return False
        if getattr(client, "usage_remaining", 0) <= 0:
            return False
        if policy.get("post_first_service_only", True):
            return getattr(client, "current_request_first_service_time", None) is not None
        return True

    def get_first_service_admission_guard_override(self, client, network_slice) -> float | None:
        if not self.is_first_service_priority_client(client, network_slice):
            return None
        policy = self.get_first_service_priority_policy()
        if "admission_guard_cap" not in policy:
            return None
        return min(
            float(getattr(network_slice, "runtime_admission_guard_factor", 1.0)),
            max(float(policy.get("admission_guard_cap", 1.0)), 0.1),
        )

    def get_waiting_ratio(self, client, network_slice) -> float:
        scheduling_policy = self.baseline_policy.get("scheduling", {})
        max_waiting_ratio = max(float(scheduling_policy.get("max_waiting_ratio", 3.0)), 0.0)
        if getattr(client, "request_start_time", None) is None:
            return 0.0
        delay_budget_ms = max(
            float(getattr(client, "current_request_delay_tolerance", network_slice.delay_tolerance) or network_slice.delay_tolerance),
            1.0,
        )
        waiting_ms = max(float(client.env.now) - float(client.request_start_time), 0.0) * client.get_time_unit_ms()
        return min(waiting_ms / delay_budget_ms, max_waiting_ratio)

    def get_deadline_pressure(self, client, network_slice) -> float:
        policy = self.get_deadline_priority_policy()
        if not self.is_deadline_priority_client(client, network_slice):
            return 0.0
        delay_budget_ms = max(
            float(getattr(client, "current_request_delay_tolerance", network_slice.delay_tolerance) or network_slice.delay_tolerance),
            1.0,
        )
        elapsed_ms = max(float(client.env.now) - float(client.request_start_time), 0.0) * client.get_time_unit_ms()
        elapsed_ratio = elapsed_ms / delay_budget_ms
        min_elapsed_ratio = max(float(policy.get("min_elapsed_ratio", 0.15)), 0.0)
        max_elapsed_ratio = max(float(policy.get("max_elapsed_ratio", 1.0)), min_elapsed_ratio + 1e-6)
        elapsed_pressure = min(
            max((elapsed_ratio - min_elapsed_ratio) / (max_elapsed_ratio - min_elapsed_ratio), 0.0),
            1.0,
        )

        effective_capacity = max(network_slice.get_effective_capacity(), 1.0)
        remaining_cycles = max(float(getattr(client, "usage_remaining", 0.0)), 0.0) / effective_capacity
        max_remaining_cycles = max(float(policy.get("max_remaining_cycles", 4.0)), 1.0)
        remaining_pressure = min(remaining_cycles / max_remaining_cycles, 1.0)
        return min(
            float(policy.get("elapsed_pressure_weight", 0.70)) * elapsed_pressure
            + float(policy.get("remaining_pressure_weight", 0.30)) * remaining_pressure,
            1.0,
        )

    def estimate_wait_cycles(self, client, network_slice) -> float:
        admission_policy = self.baseline_policy.get("admission", {})
        first_service_policy = self.get_first_service_priority_policy()
        waiting_cycles = 0.0
        if not self.should_try_immediate_service(client, network_slice):
            waiting_cycles += float(admission_policy.get("predicted_wait_base_cycles", 1.0))
        waiting_cycles += float(admission_policy.get("predicted_wait_per_user_cycles", 0.15)) * max(
            network_slice.connected_users,
            0,
        )
        waiting_cycles += float(admission_policy.get("predicted_wait_load_scale", 1.0)) * network_slice.get_load_ratio()
        waiting_cycles /= max(network_slice.runtime_scheduling_weight, 0.1)
        if self.is_first_service_priority_client(client, network_slice):
            waiting_cycles *= float(first_service_policy.get("admission_wait_discount", 0.35))
        return max(waiting_cycles, 0.0)

    def get_user_scheduling_weight(self, client, network_slice) -> float:
        scheduling_policy = self.baseline_policy.get("scheduling", {})
        first_service_policy = self.get_first_service_priority_policy()
        waiting_time_boost = float(scheduling_policy.get("waiting_time_boost", 1.0))
        qos_priority_boost = float(scheduling_policy.get("qos_priority_boost", 1.0))

        priority_component = qos_priority_boost * network_slice.get_priority_factor()
        waiting_ratio = self.get_waiting_ratio(client, network_slice)
        urgency_component = max(network_slice.runtime_scheduling_weight, 0.1) * waiting_time_boost * waiting_ratio
        first_service_component = 0.0
        if self.is_first_service_priority_client(client, network_slice):
            first_service_component = float(first_service_policy.get("unserved_boost", 4.0))
            first_service_component += float(first_service_policy.get("waiting_boost", 2.0)) * waiting_ratio
        deadline_policy = self.get_deadline_priority_policy()
        deadline_pressure = self.get_deadline_pressure(client, network_slice)
        deadline_component = 0.0
        if deadline_pressure > 0:
            deadline_component = float(deadline_policy.get("elapsed_boost", 3.0)) * deadline_pressure
            effective_capacity = max(network_slice.get_effective_capacity(), 1.0)
            remaining_cycles = max(float(getattr(client, "usage_remaining", 0.0)), 0.0) / effective_capacity
            deadline_component += (
                float(deadline_policy.get("remaining_boost", 1.5))
                * min(remaining_cycles / max(float(deadline_policy.get("max_remaining_cycles", 4.0)), 1.0), 1.0)
                * deadline_pressure
            )
        return max(0.05, 1.0 + priority_component + urgency_component + first_service_component + deadline_component)

    def get_consumable_share(self, client, network_slice) -> float:
        share_mode = self.baseline_policy.get("scheduling", {}).get("share_mode", "equal_share")
        effective_capacity = network_slice.get_effective_capacity()
        if network_slice.connected_users <= 0:
            return effective_capacity

        if share_mode == "weighted_user" and client is not None:
            slice_id = id(network_slice)
            now = float(client.env.now)
            cached = self._weight_sum_cache.get(slice_id)
            if cached is not None and cached[0] == now:
                total_weight = cached[1]
            else:
                active_clients = network_slice.get_active_connected_clients()
                if active_clients:
                    total_weight = sum(
                        self.get_user_scheduling_weight(active_client, network_slice) for active_client in active_clients
                    )
                else:
                    total_weight = 0.0
                self._weight_sum_cache[slice_id] = (now, total_weight)
            if total_weight > 0:
                return effective_capacity * self.get_user_scheduling_weight(client, network_slice) / total_weight

        return effective_capacity / network_slice.connected_users


class LatencyModel:
    """
    Mô hình ước lượng latency theo từng chặng cho simulator rút gọn.
    """

    def __init__(self, baseline_policy: dict | None = None, latency_params: dict | None = None, scheduler=None):
        self.baseline_policy = baseline_policy or {}
        self.latency_params = latency_params or {}
        self.scheduler = scheduler

    def get_time_unit_ms(self, client) -> float:
        return float(self.latency_params.get("time_unit_ms", 1.0))

    def get_request_setup_mode(self) -> str:
        mode = str(
            self.latency_params.get(
                "request_setup_mode",
                self.latency_params.get("setup_latency_mode", "none"),
            )
        ).strip().lower()
        aliases = {
            "": "none",
            "off": "none",
            "false": "none",
            "disabled": "none",
            "disable": "none",
            "user_plane": "none",
            "data_plane": "none",
            "control_plane_first_request": "first_request",
            "session_start": "first_request",
            "first_session": "first_request",
            "legacy": "per_request",
            "always": "per_request",
            "every_request": "per_request",
        }
        return aliases.get(mode, mode)

    def estimate_control_plane_setup_latency_ms(self) -> float:
        return (
            float(self.latency_params.get("attach_ms", 0.5))
            + float(self.latency_params.get("auth_ms", 0.5))
            + float(self.latency_params.get("pdu_session_ms", 0.5))
        )

    def estimate_setup_latency_ms(self, client) -> float:
        mode = self.get_request_setup_mode()
        if mode == "per_request":
            return self.estimate_control_plane_setup_latency_ms()
        if mode == "first_request" and not getattr(client, "session_established", False):
            return self.estimate_control_plane_setup_latency_ms()
        return 0.0

    def estimate_admission_latency_ms(self, client, network_slice) -> float:
        base_station_load = 0.0
        if client.base_station is not None and client.base_station.capacity_bandwidth > 0:
            total_used_bandwidth = sum(
                bs_slice.capacity.capacity - bs_slice.capacity.level for bs_slice in client.base_station.slices
            )
            base_station_load = total_used_bandwidth / client.base_station.capacity_bandwidth
        delay_discount = network_slice.get_latency_discount_factor()
        return (
            float(self.latency_params.get("admission_base_ms", 0.1))
            + float(self.latency_params.get("admission_per_connected_user_ms", 0.02)) * network_slice.connected_users
            + float(self.latency_params.get("admission_per_bs_load_ms", 0.5)) * base_station_load
        ) * delay_discount

    def estimate_predicted_first_service_latency_ms(self, client, network_slice) -> float:
        waiting_cycles = 0.0
        if self.scheduler is not None:
            waiting_cycles = self.scheduler.estimate_wait_cycles(client, network_slice)
        return (
            float(getattr(client, "current_request_setup_ms", 0.0))
            + float(getattr(client, "current_request_admission_ms", 0.0))
            + waiting_cycles * self.get_time_unit_ms(client)
        )

    def estimate_processing_latency_ms(self, client, network_slice) -> tuple[float, float]:
        load_ratio = network_slice.get_load_ratio()
        delay_discount = network_slice.get_latency_discount_factor()
        core_ms = (
            float(self.latency_params.get("core_base_ms", 0.25))
            + float(self.latency_params.get("core_load_factor_ms", 0.5)) * load_ratio
        ) * delay_discount
        edge_ms = (
            float(self.latency_params.get("edge_base_ms", 0.25))
            + float(self.latency_params.get("edge_load_factor_ms", 0.5)) * load_ratio
        ) * delay_discount
        return core_ms, edge_ms

    def compute_first_service_latency_ms(self, client, network_slice) -> float:
        first_service_elapsed_ms = max(float(client.env.now) - float(client.request_start_time), 0.0) * self.get_time_unit_ms(client)
        return (
            first_service_elapsed_ms
            + float(getattr(client, "current_request_setup_ms", 0.0))
            + float(getattr(client, "current_request_admission_ms", 0.0))
        )

    def compute_completion_latency_ms(self, client, network_slice) -> float:
        elapsed_ms = max(float(client.env.now) - float(client.request_start_time), 0.0) * self.get_time_unit_ms(client)
        core_ms, edge_ms = self.estimate_processing_latency_ms(client, network_slice)
        handover_ms = float(self.latency_params.get("handover_penalty_ms", 1.0)) * float(
            getattr(client, "current_request_handover_count", 0)
        )
        return (
            elapsed_ms
            + float(getattr(client, "current_request_setup_ms", 0.0))
            + float(getattr(client, "current_request_admission_ms", 0.0))
            + core_ms
            + edge_ms
            + handover_ms
        )


class RanAdmissionEngine:
    """
    Admission ở mức flow phía RAN.
    """

    def __init__(self, baseline_policy: dict | None = None, slice_admission=None, latency_model=None):
        self.baseline_policy = baseline_policy or {}
        self.slice_admission = slice_admission or SliceAdmissionEngine(self.baseline_policy)
        self.latency_model = latency_model

    def evaluate(self, client, network_slice) -> SliceAdmissionDecision:
        slice_decision = self.slice_admission.can_accept(network_slice)
        if not slice_decision.accepted:
            return slice_decision

        predicted_first_service_latency_ms = None
        if getattr(client, "request_start_time", None) is not None and self.latency_model is not None:
            candidate_admission_ms = self.latency_model.estimate_admission_latency_ms(client, network_slice)
            previous_admission_ms = float(getattr(client, "current_request_admission_ms", 0.0))
            client.current_request_admission_ms = previous_admission_ms + candidate_admission_ms
            predicted_first_service_latency_ms = self.latency_model.estimate_predicted_first_service_latency_ms(
                client,
                network_slice,
            )
            client.current_request_admission_ms = previous_admission_ms
        else:
            candidate_admission_ms = 0.0

        accepted = network_slice.is_available(
            predicted_first_service_latency_ms=predicted_first_service_latency_ms,
            request_delay_tolerance=getattr(client, "current_request_delay_tolerance", None),
            admission_guard_factor_override=self.latency_model.scheduler.get_first_service_admission_guard_override(
                client,
                network_slice,
            )
            if self.latency_model is not None and getattr(self.latency_model, "scheduler", None) is not None
            else None,
        )
        if accepted and getattr(client, "request_start_time", None) is not None:
            client.current_request_admission_ms += candidate_admission_ms
        return SliceAdmissionDecision(
            accepted=accepted,
            reason="ran_admission_ok" if accepted else "ran_capacity_or_latency_blocked",
            predicted_first_service_latency_ms=float(predicted_first_service_latency_ms or 0.0),
        )

    def register_connection(self, network_slice, client) -> None:
        network_slice.connected_users += 1
        network_slice.add_connected_client(client)
        self.slice_admission.register_connection(network_slice)

    def release_connection(self, network_slice, client) -> None:
        network_slice.connected_users = max(network_slice.connected_users - 1, 0)
        network_slice.remove_connected_client(client)
        self.slice_admission.release_connection(network_slice)


class CoreSimulationEngine:
    """
    Orchestrator chính cho phần core hiện tại của simulator.

    Lớp này giữ logic admission, scheduling và latency ở cùng một nơi, trong
    khi vẫn cho phép phần còn lại của simulator giữ được cấu trúc gọn nhẹ.
    """

    def __init__(self, baseline_policy: dict | None = None, latency_params: dict | None = None):
        self.baseline_policy = baseline_policy or {}
        self.latency_params = latency_params or {}
        self.slice_admission = SliceAdmissionEngine(self.baseline_policy)
        self.scheduler = RanSchedulerEngine(self.baseline_policy, self.latency_params)
        self.latency_model = LatencyModel(self.baseline_policy, self.latency_params, scheduler=self.scheduler)
        self.ran_admission = RanAdmissionEngine(
            self.baseline_policy,
            slice_admission=self.slice_admission,
            latency_model=self.latency_model,
        )

    def initialize_request(self, client, network_slice) -> None:
        client.request_start_time = float(client.env.now)
        client.current_request_delay_tolerance = network_slice.delay_tolerance
        client.current_request_setup_ms = self.latency_model.estimate_setup_latency_ms(client)
        client.current_request_admission_ms = 0.0
        client.current_request_handover_count = 0
        client.current_request_first_service_time = None

    def should_try_immediate_service(self, client, network_slice) -> bool:
        return self.scheduler.should_try_immediate_service(client, network_slice)

    def attempt_connection(self, client):
        network_slice = client.get_slice()
        if client.connected:
            return True
        if network_slice is None:
            return False

        client.stat_collector.incr_connect_attempt(client)
        decision = self.ran_admission.evaluate(client, network_slice)
        if decision.accepted:
            self.ran_admission.register_connection(network_slice, client)
            client.connected = True
            client.session_established = True
            client.stat_collector.record_connection_event(client, "connected to", network_slice, client.base_station)
            logging.info(
                f'[{int(client.env.now)}] Client_{client.pk} [{client.x}, {client.y}] connected to slice={client.get_slice()} @ {client.base_station}'
            )
            return True

        allow_alternate_bs_retry = self.baseline_policy.get("admission", {}).get("allow_alternate_bs_retry", True)
        previous_base_station = client.base_station
        if allow_alternate_bs_retry and client.base_station is not None:
            client.assign_closest_base_station(exclude=[client.base_station.pk])
            if client.usage_remaining > 0 and client.base_station is not None and previous_base_station != client.base_station:
                client.current_request_handover_count += 1

        retry_slice = client.get_slice()
        if allow_alternate_bs_retry and client.base_station is not None and retry_slice is not None:
            retry_decision = self.ran_admission.evaluate(client, retry_slice)
            if retry_decision.accepted:
                self.ran_admission.register_connection(retry_slice, client)
                client.connected = True
                client.session_established = True
                client.stat_collector.incr_handover_count(client)
                client.stat_collector.record_connection_event(client, "connected to", retry_slice, client.base_station)
                logging.info(
                    f'[{int(client.env.now)}] Client_{client.pk} [{client.x}, {client.y}] connected to slice={client.get_slice()} @ {client.base_station} after alternate-BS retry'
                )
                return True
            else:
                # PRB per-UE block tracking via Stats.record_block_for_client.
                client.stat_collector.record_block_for_client(client)
        else:
            client.stat_collector.record_block_for_client(client)

        logging.warning(
            f'[{int(client.env.now)}] Client_{client.pk} [{client.x}, {client.y}] connection refused to slice={client.get_slice()} @ {client.base_station}'
        )
        return False

    def disconnect_client(self, client):
        network_slice = client.get_slice()
        if client.connected is False:
            if network_slice is not None:
                network_slice.remove_connected_client(client)
            client.stat_collector.record_connection_event(client, "already disconnected", network_slice, client.base_station)
            logging.info(
                f'[{int(client.env.now)}] Client_{client.pk} [{client.x}, {client.y}] is already disconnected from slice={network_slice} @ {client.base_station}'
            )
            return True

        if network_slice is not None:
            self.ran_admission.release_connection(network_slice, client)
        client.connected = False
        client.stat_collector.record_connection_event(client, "disconnected from", network_slice, client.base_station)
        logging.info(
            f'[{int(client.env.now)}] Client_{client.pk} [{client.x}, {client.y}] disconnected from slice={network_slice} @ {client.base_station}'
        )
        return True

    def get_consumable_share(self, client, network_slice) -> float:
        return self.scheduler.get_consumable_share(client, network_slice)

    def estimate_setup_latency_ms(self, client) -> float:
        return self.latency_model.estimate_setup_latency_ms(client)

    def estimate_admission_latency_ms(self, client, network_slice) -> float:
        return self.latency_model.estimate_admission_latency_ms(client, network_slice)

    def estimate_predicted_first_service_latency_ms(self, client, network_slice) -> float:
        return self.latency_model.estimate_predicted_first_service_latency_ms(client, network_slice)

    def estimate_processing_latency_ms(self, client, network_slice) -> tuple[float, float]:
        return self.latency_model.estimate_processing_latency_ms(client, network_slice)

    def compute_first_service_latency_ms(self, client, network_slice) -> float:
        return self.latency_model.compute_first_service_latency_ms(client, network_slice)

    def compute_completion_latency_ms(self, client, network_slice) -> float:
        return self.latency_model.compute_completion_latency_ms(client, network_slice)
