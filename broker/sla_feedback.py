"""Feedback loop that adapts broker safety margins from observed SLA deviations."""

from __future__ import annotations

import pandas as pd

from broker.broker_schema import BrokerConfig


class SlaFeedbackController:
    """Track slice-level SLA pressure and adjust forecast safety margins."""

    def __init__(self, config: BrokerConfig):
        self.config = config
        self.safety_margins = {
            slice_name: float(value)
            for slice_name, value in config.initial_safety_margin_by_slice.items()
        }

    def get_safety_margins(self) -> dict[str, float]:
        return dict(self.safety_margins)

    def update(self, state_df: pd.DataFrame, effective_time: int | float) -> pd.DataFrame:
        if state_df.empty:
            return pd.DataFrame()

        rows = []
        grouped = state_df.groupby("slice_name", as_index=False).agg(
            observed_sla_violation_share=("current_sla_violation", "mean"),
            observed_near_breach_share=("current_sla_near_breach_count", "mean"),
            observed_request_count=("request_count", "sum"),
            observed_avg_load=("mean_slice_load_ratio", "mean"),
            observed_latency_violation_ratio=("latency_violation_ratio", "mean"),
        )
        for _, row in grouped.iterrows():
            slice_name = row["slice_name"]
            before = float(
                self.safety_margins.get(
                    slice_name,
                    self.config.initial_safety_margin_by_slice.get(slice_name, self.config.safety_margin_initial),
                )
            )
            violation_pressure = max(
                float(row["observed_sla_violation_share"]),
                float(row["observed_latency_violation_ratio"]),
            )
            if violation_pressure >= self.config.violation_threshold:
                after = before + self.config.safety_margin_step_up * violation_pressure
                reason = "increase_margin_due_to_sla_pressure"
            elif violation_pressure <= self.config.safe_threshold:
                after = before - self.config.safety_margin_step_down
                reason = "decrease_margin_after_safe_window"
            else:
                after = before
                reason = "hold_margin"

            after = min(max(after, self.config.safety_margin_min), self.config.safety_margin_max)
            self.safety_margins[slice_name] = after
            rows.append(
                {
                    "effective_time": effective_time,
                    "slice_name": slice_name,
                    "observed_sla_violation_share": float(row["observed_sla_violation_share"]),
                    "observed_latency_violation_ratio": float(row["observed_latency_violation_ratio"]),
                    "observed_near_breach_share": float(row["observed_near_breach_share"]),
                    "observed_request_count": float(row["observed_request_count"]),
                    "observed_avg_load": float(row["observed_avg_load"]),
                    "safety_margin_before": before,
                    "safety_margin_after": after,
                    "feedback_reason": reason,
                }
            )
        return pd.DataFrame(rows)

