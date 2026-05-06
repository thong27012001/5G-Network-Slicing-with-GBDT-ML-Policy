"""Forecasting-aware broker planner for slice resource actions."""

from __future__ import annotations

import pandas as pd

from broker.broker_schema import BrokerConfig
from control.action_normalizer import normalize_ratio_actions
from control.controller_schema import ControllerConstraints


class ForecastingAdmissionPlanner:
    """Blend ML risk actions with forecasted traffic demand at broker level."""

    def __init__(self, config: BrokerConfig, controller):
        self.config = config
        self.controller = controller
        self._previous_target_ratios: dict[tuple[str, str], float] = {}

    @staticmethod
    def _forecast_share(forecast_df: pd.DataFrame) -> pd.Series:
        pressure = forecast_df["forecast_upper_demand_ratio"].fillna(0.0).clip(lower=0.0)
        total = pressure.sum()
        if total <= 0:
            return pd.Series([1.0 / max(len(forecast_df), 1)] * len(forecast_df), index=forecast_df.index)
        return pressure / total

    def _constraints_with_broker_floor(self, active_slice_names: set[str] | None = None) -> ControllerConstraints:
        base = self.controller.constraints
        use_all_slice_floors = active_slice_names is None
        active_slice_names = active_slice_names or set()
        min_ratio_by_slice = {
            slice_name: float(floor)
            for slice_name, floor in (getattr(base, "min_ratio_by_slice", {}) or {}).items()
            if use_all_slice_floors or slice_name in active_slice_names
        }
        for slice_name, floor in self.config.fairness_floor_by_slice.items():
            if not use_all_slice_floors and slice_name not in active_slice_names:
                continue
            min_ratio_by_slice[slice_name] = max(float(floor), float(min_ratio_by_slice.get(slice_name, 0.0)))
        return ControllerConstraints(
            min_ratio=base.min_ratio,
            max_ratio=base.max_ratio,
            max_step_change=base.max_step_change,
            scheduling_weight_floor=base.scheduling_weight_floor,
            scheduling_weight_ceiling=base.scheduling_weight_ceiling,
            admission_guard_floor=base.admission_guard_floor,
            admission_guard_ceiling=base.admission_guard_ceiling,
            min_ratio_by_slice=min_ratio_by_slice,
            max_ratio_by_slice=dict(getattr(base, "max_ratio_by_slice", {}) or {}),
        )

    def _smooth_target_ratio(self, group: pd.DataFrame) -> pd.Series:
        alpha = min(max(float(self.config.target_ratio_ema_alpha), 0.0), 1.0)
        raw = group["broker_raw_target_ratio"].fillna(group["target_ratio"]).astype(float)
        if alpha >= 1.0:
            smoothed = raw
        else:
            values = []
            for row, raw_value in zip(group.itertuples(index=False), raw):
                key = (str(row.base_station_id), str(row.slice_name))
                previous = self._previous_target_ratios.get(key, float(row.target_ratio))
                values.append(alpha * float(raw_value) + (1.0 - alpha) * previous)
            smoothed = pd.Series(values, index=group.index, dtype=float)

        return smoothed

    def _remember_target_ratio(self, normalized_group: pd.DataFrame) -> None:
        if "target_ratio" not in normalized_group.columns:
            return
        for row in normalized_group[["base_station_id", "slice_name", "target_ratio"]].itertuples(index=False):
            key = (str(row.base_station_id), str(row.slice_name))
            self._previous_target_ratios[key] = float(row.target_ratio)

    def plan(
        self,
        state_df: pd.DataFrame,
        prediction_df: pd.DataFrame,
        forecast_df: pd.DataFrame,
        effective_time: int | float,
    ) -> pd.DataFrame:
        base_actions = self.controller.decide(state_df, prediction_df, effective_time=effective_time)
        if base_actions.empty or forecast_df.empty:
            return base_actions

        merged = base_actions.merge(
            forecast_df[
                [
                    "effective_time",
                    "slice_name",
                    "base_station_id",
                    "forecast_demand_ratio",
                    "forecast_upper_demand_ratio",
                    "safety_margin",
                ]
            ],
            on=["effective_time", "slice_name", "base_station_id"],
            how="left",
        )
        merged["forecast_demand_ratio"] = merged["forecast_demand_ratio"].fillna(0.0)
        merged["forecast_upper_demand_ratio"] = merged["forecast_upper_demand_ratio"].fillna(0.0)
        merged["safety_margin"] = merged["safety_margin"].fillna(self.config.safety_margin_initial)

        frames = []
        for _, group in merged.groupby("base_station_id", sort=False):
            group = group.copy()
            group["broker_forecast_share"] = self._forecast_share(group)
            group["broker_forecast_pressure"] = group["forecast_upper_demand_ratio"].clip(0.0, 1.0)
            blend = min(max(float(self.config.forecast_blend), 0.0), 1.0)
            group["broker_raw_target_ratio"] = (
                (1.0 - blend) * group["target_ratio"] + blend * group["broker_forecast_share"]
            )
            group["raw_target_ratio"] = self._smooth_target_ratio(group)
            group["scheduling_weight"] = group["scheduling_weight"] * (
                1.0 + self.config.scheduling_forecast_gain * group["broker_forecast_pressure"]
            )
            group["admission_guard_factor"] = group["admission_guard_factor"] * (
                1.0 + self.config.admission_forecast_gain * group["broker_forecast_pressure"]
            )
            group["decision_reason"] = [
                (
                    f"{reason}, broker={self.config.name}, "
                    f"forecast_share={share:.3f}, "
                    f"forecast_upper={upper:.3f}, "
                    f"safety={margin:.3f}, "
                    f"ema_alpha={ema_alpha:.2f}"
                )
                for reason, share, upper, margin, ema_alpha in zip(
                    group["decision_reason"].astype(str),
                    group["broker_forecast_share"].fillna(0.0),
                    group["forecast_upper_demand_ratio"].fillna(0.0),
                    group["safety_margin"].fillna(self.config.safety_margin_initial),
                    pd.Series([self.config.target_ratio_ema_alpha] * len(group), index=group.index),
                )
            ]
            active_slice_names = set(
                group.loc[group["forecast_upper_demand_ratio"].fillna(0.0) > 1e-9, "slice_name"].astype(str)
            )
            normalized_group = normalize_ratio_actions(
                group,
                constraints=self._constraints_with_broker_floor(active_slice_names),
            )
            self._remember_target_ratio(normalized_group)
            frames.append(normalized_group)

        return pd.concat(frames, ignore_index=True)
