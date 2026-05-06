"""Lightweight per-slice traffic forecasting for broker-level decisions."""

from __future__ import annotations

import math

import pandas as pd

from broker.broker_schema import BrokerConfig


class TrafficForecaster:
    """Forecast short-horizon slice demand from recent simulator windows.

    The reference paper uses Holt-Winters prediction intervals. To keep this
    project dependency-light, this forecaster uses the same idea at a smaller
    scale: recent demand level + local trend + a safety margin over observed
    one-step forecast error.
    """

    def __init__(self, config: BrokerConfig):
        self.config = config

    @staticmethod
    def _demand_signal(frame: pd.DataFrame) -> pd.Series:
        # Tất cả thành phần phải cùng đơn vị BS-relative để forecast share so sánh được
        # giữa các slice trên cùng base station. mean_slice_load_ratio nguyên gốc là
        # slice-relative (quy theo init_capacity của chính slice) nên được nhân với tỉ
        # phần slice/BS để đưa về BS-relative trước khi gộp.
        base_capacity = frame["base_station_capacity"].replace(0, 1)
        requested_ratio = (frame["requested_usage_sum"].fillna(0.0) / base_capacity).clip(0.0, 2.0)
        used_ratio = (frame["slice_used_diff"].fillna(0.0) / base_capacity).clip(0.0, 1.5)
        slice_share_of_bs = (frame["slice_init_capacity"].fillna(0.0) / base_capacity).clip(0.0, 1.0)
        bs_relative_load = (frame["mean_slice_load_ratio"].fillna(0.0) * slice_share_of_bs).clip(0.0, 1.5)
        return pd.concat([requested_ratio, used_ratio, bs_relative_load], axis=1).max(axis=1)

    @staticmethod
    def _one_step_error_std(values: list[float]) -> float:
        if len(values) < 3:
            return 0.0
        errors = []
        for index in range(1, len(values)):
            errors.append(values[index] - values[index - 1])
        if len(errors) < 2:
            return 0.0
        mean_error = sum(errors) / len(errors)
        variance = sum((error - mean_error) ** 2 for error in errors) / (len(errors) - 1)
        return math.sqrt(max(variance, 0.0))

    def _forecast_next(self, values: list[float], horizon: int) -> float:
        if not values:
            return 0.0
        if len(values) == 1:
            return max(values[-1], 0.0)

        recent = values[-max(self.config.observed_window, 1):]
        trend = (recent[-1] - recent[0]) / max(len(recent) - 1, 1)
        alpha = min(max(float(self.config.smoothing_alpha), 0.0), 1.0)
        level = recent[0]
        for value in recent[1:]:
            level = alpha * value + (1.0 - alpha) * level
        return max(level + trend * max(horizon, 1), 0.0)

    def forecast(
        self,
        history_df: pd.DataFrame,
        state_df: pd.DataFrame,
        safety_margins: dict[str, float],
        effective_time: int | float,
    ) -> pd.DataFrame:
        if state_df.empty:
            return pd.DataFrame()

        history = history_df.copy()
        if history.empty:
            history = state_df.copy()
        history["broker_demand_signal"] = self._demand_signal(history)

        rows = []
        for _, state_row in state_df.iterrows():
            slice_name = state_row["slice_name"]
            base_station_id = state_row["base_station_id"]
            group = history[
                (history["slice_name"] == slice_name)
                & (history["base_station_id"] == base_station_id)
            ].sort_values("time")
            values = (
                group["broker_demand_signal"]
                .tail(max(self.config.observed_window, 1))
                .fillna(0.0)
                .clip(lower=0.0)
                .tolist()
            )
            observed = values[-1] if values else 0.0
            forecast = self._forecast_next(values, self.config.forecast_horizon)
            error_std = self._one_step_error_std(values)
            safety_margin = float(
                safety_margins.get(
                    slice_name,
                    self.config.initial_safety_margin_by_slice.get(slice_name, self.config.safety_margin_initial),
                )
            )
            upper = max(forecast + safety_margin * error_std, observed)

            rows.append(
                {
                    "effective_time": effective_time,
                    "slice_name": slice_name,
                    "base_station_id": base_station_id,
                    "observed_demand_ratio": observed,
                    "forecast_demand_ratio": min(forecast, 2.0),
                    "forecast_upper_demand_ratio": min(upper, 2.0),
                    "forecast_error_std": error_std,
                    "safety_margin": safety_margin,
                    "forecast_reason": (
                        f"window={len(values)}, horizon={self.config.forecast_horizon}, "
                        f"alpha={self.config.smoothing_alpha:.3f}, margin={safety_margin:.3f}"
                    ),
                }
            )

        return pd.DataFrame(rows)
