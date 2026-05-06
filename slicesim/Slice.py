class Slice:
    def __init__(
        self,
        name: str,
        ratio: float,
        connected_users: int,
        user_share: float,
        delay_tolerance: float,
        qos_class: int,
        bandwidth_guaranteed: float,
        bandwidth_max: float,
        init_capacity: float,
        usage_pattern,
        baseline_policy=None,
    ):
        """
        Khởi tạo một network slice.
        """
        self.name = name
        self.connected_users = connected_users
        self.user_share = user_share
        self.delay_tolerance = delay_tolerance
        self.qos_class = qos_class
        self.ratio = ratio
        self.bandwidth_guaranteed = bandwidth_guaranteed
        self.bandwidth_max = bandwidth_max
        self.init_capacity = init_capacity
        self.capacity = 0
        self.usage_pattern = usage_pattern
        self.baseline_policy = baseline_policy or {}
        self.runtime_scheduling_weight = 1.0
        self.runtime_admission_guard_factor = 1.0
        self.connected_clients = set()

    def get_effective_capacity(self) -> float:
        admission_policy = self.baseline_policy.get("admission", {})
        if admission_policy.get("use_bandwidth_max_cap", True):
            return min(self.init_capacity, self.bandwidth_max)
        return self.init_capacity

    def apply_runtime_action(
        self,
        *,
        target_ratio: float | None = None,
        base_station_capacity: float | None = None,
        scheduling_weight: float | None = None,
        admission_guard_factor: float | None = None,
    ) -> None:
        if scheduling_weight is not None:
            self.runtime_scheduling_weight = max(float(scheduling_weight), 0.1)
        if admission_guard_factor is not None:
            self.runtime_admission_guard_factor = max(float(admission_guard_factor), 0.1)
        if target_ratio is not None and base_station_capacity is not None:
            self._apply_dynamic_ratio(float(target_ratio), float(base_station_capacity))

    def _apply_dynamic_ratio(self, target_ratio: float, base_station_capacity: float) -> None:
        target_ratio = max(target_ratio, 0.0)
        new_capacity = max(base_station_capacity * target_ratio, 0.0)
        current_capacity = getattr(self.capacity, "capacity", self.init_capacity)
        current_level = getattr(self.capacity, "level", self.init_capacity)
        used_capacity = max(current_capacity - current_level, 0.0)
        clamped_used_capacity = min(used_capacity, new_capacity)
        new_level = max(new_capacity - clamped_used_capacity, 0.0)

        self.ratio = target_ratio
        self.init_capacity = new_capacity
        if hasattr(self.capacity, "_capacity"):
            self.capacity._capacity = new_capacity
        if hasattr(self.capacity, "_level"):
            self.capacity._level = new_level

    def get_load_ratio(self) -> float:
        """
        Trả về tỷ lệ capacity đang được sử dụng của slice.
        """
        total_capacity = getattr(self.capacity, "capacity", 0)
        if total_capacity <= 0:
            return 0.0
        return (total_capacity - self.capacity.level) / total_capacity

    def get_priority_factor(self) -> float:
        """
        Chuyển QoS class thành hệ số ưu tiên đơn giản.
        qos_class càng thấp thì độ ưu tiên càng cao.
        """
        return 1.0 / max(self.qos_class, 1)

    def add_connected_client(self, client) -> None:
        self.connected_clients.add(client)

    def remove_connected_client(self, client) -> None:
        self.connected_clients.discard(client)

    def get_active_connected_clients(self) -> list:
        return [
            client
            for client in self.connected_clients
            if getattr(client, "connected", False) and getattr(client, "usage_remaining", 0) > 0
        ]

    def get_first_service_priority_policy(self) -> dict:
        return self.baseline_policy.get("scheduling", {}).get("first_service_priority", {})

    def get_deadline_priority_policy(self) -> dict:
        return self.baseline_policy.get("scheduling", {}).get("deadline_priority", {})

    def is_first_service_priority_client(self, client) -> bool:
        policy = self.get_first_service_priority_policy()
        if not policy.get("enabled", False):
            return False
        protected_slices = set(policy.get("slices", ["URLLC"]))
        if self.name not in protected_slices:
            return False
        return getattr(client, "current_request_first_service_time", None) is None

    def is_deadline_priority_client(self, client) -> bool:
        policy = self.get_deadline_priority_policy()
        if not policy.get("enabled", False):
            return False
        protected_slices = set(policy.get("slices", ["URLLC"]))
        if self.name not in protected_slices:
            return False
        if getattr(client, "request_start_time", None) is None:
            return False
        if getattr(client, "usage_remaining", 0) <= 0:
            return False
        if policy.get("post_first_service_only", True):
            return getattr(client, "current_request_first_service_time", None) is not None
        return True

    def get_waiting_ratio(self, client) -> float:
        scheduling_policy = self.baseline_policy.get("scheduling", {})
        max_waiting_ratio = max(float(scheduling_policy.get("max_waiting_ratio", 3.0)), 0.0)
        if getattr(client, "request_start_time", None) is None:
            return 0.0
        delay_budget_ms = max(
            float(getattr(client, "current_request_delay_tolerance", self.delay_tolerance) or self.delay_tolerance),
            1.0,
        )
        waiting_ms = max(float(client.env.now) - float(client.request_start_time), 0.0) * client.get_time_unit_ms()
        return min(waiting_ms / delay_budget_ms, max_waiting_ratio)

    def get_deadline_pressure(self, client) -> float:
        policy = self.get_deadline_priority_policy()
        if not self.is_deadline_priority_client(client):
            return 0.0
        delay_budget_ms = max(
            float(getattr(client, "current_request_delay_tolerance", self.delay_tolerance) or self.delay_tolerance),
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

        effective_capacity = max(self.get_effective_capacity(), 1.0)
        remaining_cycles = max(float(getattr(client, "usage_remaining", 0.0)), 0.0) / effective_capacity
        max_remaining_cycles = max(float(policy.get("max_remaining_cycles", 4.0)), 1.0)
        remaining_pressure = min(remaining_cycles / max_remaining_cycles, 1.0)
        return min(
            float(policy.get("elapsed_pressure_weight", 0.70)) * elapsed_pressure
            + float(policy.get("remaining_pressure_weight", 0.30)) * remaining_pressure,
            1.0,
        )

    def get_user_scheduling_weight(self, client) -> float:
        scheduling_policy = self.baseline_policy.get("scheduling", {})
        first_service_policy = self.get_first_service_priority_policy()
        waiting_time_boost = float(scheduling_policy.get("waiting_time_boost", 1.0))
        qos_priority_boost = float(scheduling_policy.get("qos_priority_boost", 1.0))

        priority_component = qos_priority_boost * self.get_priority_factor()
        waiting_ratio = self.get_waiting_ratio(client)
        urgency_component = max(self.runtime_scheduling_weight, 0.1) * waiting_time_boost * waiting_ratio
        first_service_component = 0.0
        if self.is_first_service_priority_client(client):
            first_service_component = float(first_service_policy.get("unserved_boost", 4.0))
            first_service_component += float(first_service_policy.get("waiting_boost", 2.0)) * waiting_ratio
        deadline_policy = self.get_deadline_priority_policy()
        deadline_pressure = self.get_deadline_pressure(client)
        deadline_component = 0.0
        if deadline_pressure > 0:
            deadline_component = float(deadline_policy.get("elapsed_boost", 3.0)) * deadline_pressure
            effective_capacity = max(self.get_effective_capacity(), 1.0)
            remaining_cycles = max(float(getattr(client, "usage_remaining", 0.0)), 0.0) / effective_capacity
            deadline_component += (
                float(deadline_policy.get("remaining_boost", 1.5))
                * min(remaining_cycles / max(float(deadline_policy.get("max_remaining_cycles", 4.0)), 1.0), 1.0)
                * deadline_pressure
            )
        return max(0.05, 1.0 + priority_component + urgency_component + first_service_component + deadline_component)

    def get_admission_latency_theta(self) -> float:
        admission_policy = self.baseline_policy.get("admission", {})
        theta_config = admission_policy.get("latency_theta", 1.0)
        if isinstance(theta_config, dict):
            theta_value = theta_config.get(self.name, theta_config.get("default", 1.0))
        else:
            theta_value = theta_config
        return max(float(theta_value), 0.1)

    def get_latency_discount_factor(self) -> float:
        """
        Ước lượng hệ số giảm trễ cho các slice có ưu tiên cao hơn.
        qos_class thấp hơn và delay_tolerance nhỏ hơn sẽ nhận hệ số thấp hơn.
        """
        qos_component = min(max(self.qos_class, 1), 9) / 9.0
        delay_component = min(max(float(self.delay_tolerance), 10.0), 500.0) / 500.0
        base_factor = max(0.15, 0.5 * qos_component + 0.5 * delay_component)
        return max(0.10, base_factor / max(self.runtime_scheduling_weight, 0.1))

    def get_consumable_share(self, client=None) -> float:
        """
        Trả về lượng băng thông mà một user có thể tiêu thụ trong chu kỳ hiện tại.
        """
        share_mode = self.baseline_policy.get("scheduling", {}).get("share_mode", "equal_share")
        effective_capacity = self.get_effective_capacity()
        if self.connected_users <= 0:
            return effective_capacity

        if share_mode == "weighted_user" and client is not None:
            active_clients = self.get_active_connected_clients()
            if active_clients:
                total_weight = sum(self.get_user_scheduling_weight(active_client) for active_client in active_clients)
                if total_weight > 0:
                    return effective_capacity * self.get_user_scheduling_weight(client) / total_weight

        return effective_capacity / self.connected_users

    def is_available(
        self,
        predicted_first_service_latency_ms: float | None = None,
        request_delay_tolerance: float | None = None,
        admission_guard_factor_override: float | None = None,
    ) -> bool:
        """
        Kiểm tra xem slice có thể admit thêm một user nữa hay không.
        """
        admission_policy = self.baseline_policy.get("admission", {})
        policy_name = admission_policy.get("policy", "guaranteed_bandwidth")
        if policy_name == "always_accept":
            return True

        real_cap = self.get_effective_capacity()
        bandwidth_next = real_cap / (self.connected_users + 1)
        guaranteed_factor = float(admission_policy.get("guaranteed_bw_factor", 1.0))
        required_bandwidth = (
            self.bandwidth_guaranteed * guaranteed_factor
            if admission_policy.get("use_bandwidth_guaranteed", True)
            else 0.0
        )
        admission_guard_factor = (
            float(admission_guard_factor_override)
            if admission_guard_factor_override is not None
            else self.runtime_admission_guard_factor
        )
        required_bandwidth *= max(admission_guard_factor, 0.1)
        if bandwidth_next < required_bandwidth:
            return False

        if (
            predicted_first_service_latency_ms is not None
            and (
                policy_name == "latency_aware_guaranteed_bandwidth"
                or admission_policy.get("latency_guard_enabled", False)
            )
        ):
            delay_budget_ms = max(float(request_delay_tolerance or self.delay_tolerance), 1.0)
            allowed_latency_ms = delay_budget_ms * self.get_admission_latency_theta()
            if float(predicted_first_service_latency_ms) > allowed_latency_ms:
                return False

        return True

    def __str__(self) -> str:
        return (
            f"{self.name:<10} init={self.init_capacity:<5} "
            f"cap={self.capacity.level:<5} diff={(self.init_capacity - self.capacity.level):<5}"
        )
