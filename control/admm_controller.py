"""ADMM-inspired controller for per-base-station slice ratio allocation.

This controller adapts the resource-consensus idea from DRL/RARE-style ADMM
without importing its environment. In this project, each base station solves a
small bounded-simplex allocation over URLLC/eMBB/mMTC and returns the same
action schema as GBDTController.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from control.action_normalizer import _project_to_bounded_simplex, normalize_ratio_actions
from control.controller_schema import (
    ControllerConstraints,
    DEFAULT_ACTION_COLUMNS,
    DEFAULT_PRIORITY_WEIGHTS,
)


@dataclass(slots=True)
class ADMMControllerPreset:
    name: str
    description: str
    risk_gain: float = 0.45
    load_gain: float = 0.30
    latency_gain: float = 0.25
    block_gain: float = 0.15
    fairness_floor: float = 0.05
    move_penalty: float = 0.35
    admm_rho: float = 1.0
    max_iterations: int = 24
    tolerance: float = 1e-4
    scheduling_risk_gain: float = 0.85
    scheduling_latency_gain: float = 0.85
    scheduling_load_gain: float = 0.25
    admission_risk_gain: float = 0.30
    admission_block_gain: float = 0.08
    priority_weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_PRIORITY_WEIGHTS))
    constraints: ControllerConstraints = field(default_factory=ControllerConstraints)


DEFAULT_ADMM_PRESETS = {
    "admm_balanced": ADMMControllerPreset(
        name="admm_balanced",
        description="Balanced ADMM ratio optimizer with conservative admission guard.",
        constraints=ControllerConstraints(
            min_ratio=0.08,
            max_ratio=0.75,
            max_step_change=0.10,
            scheduling_weight_floor=0.60,
            scheduling_weight_ceiling=3.00,
            admission_guard_floor=0.90,
            admission_guard_ceiling=1.35,
            min_ratio_by_slice={"URLLC": 0.15, "eMBB": 0.15, "mMTC": 0.10},
        ),
    ),
    "admm_latency_safe": ADMMControllerPreset(
        name="admm_latency_safe",
        description="ADMM optimizer biased toward latency-sensitive slices.",
        risk_gain=0.40,
        load_gain=0.20,
        latency_gain=0.42,
        block_gain=0.12,
        move_penalty=0.30,
        scheduling_risk_gain=0.95,
        scheduling_latency_gain=1.15,
        admission_risk_gain=0.38,
        priority_weights={"URLLC": 1.55, "eMBB": 0.95, "mMTC": 0.75},
        constraints=ControllerConstraints(
            min_ratio=0.08,
            max_ratio=0.78,
            max_step_change=0.12,
            scheduling_weight_floor=0.60,
            scheduling_weight_ceiling=3.40,
            admission_guard_floor=0.90,
            admission_guard_ceiling=1.45,
            min_ratio_by_slice={"URLLC": 0.20, "eMBB": 0.14, "mMTC": 0.10},
        ),
    ),
    "admm_throughput_fair": ADMMControllerPreset(
        name="admm_throughput_fair",
        description="ADMM optimizer with stronger demand/fairness pressure.",
        risk_gain=0.28,
        load_gain=0.46,
        latency_gain=0.18,
        block_gain=0.18,
        fairness_floor=0.08,
        move_penalty=0.42,
        scheduling_load_gain=0.38,
        admission_risk_gain=0.22,
        priority_weights={"URLLC": 1.25, "eMBB": 1.08, "mMTC": 0.90},
        constraints=ControllerConstraints(
            min_ratio=0.10,
            max_ratio=0.70,
            max_step_change=0.08,
            scheduling_weight_floor=0.65,
            scheduling_weight_ceiling=2.80,
            admission_guard_floor=0.90,
            admission_guard_ceiling=1.25,
            min_ratio_by_slice={"URLLC": 0.15, "eMBB": 0.18, "mMTC": 0.12},
        ),
    ),
}

ADMM_PRESET_ALIASES = {
    "balanced": "admm_balanced",
    "latency_priority": "admm_latency_safe",
    "guarded_ml_optimizer_v1": "admm_balanced",
}


def get_admm_controller_preset(name: str) -> ADMMControllerPreset:
    resolved = ADMM_PRESET_ALIASES.get(name, name)
    if resolved not in DEFAULT_ADMM_PRESETS:
        valid_names = ", ".join(sorted(DEFAULT_ADMM_PRESETS))
        raise ValueError(f"Unknown ADMM controller preset '{name}'. Valid presets: {valid_names}")
    preset = DEFAULT_ADMM_PRESETS[resolved]
    return ADMMControllerPreset(
        name=preset.name,
        description=preset.description,
        risk_gain=preset.risk_gain,
        load_gain=preset.load_gain,
        latency_gain=preset.latency_gain,
        block_gain=preset.block_gain,
        fairness_floor=preset.fairness_floor,
        move_penalty=preset.move_penalty,
        admm_rho=preset.admm_rho,
        max_iterations=preset.max_iterations,
        tolerance=preset.tolerance,
        scheduling_risk_gain=preset.scheduling_risk_gain,
        scheduling_latency_gain=preset.scheduling_latency_gain,
        scheduling_load_gain=preset.scheduling_load_gain,
        admission_risk_gain=preset.admission_risk_gain,
        admission_block_gain=preset.admission_block_gain,
        priority_weights=dict(preset.priority_weights),
        constraints=ControllerConstraints(
            min_ratio=preset.constraints.min_ratio,
            max_ratio=preset.constraints.max_ratio,
            max_step_change=preset.constraints.max_step_change,
            scheduling_weight_floor=preset.constraints.scheduling_weight_floor,
            scheduling_weight_ceiling=preset.constraints.scheduling_weight_ceiling,
            admission_guard_floor=preset.constraints.admission_guard_floor,
            admission_guard_ceiling=preset.constraints.admission_guard_ceiling,
            min_ratio_by_slice=dict(preset.constraints.min_ratio_by_slice),
            max_ratio_by_slice=dict(preset.constraints.max_ratio_by_slice),
        ),
    )


class ADMMRatioController:
    """Convert risk/KPI state into resource actions using ADMM-style consensus."""

    def __init__(
        self,
        preset_name: str = "admm_balanced",
        constraints: ControllerConstraints | None = None,
    ) -> None:
        preset = get_admm_controller_preset(preset_name)
        self.preset_name = preset.name
        self.preset_description = preset.description
        self.constraints = constraints or preset.constraints
        self.priority_weights = preset.priority_weights
        self.risk_gain = preset.risk_gain
        self.load_gain = preset.load_gain
        self.latency_gain = preset.latency_gain
        self.block_gain = preset.block_gain
        self.fairness_floor = preset.fairness_floor
        self.move_penalty = preset.move_penalty
        self.admm_rho = preset.admm_rho
        self.max_iterations = preset.max_iterations
        self.tolerance = preset.tolerance
        self.scheduling_risk_gain = preset.scheduling_risk_gain
        self.scheduling_latency_gain = preset.scheduling_latency_gain
        self.scheduling_load_gain = preset.scheduling_load_gain
        self.admission_risk_gain = preset.admission_risk_gain
        self.admission_block_gain = preset.admission_block_gain

    @staticmethod
    def _series(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
        if column in frame.columns:
            return frame[column].fillna(default).astype(float)
        return pd.Series(default, index=frame.index, dtype=float)

    @staticmethod
    def _normalize_share(series: pd.Series) -> pd.Series:
        filled = series.fillna(0.0).clip(lower=0.0).astype(float)
        total = float(filled.sum())
        if total <= 1e-12:
            return pd.Series([1.0 / max(len(series), 1)] * len(series), index=series.index, dtype=float)
        return filled / total

    @staticmethod
    def _clip_series(series: pd.Series, lower: pd.Series, upper: pd.Series) -> pd.Series:
        clipped = pd.concat([series.astype(float), lower.astype(float)], axis=1).max(axis=1)
        return pd.concat([clipped, upper.astype(float)], axis=1).min(axis=1)

    def _ratio_bounds(self, local: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        min_ratio = pd.Series(self.constraints.min_ratio, index=local.index, dtype=float)
        if self.constraints.min_ratio_by_slice:
            slice_floor = local["slice_name"].map(self.constraints.min_ratio_by_slice)
            min_ratio = pd.concat([min_ratio, slice_floor], axis=1).max(axis=1).fillna(self.constraints.min_ratio)

        max_ratio = pd.Series(self.constraints.max_ratio, index=local.index, dtype=float)
        if self.constraints.max_ratio_by_slice:
            slice_cap = local["slice_name"].map(self.constraints.max_ratio_by_slice)
            max_ratio = pd.concat([max_ratio, slice_cap], axis=1).min(axis=1).fillna(self.constraints.max_ratio)
        max_ratio = pd.concat([min_ratio, max_ratio], axis=1).max(axis=1)

        current = self._normalize_share(local["current_ratio"])
        step = pd.Series(self.constraints.max_step_change, index=local.index, dtype=float)
        lower = (current - step).clip(lower=0.0)
        lower = pd.concat([lower, min_ratio], axis=1).max(axis=1)
        upper = (current + step).clip(upper=1.0)
        upper = pd.concat([upper, max_ratio], axis=1).min(axis=1)
        upper = pd.concat([lower, upper], axis=1).max(axis=1)
        return lower.astype(float), upper.astype(float)

    def _demand_pressure(self, local: pd.DataFrame) -> pd.Series:
        base_capacity = self._series(local, "base_station_capacity", 1.0).replace(0.0, 1.0)
        requested_ratio = (self._series(local, "requested_usage_sum") / base_capacity).clip(0.0, 2.0)
        used_ratio = (self._series(local, "slice_used_diff") / base_capacity).clip(0.0, 1.5)
        load_ratio = self._series(local, "avg_slice_load_ratio").clip(0.0, 1.5)
        request_count = self._series(local, "request_count").clip(lower=0.0)
        if float(request_count.max()) > 0:
            request_count = (request_count / float(request_count.max())).clip(0.0, 1.0)
        return pd.concat([requested_ratio, used_ratio, load_ratio, request_count], axis=1).max(axis=1).clip(0.0, 1.0)

    def _latency_pressure(self, local: pd.DataFrame) -> pd.Series:
        avg_latency = self._series(local, "avg_latency_ms")
        max_avg_latency = self._series(local, "max_avg_latency_ms", 0.0)
        if float(max_avg_latency.max()) <= 0:
            max_avg_latency = avg_latency.where(avg_latency > 0, 1.0)
        latency_ratio = (avg_latency / max_avg_latency.replace(0.0, 1.0)).clip(0.0, 1.5)
        violation_ratio = self._series(local, "latency_violation_ratio").clip(0.0, 1.0)
        return (0.55 * violation_ratio + 0.45 * latency_ratio).clip(0.0, 1.0)

    def _merge_state_and_prediction(self, state_df: pd.DataFrame, prediction_df: pd.DataFrame) -> pd.DataFrame:
        prediction_columns = ["time", "slice_name", "base_station_id"]
        for column in ["sla_violation_action_score", "sla_violation_prob"]:
            if column in prediction_df.columns:
                prediction_columns.append(column)

        merged = state_df.merge(
            prediction_df[prediction_columns].drop_duplicates(["time", "slice_name", "base_station_id"]),
            on=["time", "slice_name", "base_station_id"],
            how="left",
        ).copy()
        if "sla_violation_action_score" in merged.columns:
            merged["sla_risk"] = merged["sla_violation_action_score"].fillna(merged.get("sla_violation_prob", 0.0))
        elif "sla_violation_prob" in merged.columns:
            merged["sla_risk"] = merged["sla_violation_prob"]
        else:
            merged["sla_risk"] = 0.0
        merged["sla_risk"] = merged["sla_risk"].fillna(0.0).clip(0.0, 1.0)

        if {"slice_init_capacity", "base_station_capacity"}.issubset(merged.columns):
            merged["current_ratio"] = (
                merged["slice_init_capacity"].fillna(0.0)
                / merged["base_station_capacity"].replace(0.0, 1.0).fillna(1.0)
            )
        else:
            merged["current_ratio"] = 1.0
        merged["priority_weight"] = merged["slice_name"].map(self.priority_weights).fillna(1.0).astype(float)
        return merged

    def _solve_admm_ratio(self, local: pd.DataFrame) -> tuple[pd.Series, int, float, float]:
        current = self._normalize_share(local["current_ratio"])
        preferred = self._normalize_share(local["preferred_ratio"])
        lower, upper = self._ratio_bounds(local)
        objective_weight = local["objective_weight"].fillna(0.0).clip(lower=0.05).astype(float)
        move_penalty = max(float(self.move_penalty), 1e-6)
        rho = max(float(self.admm_rho), 1e-6)

        z = _project_to_bounded_simplex(preferred, lower, upper)
        x = z.copy()
        u = pd.Series(0.0, index=local.index, dtype=float)
        primal_residual = 0.0
        dual_residual = 0.0
        iterations = 0

        for iteration in range(1, max(int(self.max_iterations), 1) + 1):
            previous_z = z.copy()
            x = (
                objective_weight * preferred
                + move_penalty * current
                + rho * (z - u)
            ) / (objective_weight + move_penalty + rho)
            x = self._clip_series(x, lower, upper)

            z = _project_to_bounded_simplex(x + u, lower, upper)
            u = u + x - z
            primal_residual = float((x - z).abs().sum())
            dual_residual = float(rho * (z - previous_z).abs().sum())
            iterations = iteration
            if max(primal_residual, dual_residual) <= float(self.tolerance):
                break

        return z.astype(float), iterations, primal_residual, dual_residual

    def decide(
        self,
        state_df: pd.DataFrame,
        prediction_df: pd.DataFrame,
        effective_time: int | float | None = None,
    ) -> pd.DataFrame:
        if state_df.empty:
            return pd.DataFrame(columns=DEFAULT_ACTION_COLUMNS)

        merged = self._merge_state_and_prediction(state_df, prediction_df)
        action_rows = []
        for _, group in merged.groupby("base_station_id", sort=False):
            local = group.copy()
            local["demand_pressure"] = self._demand_pressure(local)
            local["latency_pressure"] = self._latency_pressure(local)
            local["block_pressure"] = self._series(local, "block_ratio").clip(0.0, 1.0)
            local["objective_weight"] = (
                local["priority_weight"]
                * (
                    self.risk_gain * local["sla_risk"]
                    + self.load_gain * local["demand_pressure"]
                    + self.latency_gain * local["latency_pressure"]
                    + self.block_gain * local["block_pressure"]
                    + self.fairness_floor
                )
            ).clip(lower=0.05)
            local["preferred_ratio"] = self._normalize_share(local["objective_weight"])

            ratio, iterations, primal_residual, dual_residual = self._solve_admm_ratio(local)
            local["raw_target_ratio"] = ratio.reindex(local.index).astype(float)
            local["scheduling_weight"] = local["priority_weight"] * (
                1.0
                + self.scheduling_risk_gain * local["sla_risk"]
                + self.scheduling_latency_gain * local["latency_pressure"]
                + self.scheduling_load_gain * local["demand_pressure"]
            )
            local["admission_guard_factor"] = 1.0 + (
                self.admission_risk_gain * local["sla_risk"]
                + self.admission_block_gain * local["block_pressure"]
            )
            local["max_step_change"] = self.constraints.max_step_change
            local["admm_iterations"] = iterations
            local["admm_primal_residual"] = primal_residual
            local["admm_dual_residual"] = dual_residual
            local["decision_reason"] = [
                (
                    f"controller=admm, preset={self.preset_name}, "
                    f"risk={risk:.3f}, demand={demand:.3f}, latency={latency:.3f}, "
                    f"block={block:.3f}, preferred={preferred:.3f}, "
                    f"iter={iterations}, primal={primal_residual:.5f}, dual={dual_residual:.5f}"
                )
                for risk, demand, latency, block, preferred in zip(
                    local["sla_risk"].fillna(0.0),
                    local["demand_pressure"].fillna(0.0),
                    local["latency_pressure"].fillna(0.0),
                    local["block_pressure"].fillna(0.0),
                    local["preferred_ratio"].fillna(0.0),
                )
            ]
            action_rows.append(
                local[
                    [
                        "slice_name",
                        "base_station_id",
                        "current_ratio",
                        "raw_target_ratio",
                        "scheduling_weight",
                        "admission_guard_factor",
                        "max_step_change",
                        "admm_iterations",
                        "admm_primal_residual",
                        "admm_dual_residual",
                        "decision_reason",
                    ]
                ]
            )

        action_df = pd.concat(action_rows, ignore_index=True) if action_rows else pd.DataFrame()
        if action_df.empty:
            return pd.DataFrame(columns=DEFAULT_ACTION_COLUMNS)
        action_df.insert(0, "effective_time", effective_time if effective_time is not None else state_df["time"].max())
        action_df = normalize_ratio_actions(action_df, constraints=self.constraints)
        ordered_columns = [column for column in DEFAULT_ACTION_COLUMNS if column in action_df.columns] + [
            column for column in action_df.columns if column not in DEFAULT_ACTION_COLUMNS
        ]
        return action_df[ordered_columns]
