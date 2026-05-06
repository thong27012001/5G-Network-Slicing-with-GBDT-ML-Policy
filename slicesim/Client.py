import logging
import operator
import random

from .utils import KDTree, distance


class Client:
    def __init__(
        self,
        pk: int,
        env,
        x: float,
        y: float,
        mobility_pattern,
        usage_freq: float,
        subscribed_slice_index: int,
        stat_collector,
        base_station=None,
        latency_params=None,
        baseline_policy=None,
        core_simulation=None,
    ):
        """
        Khởi tạo một client trong mô phỏng.
        """
        self.pk = pk
        self.env = env
        self.x = x
        self.y = y
        self.mobility_pattern = mobility_pattern
        self.usage_freq = usage_freq
        self.base_station = base_station
        self.stat_collector = stat_collector
        self.subscribed_slice_index = subscribed_slice_index
        self.usage_remaining = 0
        self.last_usage = 0
        self.closest_base_stations = []
        self.connected = False
        self.latency_params = latency_params or {}
        self.baseline_policy = baseline_policy or {}
        self.core_simulation = core_simulation
        self.request_start_time = None
        self.current_request_delay_tolerance = None
        self.current_request_setup_ms = 0.0
        self.current_request_admission_ms = 0.0
        self.current_request_handover_count = 0
        self.current_request_first_service_time = None
        self.session_established = False

        # Thống kê.
        self.total_connected_time = 0
        self.total_unconnected_time = 0
        self.total_request_count = 0
        self.total_consume_time = 0
        self.total_usage = 0
        self.total_completed_requests = 0
        self.total_latency_ms = 0.0
        self.max_latency_ms = 0.0
        self.latency_violation_count = 0
        self.last_completed_latency_ms = 0.0
        self.total_first_service_latency_ms = 0.0
        self.max_first_service_latency_ms = 0.0
        self.first_service_latency_violation_count = 0
        self.last_first_service_latency_ms = 0.0

        self.action = env.process(self.iter())

    def iter(self):
        """
        Mỗi chu kỳ gồm bốn bước:
            1- .00: Giữ tài nguyên
            2- .25: Thu thập thống kê
            3- .50: Nhả tài nguyên
            4- .75: Di chuyển
        """

        # .00: Giữ tài nguyên.
        if self.base_station is not None:
            if self.usage_remaining > 0:
                if self.connected:
                    self.start_consume()
                else:
                    if self.connect():
                        current_slice = self.get_slice()
                        if current_slice is not None and self.should_try_immediate_service(current_slice):
                            self.start_consume()
            else:
                if self.connected:
                    self.disconnect()
                else:
                    self.generate_usage_and_connect()

        yield self.env.timeout(0.25)

        # .25: Thu thập thống kê.
        if self.connected:
            self.total_connected_time += 0.25
        else:
            self.total_unconnected_time += 0.25

        yield self.env.timeout(0.25)

        # .50: Nhả tài nguyên.
        if self.connected and self.last_usage > 0:
            self.release_consume()
            if self.usage_remaining <= 0:
                self.disconnect()

        yield self.env.timeout(0.25)

        # .75: Di chuyển.
        x, y = self.mobility_pattern.generate_movement()
        self.x += x
        self.y += y

        if self.base_station is not None:
            previous_base_station = self.base_station
            if not previous_base_station.coverage.is_in_coverage(self.x, self.y):
                self.disconnect()
                self.assign_closest_base_station(exclude=[previous_base_station.pk])
                if self.usage_remaining > 0 and self.base_station is not None and previous_base_station != self.base_station:
                    self.current_request_handover_count += 1
        else:
            self.assign_closest_base_station()

        yield self.env.timeout(0.25)

        yield self.env.process(self.iter())

    def get_slice(self):
        if self.base_station is None:
            return None
        return self.base_station.slices[self.subscribed_slice_index]

    def generate_usage_and_connect(self):
        network_slice = self.get_slice()
        if self.usage_freq < random.random() and network_slice is not None:
            self.usage_remaining = network_slice.usage_pattern.generate()
            self.total_request_count += 1
            self.stat_collector.record_request(self, self.usage_remaining, network_slice, self.base_station)
            if self.core_simulation is not None:
                self.core_simulation.initialize_request(self, network_slice)
            else:
                self.request_start_time = float(self.env.now)
                self.current_request_delay_tolerance = network_slice.delay_tolerance
                self.current_request_setup_ms = self.estimate_setup_latency_ms()
                self.current_request_admission_ms = 0.0
                self.current_request_handover_count = 0
                self.current_request_first_service_time = None
            self.connect()
            current_slice = self.get_slice()
            if self.connected and current_slice is not None and self.should_try_immediate_service(current_slice):
                self.start_consume()
            logging.info(
                f'[{int(self.env.now)}] Client_{self.pk} [{self.x}, {self.y}] requests {self.usage_remaining} usage.'
            )

    def connect(self):
        if self.core_simulation is not None:
            return self.core_simulation.attempt_connection(self)

        network_slice = self.get_slice()
        if self.connected:
            return True
        if network_slice is None:
            return False

        self.stat_collector.incr_connect_attempt(self)
        predicted_first_service_latency_ms = None
        if self.request_start_time is not None:
            self.current_request_admission_ms += self.estimate_admission_latency_ms(network_slice)
            predicted_first_service_latency_ms = self.estimate_predicted_first_service_latency_ms(network_slice)

        if network_slice.is_available(
            predicted_first_service_latency_ms=predicted_first_service_latency_ms,
            request_delay_tolerance=self.current_request_delay_tolerance,
        ):
            network_slice.connected_users += 1
            network_slice.add_connected_client(self)
            self.connected = True
            self.session_established = True
            self.stat_collector.record_connection_event(self, "connected to", network_slice, self.base_station)
            logging.info(
                f'[{int(self.env.now)}] Client_{self.pk} [{self.x}, {self.y}] connected to slice={self.get_slice()} @ {self.base_station}'
            )
            return True

        allow_alternate_bs_retry = self.baseline_policy.get("admission", {}).get("allow_alternate_bs_retry", True)
        previous_base_station = self.base_station
        if allow_alternate_bs_retry and self.base_station is not None:
            self.assign_closest_base_station(exclude=[self.base_station.pk])
            if self.usage_remaining > 0 and self.base_station is not None and previous_base_station != self.base_station:
                self.current_request_handover_count += 1

        retry_slice = self.get_slice()
        retry_predicted_first_service_latency_ms = None
        if allow_alternate_bs_retry and retry_slice is not None and self.request_start_time is not None:
            retry_predicted_first_service_latency_ms = self.estimate_predicted_first_service_latency_ms(retry_slice)

        if (
            allow_alternate_bs_retry
            and self.base_station is not None
            and retry_slice is not None
            and retry_slice.is_available(
                predicted_first_service_latency_ms=retry_predicted_first_service_latency_ms,
                request_delay_tolerance=self.current_request_delay_tolerance,
            )
        ):
            self.stat_collector.incr_handover_count(self)
        else:
            # PRB per-UE block tracking: record_block_for_client wraps the legacy
            # incr_block_count and additionally attributes the block to (client, BS, slice).
            self.stat_collector.record_block_for_client(self)

        logging.warning(
            f'[{int(self.env.now)}] Client_{self.pk} [{self.x}, {self.y}] connection refused to slice={self.get_slice()} @ {self.base_station}'
        )
        return False

    def disconnect(self):
        if self.core_simulation is not None:
            return self.core_simulation.disconnect_client(self)

        network_slice = self.get_slice()
        if self.connected is False:
            if network_slice is not None:
                network_slice.remove_connected_client(self)
            self.stat_collector.record_connection_event(self, "already disconnected", self.get_slice(), self.base_station)
            logging.info(
                f'[{int(self.env.now)}] Client_{self.pk} [{self.x}, {self.y}] is already disconnected from slice={self.get_slice()} @ {self.base_station}'
            )
        else:
            network_slice.connected_users -= 1
            network_slice.remove_connected_client(self)
            self.connected = False
            self.stat_collector.record_connection_event(self, "disconnected from", network_slice, self.base_station)
            logging.info(
                f'[{int(self.env.now)}] Client_{self.pk} [{self.x}, {self.y}] disconnected from slice={self.get_slice()} @ {self.base_station}'
            )
        return not self.connected

    def start_consume(self):
        network_slice = self.get_slice()
        if network_slice is None:
            return
        if self.core_simulation is not None:
            consumable_share = self.core_simulation.get_consumable_share(self, network_slice)
        else:
            consumable_share = network_slice.get_consumable_share(self)
        amount = min(consumable_share, self.usage_remaining)
        if amount <= 0:
            return
        network_slice.capacity.get(amount)
        if self.current_request_first_service_time is None:
            self.current_request_first_service_time = float(self.env.now)
            self.record_first_service_latency(network_slice)
        logging.info(f'[{int(self.env.now)}] Client_{self.pk} [{self.x}, {self.y}] gets {amount} usage.')
        self.last_usage = amount

    def release_consume(self):
        network_slice = self.get_slice()
        if network_slice is None:
            return
        if self.last_usage > 0:
            network_slice.capacity.put(self.last_usage)
            logging.info(
                f'[{int(self.env.now)}] Client_{self.pk} [{self.x}, {self.y}] puts back {self.last_usage} usage.'
            )
            self.total_consume_time += 1
            self.total_usage += self.last_usage
            self.usage_remaining -= self.last_usage
            self.last_usage = 0
            if self.usage_remaining <= 0:
                self.finalize_request_latency(network_slice)

    def get_time_unit_ms(self) -> float:
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

    def should_try_immediate_service(self, network_slice) -> bool:
        if self.core_simulation is not None:
            return self.core_simulation.should_try_immediate_service(self, network_slice)

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

    def estimate_setup_latency_ms(self) -> float:
        if self.core_simulation is not None:
            return self.core_simulation.estimate_setup_latency_ms(self)
        mode = self.get_request_setup_mode()
        if mode == "per_request":
            return self.estimate_control_plane_setup_latency_ms()
        if mode == "first_request" and not self.session_established:
            return self.estimate_control_plane_setup_latency_ms()
        return 0.0

    def estimate_admission_latency_ms(self, network_slice) -> float:
        if self.core_simulation is not None:
            return self.core_simulation.estimate_admission_latency_ms(self, network_slice)
        base_station_load = 0.0
        if self.base_station is not None and self.base_station.capacity_bandwidth > 0:
            total_used_bandwidth = sum(
                bs_slice.capacity.capacity - bs_slice.capacity.level for bs_slice in self.base_station.slices
            )
            base_station_load = total_used_bandwidth / self.base_station.capacity_bandwidth
        delay_discount = network_slice.get_latency_discount_factor()
        return (
            float(self.latency_params.get("admission_base_ms", 0.1))
            + float(self.latency_params.get("admission_per_connected_user_ms", 0.02)) * network_slice.connected_users
            + float(self.latency_params.get("admission_per_bs_load_ms", 0.5)) * base_station_load
        ) * delay_discount

    def estimate_predicted_first_service_latency_ms(self, network_slice) -> float:
        if self.core_simulation is not None:
            return self.core_simulation.estimate_predicted_first_service_latency_ms(self, network_slice)
        admission_policy = self.baseline_policy.get("admission", {})
        waiting_cycles = 0.0
        if not self.should_try_immediate_service(network_slice):
            waiting_cycles += float(admission_policy.get("predicted_wait_base_cycles", 1.0))
        waiting_cycles += float(admission_policy.get("predicted_wait_per_user_cycles", 0.15)) * max(
            network_slice.connected_users,
            0,
        )
        waiting_cycles += float(admission_policy.get("predicted_wait_load_scale", 1.0)) * network_slice.get_load_ratio()
        waiting_cycles /= max(network_slice.runtime_scheduling_weight, 0.1)
        return self.current_request_setup_ms + self.current_request_admission_ms + waiting_cycles * self.get_time_unit_ms()

    def estimate_processing_latency_ms(self, network_slice) -> tuple[float, float]:
        if self.core_simulation is not None:
            return self.core_simulation.estimate_processing_latency_ms(self, network_slice)
        load_ratio = network_slice.get_load_ratio()
        delay_discount = network_slice.get_latency_discount_factor()
        core_ms = (
            float(self.latency_params.get("core_base_ms", 0.25))
            + float(self.latency_params.get("core_load_factor_ms", 0.5)) * load_ratio
        ) * delay_discount
        edge_ms = (
            float(self.latency_params.get("edge_base_ms", 0.25))
            + float(self.latency_params.get("edge_load_factor_ms", 0.5))
            * load_ratio
        ) * delay_discount
        return core_ms, edge_ms

    def record_first_service_latency(self, network_slice) -> None:
        if self.request_start_time is None:
            return
        if self.core_simulation is not None:
            first_service_latency_ms = self.core_simulation.compute_first_service_latency_ms(self, network_slice)
        else:
            first_service_elapsed_ms = max(float(self.env.now) - self.request_start_time, 0.0) * self.get_time_unit_ms()
            first_service_latency_ms = (
                first_service_elapsed_ms
                + self.current_request_setup_ms
                + self.current_request_admission_ms
            )
        delay_tolerance = self.current_request_delay_tolerance or network_slice.delay_tolerance
        is_violation = first_service_latency_ms > delay_tolerance

        self.total_first_service_latency_ms += first_service_latency_ms
        self.max_first_service_latency_ms = max(self.max_first_service_latency_ms, first_service_latency_ms)
        self.last_first_service_latency_ms = first_service_latency_ms
        self.first_service_latency_violation_count += int(is_violation)
        self.stat_collector.record_first_service_latency(
            self,
            first_service_latency_ms,
            is_violation,
            slice_name=network_slice.name,
        )

    def finalize_request_latency(self, network_slice) -> None:
        if self.request_start_time is None:
            return

        if self.core_simulation is not None:
            total_latency_ms = self.core_simulation.compute_completion_latency_ms(self, network_slice)
        else:
            elapsed_ms = max(float(self.env.now) - self.request_start_time, 0.0) * self.get_time_unit_ms()
            core_ms, edge_ms = self.estimate_processing_latency_ms(network_slice)
            handover_ms = float(self.latency_params.get("handover_penalty_ms", 1.0)) * self.current_request_handover_count
            total_latency_ms = (
                elapsed_ms
                + self.current_request_setup_ms
                + self.current_request_admission_ms
                + core_ms
                + edge_ms
                + handover_ms
            )
        delay_tolerance = self.current_request_delay_tolerance or network_slice.delay_tolerance
        is_violation = total_latency_ms > delay_tolerance

        self.total_completed_requests += 1
        self.total_latency_ms += total_latency_ms
        self.max_latency_ms = max(self.max_latency_ms, total_latency_ms)
        self.last_completed_latency_ms = total_latency_ms
        self.latency_violation_count += int(is_violation)
        self.stat_collector.record_latency(self, total_latency_ms, is_violation, slice_name=network_slice.name)

        logging.info(
            f'[{int(self.env.now)}] Client_{self.pk} [{self.x}, {self.y}] completed request with latency={total_latency_ms:.3f} ms '
            f'(setup={self.current_request_setup_ms:.3f}, admission={self.current_request_admission_ms:.3f}, '
            f'handovers={self.current_request_handover_count}, violation={is_violation}).'
        )

        self.request_start_time = None
        self.current_request_delay_tolerance = None
        self.current_request_setup_ms = 0.0
        self.current_request_admission_ms = 0.0
        self.current_request_handover_count = 0
        self.current_request_first_service_time = None

    # Kiểm tra các base station gần nhất của client và gán base station gần nhất khả dụng không bị loại trừ.
    def assign_closest_base_station(self, exclude=None):
        updated_list = []
        for d, base_station in self.closest_base_stations:
            if exclude is not None and base_station.pk in exclude:
                continue
            d = distance((self.x, self.y), (base_station.coverage.center[0], base_station.coverage.center[1]))
            updated_list.append((d, base_station))
        updated_list.sort(key=operator.itemgetter(0))
        for d, base_station in updated_list:
            if d <= base_station.coverage.radius:
                self.base_station = base_station
                logging.info(f'[{int(self.env.now)}] Client_{self.pk} freshly assigned to {self.base_station}')
                return
        if KDTree.last_run_time != int(self.env.now):
            KDTree.run(self.stat_collector.clients, self.stat_collector.base_stations, int(self.env.now), assign=False)
        self.base_station = None

    def __str__(self) -> str:
        return (
            f'Client_{self.pk} [{self.x:<5}, {self.y:>5}] connected to: slice={self.get_slice()} @ {self.base_station}'
            f'\t with mobility pattern of {self.mobility_pattern}'
        )
