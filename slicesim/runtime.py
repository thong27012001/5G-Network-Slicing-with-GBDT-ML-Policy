from dataclasses import dataclass
from copy import deepcopy
from pathlib import Path
import math
import random
from typing import Any, Dict, List, Optional

import simpy
import yaml

from .BaseStation import BaseStation
from .Client import Client
from .core_simulation import CoreSimulationEngine
from .Coverage import Coverage
from .Distributor import Distributor
from .Slice import Slice
from .Stats import Stats
from .utils import KDTree


STAT_METRIC_NAMES = (
    "connected_clients_ratio",
    "total_bandwidth_usage",
    "avg_slice_load_ratio",
    "avg_slice_client_count",
    "coverage_ratio",
    "block_ratio",
    "handover_ratio",
    "avg_latency_ms",
    "p95_latency_ms",
    "latency_violation_ratio",
)

DEFAULT_LATENCY_PARAMS = {
    "time_unit_ms": 1.0,
    "request_setup_mode": "none",
    "attach_ms": 0.5,
    "auth_ms": 0.5,
    "pdu_session_ms": 0.5,
    "immediate_service_qos_threshold": 2,
    "admission_base_ms": 0.1,
    "admission_per_connected_user_ms": 0.02,
    "admission_per_bs_load_ms": 0.5,
    "core_base_ms": 0.25,
    "core_load_factor_ms": 0.5,
    "edge_base_ms": 0.25,
    "edge_load_factor_ms": 0.5,
    "handover_penalty_ms": 1.0,
}

DEFAULT_BASELINE_POLICY = {
    "scheduling": {
        "share_mode": "equal_share",
        "waiting_time_boost": 1.0,
        "qos_priority_boost": 1.0,
        "max_waiting_ratio": 3.0,
        "immediate_service": {
            "enabled": True,
            "qos_threshold": 2,
        },
    },
    "admission": {
        "policy": "guaranteed_bandwidth",
        "use_bandwidth_guaranteed": True,
        "guaranteed_bw_factor": 1.0,
        "latency_guard_enabled": False,
        "latency_theta": {
            "default": 1.0,
        },
        "predicted_wait_base_cycles": 1.0,
        "predicted_wait_per_user_cycles": 0.15,
        "predicted_wait_load_scale": 1.0,
        "allow_alternate_bs_retry": True,
        "use_bandwidth_max_cap": True,
    },
    "latency": deepcopy(DEFAULT_LATENCY_PARAMS),
    "slices": {},
}


@dataclass
class SimulationContext:
    env: simpy.Environment
    settings: Dict[str, Any]
    slices_info: Dict[str, Any]
    base_stations: List[BaseStation]
    clients: List[Client]
    stats: Stats
    core_simulation: Any | None = None


@dataclass
class SimulationRun:
    context: SimulationContext
    resource_rows: List[Dict[str, Any]]
    stats_series: Dict[str, List[float]]


def validate_config(data: Dict[str, Any]) -> None:
    required_settings = [
        "simulation_time",
        "num_clients",
        "limit_closest_base_stations",
        "statistics_params",
        "plotting_params",
    ]
    for key in required_settings:
        if key not in data.get("settings", {}):
            raise ValueError(f"Missing required setting: {key}")
    if "slices" not in data:
        raise ValueError("Missing 'slices' section in config.")
    if "clients" not in data:
        raise ValueError("Missing 'clients' section in config.")
    if "base_stations" not in data:
        raise ValueError("Missing 'base_stations' section in config.")
    if "mobility_patterns" not in data:
        raise ValueError("Missing 'mobility_patterns' section in config.")


def load_config_file(path: Path) -> Dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as stream:
        data = yaml.load(stream, Loader=yaml.FullLoader)
    if not isinstance(data, dict):
        raise ValueError("Configuration file must define a mapping at the top level.")
    data.setdefault("__meta__", {})["config_dir"] = str(Path(path).resolve().parent)
    return data


def load_config_text(text: str) -> Dict[str, Any]:
    data = yaml.load(text, Loader=yaml.FullLoader)
    if not isinstance(data, dict):
        raise ValueError("Configuration text must define a mapping at the top level.")
    data.setdefault("__meta__", {})["config_dir"] = str(Path.cwd())
    return data


def _deep_merge_dict(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dict(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _load_baseline_file(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        data = yaml.load(stream, Loader=yaml.FullLoader)
    if not isinstance(data, dict):
        raise ValueError("Baseline file must define a mapping at the top level.")
    if "baseline" in data:
        baseline_data = data["baseline"]
        if not isinstance(baseline_data, dict):
            raise ValueError("'baseline' section must be a mapping.")
        return baseline_data
    return data


def resolve_baseline_policy(data: Dict[str, Any]) -> Dict[str, Any]:
    settings = data.setdefault("settings", {})
    config_dir = Path(data.get("__meta__", {}).get("config_dir", Path(__file__).resolve().parent))
    baseline_policy = deepcopy(DEFAULT_BASELINE_POLICY)
    baseline_file = settings.get("baseline_file")

    if baseline_file:
        baseline_path = Path(baseline_file)
        if not baseline_path.is_absolute():
            baseline_path = config_dir / baseline_path
        if not baseline_path.exists():
            raise ValueError(f"Baseline config file not found: {baseline_path}")
        baseline_policy = _deep_merge_dict(baseline_policy, _load_baseline_file(baseline_path))
        settings["baseline_file"] = str(baseline_path)
    else:
        default_baseline_path = config_dir / "baseline.yml"
        if default_baseline_path.exists():
            baseline_policy = _deep_merge_dict(baseline_policy, _load_baseline_file(default_baseline_path))
            settings["baseline_file"] = str(default_baseline_path)

    inline_baseline = data.get("baseline", {})
    if inline_baseline:
        if not isinstance(inline_baseline, dict):
            raise ValueError("Inline 'baseline' configuration must be a mapping.")
        baseline_policy = _deep_merge_dict(baseline_policy, inline_baseline)

    return baseline_policy


def get_dist(name: str) -> Any:
    return {
        "randrange": random.randrange,
        "randint": random.randint,
        "random": random.random,
        "uniform": random.uniform,
        "triangular": random.triangular,
        "beta": random.betavariate,
        "expo": random.expovariate,
        "gamma": random.gammavariate,
        "gauss": random.gauss,
        "lognorm": random.lognormvariate,
        "normal": random.normalvariate,
        "vonmises": random.vonmisesvariate,
        "pareto": random.paretovariate,
        "weibull": random.weibullvariate,
    }.get(name)


def get_random_mobility_pattern(vals, mobility_patterns):
    i = 0
    r = random.random()
    while vals[i] < r:
        i += 1
    return mobility_patterns[i]


def get_random_slice_index(vals):
    i = 0
    r = random.random()
    while vals[i] < r:
        i += 1
    return i


def _build_cumulative_weights(weighted_items: Dict[str, Any]) -> List[float]:
    collected = 0
    weights = []
    for _, item in weighted_items.items():
        collected += item["client_weight"]
        weights.append(collected)
    return weights


def _build_distributor(name: str, config: Dict[str, Any], divide_scale: float = 1) -> Distributor:
    distribution = get_dist(config["distribution"])
    if distribution is None:
        raise ValueError(f"Unsupported distribution '{config['distribution']}' for '{name}'.")
    return Distributor(name, distribution, *config["params"], divide_scale=divide_scale)


_PRB_EXPORT_DEFAULTS: Dict[str, Any] = {
    "enabled": False,
    "output_dir": "artifacts/prb_metrics/<scenario_name>",
    "per_slice": True,
    "per_ue": False,
    "channel_efficiency": 1.0,
    "cell_edge_factor": 0.90,
}


def _resolve_prb_export_config(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Validate the optional `settings.prb_export` block and merge missing keys with defaults.
    NetSim-inspired bandwidth proxy; see docs/prb_proxy_metrics.md."""
    if raw is None:
        return dict(_PRB_EXPORT_DEFAULTS)
    if not isinstance(raw, dict):
        raise ValueError("settings.prb_export must be a mapping when provided.")

    config = dict(_PRB_EXPORT_DEFAULTS)
    config.update(raw)

    if not isinstance(config["enabled"], bool):
        raise ValueError("settings.prb_export.enabled must be a boolean.")
    if not isinstance(config["output_dir"], str) or not config["output_dir"]:
        raise ValueError("settings.prb_export.output_dir must be a non-empty string.")
    if not isinstance(config["per_slice"], bool):
        raise ValueError("settings.prb_export.per_slice must be a boolean.")
    if not isinstance(config["per_ue"], bool):
        raise ValueError("settings.prb_export.per_ue must be a boolean.")
    try:
        config["channel_efficiency"] = float(config["channel_efficiency"])
    except (TypeError, ValueError) as exc:
        raise ValueError("settings.prb_export.channel_efficiency must be a float.") from exc
    if not (0.0 < config["channel_efficiency"] <= 1.0):
        raise ValueError(
            f"settings.prb_export.channel_efficiency must be in (0, 1] (got {config['channel_efficiency']})."
        )
    try:
        config["cell_edge_factor"] = float(config["cell_edge_factor"])
    except (TypeError, ValueError) as exc:
        raise ValueError("settings.prb_export.cell_edge_factor must be a float.") from exc
    if not (0.0 < config["cell_edge_factor"] <= 1.5):
        raise ValueError(
            f"settings.prb_export.cell_edge_factor must be in (0, 1.5] (got {config['cell_edge_factor']})."
        )
    if config["enabled"] and not (config["per_slice"] or config["per_ue"]):
        raise ValueError(
            "settings.prb_export.enabled=true requires at least one of per_slice/per_ue to be true."
        )
    return config


def _sample_point_in_disk(center: tuple[float, float], radius: float) -> tuple[float, float]:
    angle = random.uniform(0.0, 2.0 * math.pi)
    distance = radius * math.sqrt(random.random())
    return center[0] + distance * math.cos(angle), center[1] + distance * math.sin(angle)


def _sample_point_in_flat_hex(center: tuple[float, float], radius: float) -> tuple[float, float]:
    apothem = math.sqrt(3.0) * radius / 2.0
    for _ in range(100):
        dx = random.uniform(-radius, radius)
        dy = random.uniform(-apothem, apothem)
        if math.sqrt(3.0) * abs(dx) + abs(dy) <= math.sqrt(3.0) * radius:
            return center[0] + dx, center[1] + dy
    return center


def _build_client_placement_order(base_stations: List[BaseStation], placement_info: Dict[str, Any]) -> List[int]:
    order = list(range(len(base_stations)))
    if placement_info.get("shuffle", True):
        random.shuffle(order)
    return order


_VALID_MIX_KINDS = {"balanced_hex_cell", "balanced_hex", "balanced_disk", "hotspot", "cell_edge", "out_of_coverage"}


def _validate_mix_block(mix: List[Dict[str, Any]]) -> None:
    if not mix:
        raise ValueError("placement.mix must be a non-empty list when mode='mixed_density'.")
    total = sum(float(item.get("ratio", 0.0)) for item in mix)
    if abs(total - 1.0) > 1e-3:
        raise ValueError(f"placement.mix ratios must sum to 1.0 (got {total:.4f}).")
    for index, item in enumerate(mix):
        kind = item.get("kind")
        if kind not in _VALID_MIX_KINDS:
            raise ValueError(
                f"placement.mix[{index}].kind='{kind}' is invalid. "
                f"Valid kinds: {sorted(_VALID_MIX_KINDS)}."
            )
        if kind == "hotspot":
            clusters = item.get("clusters")
            if not clusters or not isinstance(clusters, list):
                raise ValueError(f"placement.mix[{index}] (hotspot) requires non-empty 'clusters' list.")
            for cluster_idx, point in enumerate(clusters):
                if not isinstance(point, (list, tuple)) or len(point) != 2:
                    raise ValueError(
                        f"placement.mix[{index}].clusters[{cluster_idx}] must be a [x, y] pair (got {point})."
                    )
            if float(item.get("cluster_radius", 0.0)) <= 0.0:
                raise ValueError(f"placement.mix[{index}] (hotspot) requires cluster_radius > 0.")
        elif kind == "cell_edge":
            rng = item.get("radius_factor_range", [0.95, 1.05])
            if not isinstance(rng, (list, tuple)) or len(rng) != 2:
                raise ValueError(f"placement.mix[{index}].radius_factor_range must be [low, high].")
            low, high = float(rng[0]), float(rng[1])
            if not (0.0 < low < high):
                raise ValueError(
                    f"placement.mix[{index}] (cell_edge) requires 0 < low < high (got [{low}, {high}])."
                )
        elif kind == "out_of_coverage":
            if float(item.get("outer_radius_factor", 0.0)) <= 1.0:
                raise ValueError(
                    f"placement.mix[{index}] (out_of_coverage) requires outer_radius_factor > 1.0."
                )


def _build_placement_kinds(num_clients: int, mix: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return a length-N list of mix-item configs, one per client. Counts honor ratios; remainder
    goes to the first item to keep the total exact. The list is shuffled so kind ordering does not
    correlate with client_id (which would skew BS round-robin)."""
    counts = [int(round(num_clients * float(item["ratio"]))) for item in mix]
    diff = num_clients - sum(counts)
    counts[0] += diff
    assignments: List[Dict[str, Any]] = []
    for item, count in zip(mix, counts):
        assignments.extend([item] * max(count, 0))
    random.shuffle(assignments)
    return assignments


def _sample_hotspot_location(clusters: List[List[float]], cluster_radius: float) -> tuple[float, float]:
    cx, cy = random.choice(clusters)
    angle = random.uniform(0.0, 2.0 * math.pi)
    distance = cluster_radius * math.sqrt(random.random())
    return float(cx) + distance * math.cos(angle), float(cy) + distance * math.sin(angle)


def _sample_cell_edge_location(target_bs: BaseStation, factor_range: tuple[float, float]) -> tuple[float, float]:
    factor = random.uniform(factor_range[0], factor_range[1])
    radius = float(target_bs.coverage.radius) * factor
    angle = random.uniform(0.0, 2.0 * math.pi)
    cx, cy = target_bs.coverage.center
    return cx + radius * math.cos(angle), cy + radius * math.sin(angle)


def _sample_out_of_coverage_location(target_bs: BaseStation, outer_factor: float) -> tuple[float, float]:
    factor = random.uniform(outer_factor, outer_factor + 0.10)
    radius = float(target_bs.coverage.radius) * factor
    angle = random.uniform(0.0, 2.0 * math.pi)
    cx, cy = target_bs.coverage.center
    return cx + radius * math.cos(angle), cy + radius * math.sin(angle)


def _dispatch_kind_location(
    client_id: int,
    kind_config: Dict[str, Any],
    base_stations: List[BaseStation],
    placement_order: List[int],
) -> tuple[float, float]:
    kind = kind_config["kind"]
    target_index = placement_order[client_id % len(placement_order)]
    target_bs = base_stations[target_index]
    if kind in {"balanced_hex_cell", "balanced_hex"}:
        radius_factor = float(kind_config.get("radius_factor", 0.62))
        radius = max(float(target_bs.coverage.radius) * radius_factor, 0.0)
        return _sample_point_in_flat_hex(target_bs.coverage.center, radius)
    if kind == "balanced_disk":
        radius_factor = float(kind_config.get("radius_factor", 0.62))
        radius = max(float(target_bs.coverage.radius) * radius_factor, 0.0)
        return _sample_point_in_disk(target_bs.coverage.center, radius)
    if kind == "hotspot":
        return _sample_hotspot_location(
            kind_config["clusters"],
            float(kind_config.get("cluster_radius", 50.0)),
        )
    if kind == "cell_edge":
        rng = kind_config.get("radius_factor_range", [0.95, 1.05])
        return _sample_cell_edge_location(target_bs, (float(rng[0]), float(rng[1])))
    if kind == "out_of_coverage":
        return _sample_out_of_coverage_location(
            target_bs,
            float(kind_config.get("outer_radius_factor", 1.20)),
        )
    raise ValueError(f"Unknown placement kind '{kind}'.")


def _generate_client_location(
    client_id: int,
    clients_info: Dict[str, Any],
    base_stations: List[BaseStation],
    placement_order: List[int],
    location_x_dist: Distributor | None,
    location_y_dist: Distributor | None,
    placement_kinds: Optional[List[Dict[str, Any]]] = None,
) -> tuple[float, float]:
    placement_info = clients_info.get("placement", {}) or {}
    mode = str(placement_info.get("mode", "distribution"))

    if mode == "mixed_density":
        if not base_stations:
            raise ValueError("Mixed-density placement requires at least one base station.")
        if placement_kinds is None:
            raise ValueError("Mixed-density placement requires precomputed placement_kinds.")
        return _dispatch_kind_location(
            client_id,
            placement_kinds[client_id],
            base_stations,
            placement_order,
        )

    if mode in {"balanced_hex_cell", "balanced_hex", "balanced_by_bs", "balanced_disk"}:
        if not base_stations:
            raise ValueError("Balanced client placement requires at least one base station.")
        target_index = placement_order[client_id % len(placement_order)]
        target_bs = base_stations[target_index]
        radius_factor = float(placement_info.get("radius_factor", 0.62))
        radius = max(float(target_bs.coverage.radius) * radius_factor, 0.0)
        center = target_bs.coverage.center
        if mode in {"balanced_hex_cell", "balanced_hex"}:
            return _sample_point_in_flat_hex(center, radius)
        return _sample_point_in_disk(center, radius)

    if location_x_dist is None or location_y_dist is None:
        raise ValueError("clients.location is required when clients.placement.mode is not balanced.")
    return location_x_dist.generate(), location_y_dist.generate()


def build_simulation_context(data: Dict[str, Any], seed: Optional[int] = None) -> SimulationContext:
    validate_config(data)
    random.seed(seed)

    env = simpy.Environment()
    settings = data["settings"]
    baseline_policy = resolve_baseline_policy(data)
    settings["baseline_policy"] = baseline_policy
    settings["latency_params"] = {
        **DEFAULT_LATENCY_PARAMS,
        **baseline_policy.get("latency", {}),
        **settings.get("latency_params", {}),
    }
    core_simulation = CoreSimulationEngine(
        baseline_policy=baseline_policy,
        latency_params=settings["latency_params"],
    )
    slices_info = data["slices"]
    num_clients = settings["num_clients"]
    mobility_patterns_info = data["mobility_patterns"]
    base_stations_info = data["base_stations"]
    clients_info = data["clients"]

    slice_weights = _build_cumulative_weights(slices_info)
    mobility_weights = _build_cumulative_weights(mobility_patterns_info)

    mobility_patterns = []
    for name, pattern_info in mobility_patterns_info.items():
        mobility_patterns.append(_build_distributor(name, pattern_info))

    usage_patterns = {}
    for name, slice_info in slices_info.items():
        usage_patterns[name] = _build_distributor(name, slice_info["usage_pattern"])

    base_stations = []
    for base_station_id, base_station_info in enumerate(base_stations_info):
        slices = []
        ratios = base_station_info["ratios"]
        capacity = base_station_info["capacity_bandwidth"]
        for name, slice_info in slices_info.items():
            if name not in ratios:
                raise ValueError(
                    f"Base station {base_station_id} is missing ratio configuration for slice '{name}'."
                )
            slice_capacity = capacity * ratios[name]
            network_slice = Slice(
                name,
                ratios[name],
                0,
                slice_info["client_weight"],
                slice_info["delay_tolerance"],
                slice_info["qos_class"],
                slice_info["bandwidth_guaranteed"],
                slice_info["bandwidth_max"],
                slice_capacity,
                usage_patterns[name],
                baseline_policy=baseline_policy,
            )
            network_slice.capacity = simpy.Container(
                env,
                init=slice_capacity,
                capacity=slice_capacity,
            )
            slices.append(network_slice)

        base_station = BaseStation(
            base_station_id,
            Coverage(
                (base_station_info["x"], base_station_info["y"]),
                base_station_info["coverage"],
            ),
            capacity,
            slices,
        )
        base_stations.append(base_station)

    usage_frequency = clients_info["usage_frequency"]
    usage_freq_pattern = _build_distributor(
        "usage_frequency",
        usage_frequency,
        divide_scale=usage_frequency["divide_scale"],
    )

    x_vals = settings["statistics_params"]["x"]
    y_vals = settings["statistics_params"]["y"]

    # Validate + populate defaults for prb_export. NetSim-inspired bandwidth proxy; see
    # docs/prb_proxy_metrics.md.
    prb_export = _resolve_prb_export_config(settings.get("prb_export"))
    settings["prb_export"] = prb_export

    stats = Stats(
        env,
        base_stations,
        None,
        ((x_vals["min"], x_vals["max"]), (y_vals["min"], y_vals["max"])),
        prb_config=prb_export,
    )

    clients = []
    location_x_dist = None
    location_y_dist = None
    if "location" in clients_info:
        location_x_dist = _build_distributor("client_location_x", clients_info["location"]["x"])
        location_y_dist = _build_distributor("client_location_y", clients_info["location"]["y"])
    placement_info = clients_info.get("placement", {}) or {}
    placement_order = _build_client_placement_order(base_stations, placement_info)

    placement_kinds: Optional[List[Dict[str, Any]]] = None
    if str(placement_info.get("mode", "distribution")) == "mixed_density":
        mix = placement_info.get("mix") or []
        _validate_mix_block(mix)
        placement_kinds = _build_placement_kinds(num_clients, mix)

    for client_id in range(num_clients):
        client_x, client_y = _generate_client_location(
            client_id,
            clients_info,
            base_stations,
            placement_order,
            location_x_dist,
            location_y_dist,
            placement_kinds=placement_kinds,
        )
        client = Client(
            client_id,
            env,
            client_x,
            client_y,
            get_random_mobility_pattern(mobility_weights, mobility_patterns),
            usage_freq_pattern.generate_scaled(),
            get_random_slice_index(slice_weights),
            stats,
            latency_params=settings["latency_params"],
            baseline_policy=baseline_policy,
            core_simulation=core_simulation,
        )
        clients.append(client)

    KDTree.last_run_time = None
    KDTree.limit = settings["limit_closest_base_stations"]
    KDTree.run(clients, base_stations, 0)
    stats.clients = clients

    return SimulationContext(
        env=env,
        settings=settings,
        slices_info=slices_info,
        base_stations=base_stations,
        clients=clients,
        stats=stats,
        core_simulation=core_simulation,
    )


class ResourceTracker:
    def __init__(
        self,
        env: simpy.Environment,
        base_stations: List[BaseStation],
        sample_interval: float = 1.0,
        start_offset: float = 0.25,
    ) -> None:
        if sample_interval <= 0:
            raise ValueError("sample_interval must be greater than 0.")
        self.env = env
        self.base_stations = base_stations
        self.sample_interval = sample_interval
        self.start_offset = start_offset
        self.samples: List[Dict[str, Any]] = []

    def collect(self):
        yield self.env.timeout(self.start_offset)
        while True:
            self.samples.extend(self.snapshot_rows())
            yield self.env.timeout(self.sample_interval)

    def snapshot_rows(self) -> List[Dict[str, Any]]:
        rows = []
        snapshot_time = float(self.env.now)
        for base_station in self.base_stations:
            total_used_bandwidth = sum(
                network_slice.capacity.capacity - network_slice.capacity.level
                for network_slice in base_station.slices
            )
            total_connected_users = sum(network_slice.connected_users for network_slice in base_station.slices)

            for network_slice in base_station.slices:
                used_bandwidth = network_slice.capacity.capacity - network_slice.capacity.level
                rows.append(
                    {
                        "time": snapshot_time,
                        "bs_id": base_station.pk,
                        "bs_x": base_station.coverage.center[0],
                        "bs_y": base_station.coverage.center[1],
                        "bs_radius": base_station.coverage.radius,
                        "bs_capacity": base_station.capacity_bandwidth,
                        "bs_total_used_bandwidth": total_used_bandwidth,
                        "bs_total_connected_users": total_connected_users,
                        "slice_name": network_slice.name,
                        "configured_ratio": network_slice.ratio,
                        "reserved_capacity": network_slice.init_capacity,
                        "reserved_ratio_of_bs_capacity": (
                            network_slice.init_capacity / base_station.capacity_bandwidth
                            if base_station.capacity_bandwidth
                            else 0
                        ),
                        "used_bandwidth": used_bandwidth,
                        "used_ratio_of_bs_capacity": (
                            used_bandwidth / base_station.capacity_bandwidth
                            if base_station.capacity_bandwidth
                            else 0
                        ),
                        "used_ratio_of_bs_usage": (
                            used_bandwidth / total_used_bandwidth if total_used_bandwidth else 0
                        ),
                        "connected_users": network_slice.connected_users,
                        "connected_user_ratio": (
                            network_slice.connected_users / total_connected_users
                            if total_connected_users
                            else 0
                        ),
                        "bandwidth_guaranteed": network_slice.bandwidth_guaranteed,
                        "bandwidth_max": network_slice.bandwidth_max,
                    }
                )
        return rows


def stats_to_dict(stats: Stats) -> Dict[str, List[float]]:
    return {name: list(values) for name, values in zip(STAT_METRIC_NAMES, stats.get_stats())}


def run_simulation(
    data: Dict[str, Any],
    seed: Optional[int] = None,
    sample_interval: float = 1.0,
) -> SimulationRun:
    context = build_simulation_context(data, seed=seed)
    tracker = ResourceTracker(context.env, context.base_stations, sample_interval=sample_interval)

    context.env.process(context.stats.collect())
    context.env.process(tracker.collect())
    context.env.run(until=int(context.settings["simulation_time"]))

    return SimulationRun(
        context=context,
        resource_rows=tracker.samples,
        stats_series=stats_to_dict(context.stats),
    )
