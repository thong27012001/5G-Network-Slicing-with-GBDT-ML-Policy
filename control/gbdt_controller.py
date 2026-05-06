"""Risk-aware controller that converts GBDT predictions into policy actions."""

from __future__ import annotations

import pandas as pd

try:
    import cvxpy as cp
except ImportError:  # pragma: no cover - optional optimization dependency.
    cp = None

from control.action_normalizer import _project_to_bounded_simplex, normalize_ratio_actions
from control.controller_schema import (
    ControllerConstraints,
    DEFAULT_ACTION_COLUMNS,
    get_controller_preset,
)


class GBDTController:
    """Translate predicted SLA risk into ratio, scheduling, and admission actions."""

    def __init__(
        self,
        preset_name: str = "balanced",
        constraints: ControllerConstraints | None = None,
        priority_weights: dict[str, float] | None = None,
        alpha_risk: float | None = None,
        beta_load: float | None = None,
        gamma_latency: float | None = None,
        delta_priority: float | None = None,
        scheduling_risk_gain: float | None = None,
        scheduling_latency_gain: float | None = None,
        scheduling_load_gain: float | None = None,
        admission_risk_gain: float | None = None,
        admission_block_gain: float | None = None,
        risk_probability_ceiling: float | None = None,
        admission_hysteresis_high_threshold: float | None = None,
        admission_hysteresis_low_threshold: float | None = None,
        admission_hysteresis_windows: int | None = None,
        admission_hysteresis_warmup_factor: float | None = None,
        urllc_first_service_gain: float | None = None,
        urllc_scheduling_bonus: float | None = None,
        urllc_admission_guard_bonus: float | None = None,
        non_urllc_scheduling_backoff: float | None = None,
        non_urllc_admission_guard_bonus: float | None = None,
        slice_ratio_biases: dict[str, float] | None = None,
        action_optimizer_enabled: bool | None = None,
        optimizer_current_anchor: float | None = None,
        optimizer_demand_gain: float | None = None,
        optimizer_risk_gain: float | None = None,
        optimizer_move_penalty: float | None = None,
        optimizer_prior_gain: float | None = None,
        optimizer_prior_penalty: float | None = None,
        optimizer_starvation_floor: float | None = None,
        optimizer_ratio_prior_by_slice: dict[str, float] | None = None,
        optimization_qp_enabled: bool | None = None,
        qp_mu: float | None = None,
        qp_load_gain: float | None = None,
        qp_latency_gain: float | None = None,
        qp_min_objective_weight: float | None = None,
        dynamic_borrow_enabled: bool | None = None,
        borrow_intensity: float | None = None,
        borrow_load_threshold: float | None = None,
        borrow_risk_threshold: float | None = None,
        adaptive_step_enabled: bool | None = None,
        adaptive_step_kappa: float | None = None,
        adaptive_step_ceiling: float | None = None,
    ) -> None:
        preset = get_controller_preset(preset_name)
        self.preset_name = preset.name
        self.preset_description = preset.description
        self.constraints = constraints or preset.constraints
        self.priority_weights = priority_weights or preset.priority_weights
        self.alpha_risk = preset.alpha_risk if alpha_risk is None else alpha_risk
        self.beta_load = preset.beta_load if beta_load is None else beta_load
        self.gamma_latency = preset.gamma_latency if gamma_latency is None else gamma_latency
        self.delta_priority = preset.delta_priority if delta_priority is None else delta_priority
        self.scheduling_risk_gain = (
            preset.scheduling_risk_gain if scheduling_risk_gain is None else scheduling_risk_gain
        )
        self.scheduling_latency_gain = (
            preset.scheduling_latency_gain if scheduling_latency_gain is None else scheduling_latency_gain
        )
        self.scheduling_load_gain = preset.scheduling_load_gain if scheduling_load_gain is None else scheduling_load_gain
        self.admission_risk_gain = preset.admission_risk_gain if admission_risk_gain is None else admission_risk_gain
        self.admission_block_gain = preset.admission_block_gain if admission_block_gain is None else admission_block_gain
        self.risk_probability_ceiling = (
            preset.risk_probability_ceiling if risk_probability_ceiling is None else risk_probability_ceiling
        )
        self.admission_hysteresis_high_threshold = (
            preset.admission_hysteresis_high_threshold
            if admission_hysteresis_high_threshold is None
            else admission_hysteresis_high_threshold
        )
        self.admission_hysteresis_low_threshold = (
            preset.admission_hysteresis_low_threshold
            if admission_hysteresis_low_threshold is None
            else admission_hysteresis_low_threshold
        )
        self.admission_hysteresis_windows = (
            preset.admission_hysteresis_windows
            if admission_hysteresis_windows is None
            else admission_hysteresis_windows
        )
        self.admission_hysteresis_warmup_factor = (
            preset.admission_hysteresis_warmup_factor
            if admission_hysteresis_warmup_factor is None
            else admission_hysteresis_warmup_factor
        )
        self._admission_risk_streaks: dict[tuple[str, str], int] = {}
        self.urllc_first_service_gain = (
            preset.urllc_first_service_gain if urllc_first_service_gain is None else urllc_first_service_gain
        )
        self.urllc_scheduling_bonus = (
            preset.urllc_scheduling_bonus if urllc_scheduling_bonus is None else urllc_scheduling_bonus
        )
        self.urllc_admission_guard_bonus = (
            preset.urllc_admission_guard_bonus
            if urllc_admission_guard_bonus is None
            else urllc_admission_guard_bonus
        )
        self.non_urllc_scheduling_backoff = (
            preset.non_urllc_scheduling_backoff
            if non_urllc_scheduling_backoff is None
            else non_urllc_scheduling_backoff
        )
        self.non_urllc_admission_guard_bonus = (
            preset.non_urllc_admission_guard_bonus
            if non_urllc_admission_guard_bonus is None
            else non_urllc_admission_guard_bonus
        )
        self.slice_ratio_biases = dict(preset.slice_ratio_biases if slice_ratio_biases is None else slice_ratio_biases)
        self.action_optimizer_enabled = (
            preset.action_optimizer_enabled if action_optimizer_enabled is None else action_optimizer_enabled
        )
        self.optimizer_current_anchor = (
            preset.optimizer_current_anchor if optimizer_current_anchor is None else optimizer_current_anchor
        )
        self.optimizer_demand_gain = preset.optimizer_demand_gain if optimizer_demand_gain is None else optimizer_demand_gain
        self.optimizer_risk_gain = preset.optimizer_risk_gain if optimizer_risk_gain is None else optimizer_risk_gain
        self.optimizer_move_penalty = (
            preset.optimizer_move_penalty if optimizer_move_penalty is None else optimizer_move_penalty
        )
        self.optimizer_prior_gain = preset.optimizer_prior_gain if optimizer_prior_gain is None else optimizer_prior_gain
        self.optimizer_prior_penalty = (
            preset.optimizer_prior_penalty if optimizer_prior_penalty is None else optimizer_prior_penalty
        )
        self.optimizer_starvation_floor = (
            preset.optimizer_starvation_floor if optimizer_starvation_floor is None else optimizer_starvation_floor
        )
        self.optimizer_ratio_prior_by_slice = dict(
            preset.optimizer_ratio_prior_by_slice
            if optimizer_ratio_prior_by_slice is None
            else optimizer_ratio_prior_by_slice
        )
        self.optimization_qp_enabled = (
            preset.optimization_qp_enabled if optimization_qp_enabled is None else optimization_qp_enabled
        )
        self.qp_mu = preset.qp_mu if qp_mu is None else qp_mu
        self.qp_load_gain = preset.qp_load_gain if qp_load_gain is None else qp_load_gain
        self.qp_latency_gain = preset.qp_latency_gain if qp_latency_gain is None else qp_latency_gain
        self.qp_min_objective_weight = (
            preset.qp_min_objective_weight if qp_min_objective_weight is None else qp_min_objective_weight
        )
        self.dynamic_borrow_enabled = (
            preset.dynamic_borrow_enabled if dynamic_borrow_enabled is None else dynamic_borrow_enabled
        )
        self.borrow_intensity = preset.borrow_intensity if borrow_intensity is None else borrow_intensity
        self.borrow_load_threshold = (
            preset.borrow_load_threshold if borrow_load_threshold is None else borrow_load_threshold
        )
        self.borrow_risk_threshold = (
            preset.borrow_risk_threshold if borrow_risk_threshold is None else borrow_risk_threshold
        )
        self.adaptive_step_enabled = (
            preset.adaptive_step_enabled if adaptive_step_enabled is None else adaptive_step_enabled
        )
        self.adaptive_step_kappa = preset.adaptive_step_kappa if adaptive_step_kappa is None else adaptive_step_kappa
        self.adaptive_step_ceiling = (
            preset.adaptive_step_ceiling if adaptive_step_ceiling is None else adaptive_step_ceiling
        )
        self._previous_risk_by_key: dict[tuple[str, str], float] = {}

    @staticmethod
    def _normalize_for_local_pressure(series: pd.Series) -> pd.Series:
        filled = series.fillna(0.0).clip(lower=0.0)
        peak = float(filled.max())
        if peak <= 0:
            return pd.Series([0.0] * len(series), index=series.index, dtype=float)
        return (filled / peak).clip(lower=0.0, upper=1.0)

    @staticmethod
    def _normalize_share(series: pd.Series) -> pd.Series:
        filled = series.fillna(0.0).clip(lower=0.0).astype(float)
        total = float(filled.sum())
        if total <= 1e-12:
            return pd.Series([1.0 / max(len(series), 1)] * len(series), index=series.index, dtype=float)
        return filled / total

    def _score_ratio_candidate(
        self,
        ratio: pd.Series,
        current_share: pd.Series,
        demand_share: pd.Series,
        risk_share: pd.Series,
        prior_share: pd.Series,
    ) -> float:
        ratio = self._normalize_share(ratio)
        demand_gap = ((demand_share - ratio).clip(lower=0.0) * demand_share).sum()
        risk_gap = ((risk_share - ratio).clip(lower=0.0) * risk_share).sum()
        move = (ratio - current_share).abs().sum()
        prior_move = (ratio - prior_share).abs().sum()
        starvation_floor = min(max(float(self.optimizer_starvation_floor), 0.0), 1.0)
        starvation = float(((demand_share > starvation_floor) & (ratio < starvation_floor)).sum())
        concentration = max(float(ratio.max()) - float(self.constraints.max_ratio), 0.0)
        return float(
            self.optimizer_demand_gain * demand_gap
            + self.optimizer_risk_gain * risk_gap
            + self.optimizer_move_penalty * move
            + self.optimizer_prior_penalty * prior_move
            + 0.25 * starvation
            + 0.50 * concentration
        )

    def _ratio_bounds(self, local: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        min_ratio = pd.Series(self.constraints.min_ratio, index=local.index, dtype=float)
        if self.constraints.min_ratio_by_slice:
            slice_min_ratio = local["slice_name"].map(self.constraints.min_ratio_by_slice)
            min_ratio = pd.concat([min_ratio, slice_min_ratio], axis=1).max(axis=1).fillna(self.constraints.min_ratio)

        max_ratio = pd.Series(self.constraints.max_ratio, index=local.index, dtype=float)
        if self.constraints.max_ratio_by_slice:
            slice_max_ratio = local["slice_name"].map(self.constraints.max_ratio_by_slice)
            max_ratio = pd.concat([max_ratio, slice_max_ratio], axis=1).min(axis=1).fillna(self.constraints.max_ratio)
        max_ratio = pd.concat([min_ratio, max_ratio], axis=1).max(axis=1)

        current = local["current_ratio"].astype(float).fillna(1.0 / max(len(local), 1))
        if "max_step_change" in local.columns:
            step_change = local["max_step_change"].fillna(self.constraints.max_step_change).clip(lower=0.0)
        else:
            step_change = pd.Series(self.constraints.max_step_change, index=local.index, dtype=float)
        lower = (current - step_change).clip(lower=min_ratio)
        upper = (current + step_change).clip(upper=max_ratio)
        upper = pd.concat([lower, upper], axis=1).max(axis=1)
        return lower.astype(float), upper.astype(float)

    def _risk_delta_signal(self, frame: pd.DataFrame) -> pd.Series:
        deltas = []
        for row in frame[["base_station_id", "slice_name", "sla_violation_prob"]].itertuples(index=False):
            key = (str(row.base_station_id), str(row.slice_name))
            risk = float(row.sla_violation_prob or 0.0)
            previous = self._previous_risk_by_key.get(key, risk)
            deltas.append(abs(risk - previous))
            self._previous_risk_by_key[key] = risk
        return pd.Series(deltas, index=frame.index, dtype=float).clip(0.0, 1.0)

    def _adaptive_step_change(self, risk_delta: pd.Series) -> pd.Series:
        base_step = float(self.constraints.max_step_change)
        if not self.adaptive_step_enabled:
            return pd.Series(base_step, index=risk_delta.index, dtype=float)

        step = base_step * (1.0 + max(float(self.adaptive_step_kappa), 0.0) * risk_delta.fillna(0.0).clip(0.0, 1.0))
        ceiling = self.adaptive_step_ceiling
        if ceiling is not None:
            step = step.clip(upper=max(float(ceiling), base_step))
        return step.clip(lower=base_step)

    def _bs_relative_demand_ratio(self, local: pd.DataFrame) -> pd.Series:
        base_capacity = local["base_station_capacity"].replace(0, 1).astype(float)
        requested_ratio = (local["requested_usage_sum"].fillna(0.0) / base_capacity).clip(0.0, 2.0)
        used_ratio = (local["slice_used_diff"].fillna(0.0) / base_capacity).clip(0.0, 1.5)
        current_ratio = local["current_ratio"].fillna(0.0).clip(0.0, 1.0)
        load_ratio = (local["avg_slice_load_ratio"].fillna(0.0) * current_ratio).clip(0.0, 1.5)
        return pd.concat([requested_ratio, used_ratio, load_ratio], axis=1).max(axis=1).astype(float)

    def _solve_qp_ratio(self, local: pd.DataFrame) -> tuple[pd.Series, str, float]:
        current = self._normalize_share(local["current_ratio"])
        lower, upper = self._ratio_bounds(local)
        risk = local["sla_violation_prob"].fillna(0.0).clip(0.0, 1.0).astype(float)
        load = self._bs_relative_demand_ratio(local).clip(0.0, 1.0)
        latency = local["latency_pressure"].fillna(0.0).clip(0.0, 1.0).astype(float)
        priority = local["priority_weight"].fillna(1.0).clip(lower=0.1).astype(float)
        objective_weight = (
            priority
            * (
                risk
                + float(self.qp_load_gain) * load
                + float(self.qp_latency_gain) * latency
            )
        ).clip(lower=float(self.qp_min_objective_weight))
        mu = max(float(self.qp_mu), 1e-6)

        if cp is not None:
            rho = cp.Variable(len(local))
            rho_max = upper.to_numpy(dtype=float)
            rho_prev = current.to_numpy(dtype=float)
            weights = objective_weight.to_numpy(dtype=float)
            constraints = [
                cp.sum(rho) == 1.0,
                rho >= lower.to_numpy(dtype=float),
                rho <= upper.to_numpy(dtype=float),
            ]
            objective = cp.Minimize(
                cp.sum(cp.multiply(weights, cp.square(rho_max - rho)))
                + mu * cp.sum_squares(rho - rho_prev)
            )
            problem = cp.Problem(objective, constraints)
            try:
                problem.solve(solver=cp.OSQP, warm_start=True, eps_abs=1e-5, eps_rel=1e-5, max_iter=10000, verbose=False)
                if rho.value is not None and problem.status in {"optimal", "optimal_inaccurate"}:
                    result = pd.Series(rho.value, index=local.index, dtype=float)
                    result = _project_to_bounded_simplex(result, lower, upper)
                    return result, f"qp_osqp:{problem.status}", float(problem.value or 0.0)
            except Exception:
                pass

        # Closed-form unconstrained solution, then bounded-simplex projection.
        preferred = (objective_weight * upper + mu * current) / (objective_weight + mu)
        result = _project_to_bounded_simplex(preferred, lower, upper)
        proxy_value = float((objective_weight * (upper - result).pow(2) + mu * (result - current).pow(2)).sum())
        return result, "qp_fallback_projected", proxy_value

    def _apply_dynamic_capacity_borrow(self, local: pd.DataFrame, ratio: pd.Series) -> tuple[pd.Series, float]:
        if len(local) <= 1:
            return ratio, 0.0

        lower, upper = self._ratio_bounds(local)
        demand = self._bs_relative_demand_ratio(local).clip(0.0, 1.0)
        risk = local["sla_violation_prob"].fillna(0.0).clip(0.0, 1.0)
        latency = local["latency_pressure"].fillna(0.0).clip(0.0, 1.0)
        priority = local["priority_weight"].fillna(1.0).clip(lower=0.1)
        headroom = (ratio - demand).clip(lower=0.0)
        stress = (demand - ratio).clip(lower=0.0) * (0.50 + risk + latency + 0.15 * priority)
        receiver_mask = (demand >= float(self.borrow_load_threshold)) | (risk >= float(self.borrow_risk_threshold))
        stress = stress.where(receiver_mask, 0.0)

        headroom_sum = float(headroom.sum())
        stress_sum = float(stress.sum())
        if headroom_sum <= 1e-12 or stress_sum <= 1e-12:
            return ratio, 0.0

        receiver_room = (upper - ratio).clip(lower=0.0)
        borrow_pool = min(
            headroom_sum * min(max(float(self.borrow_intensity), 0.0), 1.0),
            float(receiver_room[stress > 0].sum()),
        )
        if borrow_pool <= 1e-12:
            return ratio, 0.0

        updated = ratio.copy()
        updated = updated - borrow_pool * headroom / headroom_sum
        updated = updated + borrow_pool * stress / stress_sum
        updated = _project_to_bounded_simplex(updated, lower, upper)
        return updated, borrow_pool

    def _optimize_local_ratios_qp(self, local: pd.DataFrame) -> pd.DataFrame:
        local = local.copy()
        if len(local) <= 1:
            local["raw_target_ratio"] = self._normalize_share(local["current_ratio"])
            local["optimizer_choice"] = "qp_single_slice"
            local["optimizer_score"] = 0.0
            local["borrow_pool"] = 0.0
            return local

        ratio, solver_name, objective_value = self._solve_qp_ratio(local)
        borrow_pool = 0.0
        if self.dynamic_borrow_enabled:
            ratio, borrow_pool = self._apply_dynamic_capacity_borrow(local, ratio)
            solver_name = f"{solver_name}+borrow" if borrow_pool > 0 else f"{solver_name}+borrow_idle"

        local["raw_target_ratio"] = ratio.reindex(local.index).astype(float)
        local["optimizer_choice"] = solver_name
        local["optimizer_score"] = objective_value
        local["borrow_pool"] = borrow_pool
        return local

    def _optimize_local_ratios(self, local: pd.DataFrame) -> pd.DataFrame:
        local = local.copy()
        if len(local) <= 1:
            local["optimizer_choice"] = "single_slice"
            local["optimizer_score"] = 0.0
            return local

        current_share = self._normalize_share(local["current_ratio"])
        prior_values = local["slice_name"].map(self.optimizer_ratio_prior_by_slice)
        if prior_values.notna().any():
            prior_share = self._normalize_share(prior_values.fillna(local["current_ratio"]))
        else:
            prior_share = current_share
        demand_signal = (
            local["requested_usage_sum"].fillna(0.0).clip(lower=0.0)
            + local["requested_usage_mean"].fillna(0.0).clip(lower=0.0) * local["request_count"].fillna(0.0).clip(lower=0.0)
            + local["connected_events"].fillna(0.0).clip(lower=0.0)
        )
        if float(demand_signal.sum()) <= 1e-12:
            demand_signal = local["avg_slice_load_ratio"].fillna(0.0).clip(lower=0.0)
        demand_share = self._normalize_share(demand_signal)

        risk_signal = (
            local["sla_violation_prob"].fillna(0.0).clip(0.0, 1.0) * local["priority_weight"].fillna(1.0)
            + local["latency_pressure"].fillna(0.0).clip(0.0, 1.0) * local["priority_weight"].fillna(1.0)
            + local["first_service_pressure"].fillna(0.0).clip(0.0, 1.0)
            + 0.25 * local["avg_slice_load_ratio"].fillna(0.0).clip(0.0, 1.0)
        )
        risk_share = self._normalize_share(risk_signal)
        raw_share = self._normalize_share(local["raw_target_ratio"])

        anchor = min(max(float(self.optimizer_current_anchor), 0.0), 1.0)
        demand_gain = min(max(float(self.optimizer_demand_gain), 0.0), 1.0)
        risk_gain = min(max(float(self.optimizer_risk_gain), 0.0), 1.0)
        prior_gain = min(max(float(self.optimizer_prior_gain), 0.0), 1.0)
        total = max(anchor + demand_gain + risk_gain + prior_gain, 1e-12)
        guarded_blend = (
            anchor / total * current_share
            + demand_gain / total * demand_share
            + risk_gain / total * risk_share
            + prior_gain / total * prior_share
        )

        candidates = {
            "current_anchor": current_share,
            "baseline_prior": prior_share,
            "risk_target": raw_share,
            "demand_balanced": self._normalize_share(0.70 * current_share + 0.30 * demand_share),
            "guarded_blend": self._normalize_share(guarded_blend),
            "risk_boosted": self._normalize_share(
                0.45 * current_share + 0.25 * prior_share + 0.15 * demand_share + 0.15 * risk_share
            ),
        }
        scored = {
            name: self._score_ratio_candidate(candidate, current_share, demand_share, risk_share, prior_share)
            for name, candidate in candidates.items()
        }
        best_name = min(scored, key=scored.get)
        local["raw_target_ratio"] = candidates[best_name].reindex(local.index).astype(float)
        local["optimizer_choice"] = best_name
        local["optimizer_score"] = scored[best_name]
        return local

    def _admission_risk_signal(self, frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        required_windows = max(int(self.admission_hysteresis_windows), 1)
        if required_windows <= 1:
            risk = frame["sla_violation_prob"].fillna(0.0)
            return risk, pd.Series([1] * len(frame), index=frame.index, dtype=int)

        high_threshold = min(max(float(self.admission_hysteresis_high_threshold), 0.0), 1.0)
        low_threshold = min(max(float(self.admission_hysteresis_low_threshold), 0.0), high_threshold)
        warmup_factor = min(max(float(self.admission_hysteresis_warmup_factor), 0.0), 1.0)

        signals = []
        streaks = []
        for row in frame[["base_station_id", "slice_name", "sla_violation_prob"]].itertuples(index=False):
            key = (str(row.base_station_id), str(row.slice_name))
            risk = float(row.sla_violation_prob or 0.0)
            streak = int(self._admission_risk_streaks.get(key, 0))
            if risk >= high_threshold:
                streak += 1
            elif risk <= low_threshold:
                streak = 0

            self._admission_risk_streaks[key] = streak
            streaks.append(streak)
            signals.append(risk if streak >= required_windows else risk * warmup_factor)

        return (
            pd.Series(signals, index=frame.index, dtype=float),
            pd.Series(streaks, index=frame.index, dtype=int),
        )

    def decide(
        self,
        state_df: pd.DataFrame,
        prediction_df: pd.DataFrame,
        effective_time: int | float | None = None,
    ) -> pd.DataFrame:
        prediction_columns = ["time", "slice_name", "base_station_id", "sla_violation_prob"]
        for optional_column in ["sla_violation_action_score", "sla_violation_threshold"]:
            if optional_column in prediction_df.columns:
                prediction_columns.append(optional_column)
        merged = state_df.merge(
            prediction_df[prediction_columns],
            on=["time", "slice_name", "base_station_id"],
            how="left",
        ).copy()
        if "sla_violation_action_score" in merged.columns:
            merged["raw_sla_violation_prob"] = merged["sla_violation_prob"].fillna(0.0).clip(0.0, 1.0)
            merged["sla_violation_prob"] = merged["sla_violation_action_score"].fillna(
                merged["raw_sla_violation_prob"]
            )
        risk_ceiling = min(max(float(self.risk_probability_ceiling), 0.0), 1.0)
        merged["sla_violation_prob"] = merged["sla_violation_prob"].fillna(0.0).clip(0.0, risk_ceiling)
        merged["risk_delta"] = self._risk_delta_signal(merged)
        merged["max_step_change"] = self._adaptive_step_change(merged["risk_delta"])
        merged["admission_risk_signal"], merged["admission_risk_streak"] = self._admission_risk_signal(merged)
        merged["priority_weight"] = merged["slice_name"].map(self.priority_weights).fillna(1.0)
        merged["current_ratio"] = merged["slice_init_capacity"] / merged["base_station_capacity"].replace(0, 1)

        latency_pressure = (
            merged["latency_violation_ratio"].fillna(0.0)
            + (merged["avg_latency_ms"] / merged["max_avg_latency_ms"].replace(0, 1)).fillna(0.0)
        ) / 2.0
        merged["latency_pressure"] = latency_pressure.fillna(0.0).clip(0.0, 1.0)
        merged["urgency_score"] = (
            self.alpha_risk * merged["sla_violation_prob"]
            + self.beta_load * merged["avg_slice_load_ratio"].fillna(0.0)
            + self.gamma_latency * merged["latency_pressure"]
            + self.delta_priority * merged["priority_weight"]
        ).clip(lower=1e-6)

        action_rows = []
        for _, group in merged.groupby("base_station_id", sort=False):
            local = group.copy()
            local["request_pressure"] = self._normalize_for_local_pressure(local["request_count"])
            local["arrival_pressure"] = self._normalize_for_local_pressure(local["connected_events"])
            local["capacity_pressure"] = (1.0 - local["mean_remaining_capacity_ratio"].fillna(0.0)).clip(0.0, 1.0)
            local["margin_pressure"] = self._normalize_for_local_pressure(local["current_sla_near_breach_count"])
            local["first_service_pressure"] = (
                0.30 * local["request_pressure"]
                + 0.20 * local["arrival_pressure"]
                + 0.20 * local["capacity_pressure"]
                + 0.15 * local["block_ratio"].fillna(0.0).clip(0.0, 1.0)
                + 0.10 * local["latency_pressure"].fillna(0.0).clip(0.0, 1.0)
                + 0.05 * local["margin_pressure"]
            ).clip(0.0, 1.0)

            urllc_mask = local["slice_name"] == "URLLC"
            local["effective_urgency_score"] = local["urgency_score"]
            if urllc_mask.any() and self.urllc_first_service_gain > 0:
                local.loc[urllc_mask, "effective_urgency_score"] = local.loc[urllc_mask, "urgency_score"] * (
                    1.0 + self.urllc_first_service_gain * local.loc[urllc_mask, "first_service_pressure"]
                )

            if self.slice_ratio_biases:
                local["effective_urgency_score"] = (
                    local["effective_urgency_score"] + local["slice_name"].map(self.slice_ratio_biases).fillna(0.0)
                ).clip(lower=1e-6)

            urgency_sum = local["effective_urgency_score"].sum()
            if urgency_sum <= 0:
                raw_target_ratio = pd.Series([1.0 / len(local)] * len(local), index=local.index)
            else:
                raw_target_ratio = local["effective_urgency_score"] / urgency_sum

            local["raw_target_ratio"] = raw_target_ratio
            if self.optimization_qp_enabled:
                local = self._optimize_local_ratios_qp(local)
            elif self.action_optimizer_enabled:
                local = self._optimize_local_ratios(local)

            local["scheduling_weight"] = (
                local["priority_weight"]
                * (
                    1.0
                    + self.scheduling_risk_gain * local["sla_violation_prob"]
                    + self.scheduling_latency_gain * local["latency_pressure"]
                    + self.scheduling_load_gain * local["avg_slice_load_ratio"].fillna(0.0)
                )
            )
            local["admission_guard_factor"] = 1.0 + (
                self.admission_risk_gain * local["admission_risk_signal"]
                + self.admission_block_gain * local["block_ratio"].fillna(0.0)
            )

            if urllc_mask.any():
                local.loc[urllc_mask, "scheduling_weight"] = local.loc[urllc_mask, "scheduling_weight"] * (
                    1.0 + self.urllc_scheduling_bonus * local.loc[urllc_mask, "first_service_pressure"]
                )
                local.loc[urllc_mask, "admission_guard_factor"] = local.loc[urllc_mask, "admission_guard_factor"] + (
                    self.urllc_admission_guard_bonus * local.loc[urllc_mask, "first_service_pressure"]
                )

                shared_urllc_pressure = float(local.loc[urllc_mask, "first_service_pressure"].max())
                non_urllc_mask = ~urllc_mask
                if shared_urllc_pressure > 0 and non_urllc_mask.any():
                    local.loc[non_urllc_mask, "scheduling_weight"] = local.loc[
                        non_urllc_mask, "scheduling_weight"
                    ] * (1.0 - self.non_urllc_scheduling_backoff * shared_urllc_pressure)
                    local.loc[non_urllc_mask, "admission_guard_factor"] = local.loc[
                        non_urllc_mask, "admission_guard_factor"
                    ] + (self.non_urllc_admission_guard_bonus * shared_urllc_pressure)

            local["decision_reason"] = [
                (
                    f"preset={self.preset_name}, "
                    f"risk={risk:.3f}, "
                    f"admission_risk={admission_risk:.3f}, "
                    f"risk_streak={risk_streak}, "
                    f"load={load:.3f}, "
                    f"lat={lat:.3f}, "
                    f"lat_pressure={latency:.3f}, "
                    f"first_service_pressure={first_service:.3f}, "
                    f"risk_delta={risk_delta:.3f}, "
                    f"step={max_step:.3f}, "
                    f"optimizer={optimizer_choice}, "
                    f"optimizer_score={optimizer_score:.3f}, "
                    f"borrow={borrow_pool:.3f}"
                )
                for risk, admission_risk, risk_streak, load, lat, latency, first_service, risk_delta, max_step, optimizer_choice, optimizer_score, borrow_pool in zip(
                    local["sla_violation_prob"].fillna(0.0),
                    local["admission_risk_signal"].fillna(0.0),
                    local["admission_risk_streak"].fillna(0).astype(int),
                    local["avg_slice_load_ratio"].fillna(0.0),
                    local["latency_violation_ratio"].fillna(0.0),
                    local["latency_pressure"].fillna(0.0),
                    local["first_service_pressure"].fillna(0.0),
                    local["risk_delta"].fillna(0.0),
                    local["max_step_change"].fillna(self.constraints.max_step_change),
                    local.get("optimizer_choice", pd.Series(["disabled"] * len(local), index=local.index)).astype(str),
                    local.get("optimizer_score", pd.Series([0.0] * len(local), index=local.index)).fillna(0.0),
                    local.get("borrow_pool", pd.Series([0.0] * len(local), index=local.index)).fillna(0.0),
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
                        "decision_reason",
                    ]
                ]
            )

        action_df = pd.concat(action_rows, ignore_index=True)
        action_df.insert(0, "effective_time", effective_time if effective_time is not None else state_df["time"].max())
        action_df = normalize_ratio_actions(action_df, constraints=self.constraints)
        ordered_columns = [column for column in DEFAULT_ACTION_COLUMNS if column in action_df.columns] + [
            column for column in action_df.columns if column not in DEFAULT_ACTION_COLUMNS
        ]
        return action_df[ordered_columns]
