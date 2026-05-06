"""Schema và preset cho slicing control loop ở mức broker."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass(slots=True)
class BrokerConfig:
    name: str = "forecasting_balanced"
    description: str = "Broker có xét forecasting, kết hợp action từ risk của ML với traffic demand forecast."
    observed_window: int = 8
    forecast_horizon: int = 1
    smoothing_alpha: float = 0.45
    forecast_blend: float = 0.35
    safety_margin_initial: float = 1.0
    safety_margin_min: float = 0.45
    safety_margin_max: float = 2.50
    safety_margin_step_up: float = 0.25
    safety_margin_step_down: float = 0.05
    violation_threshold: float = 0.15
    safe_threshold: float = 0.03
    scheduling_forecast_gain: float = 0.18
    admission_forecast_gain: float = 0.04
    target_ratio_ema_alpha: float = 1.0
    fairness_floor_by_slice: dict[str, float] = field(
        default_factory=lambda: {"URLLC": 0.20, "eMBB": 0.12, "mMTC": 0.08}
    )
    initial_safety_margin_by_slice: dict[str, float] = field(
        default_factory=lambda: {"URLLC": 1.25, "eMBB": 0.90, "mMTC": 0.90}
    )


@dataclass(slots=True)
class BrokerDecision:
    actions: pd.DataFrame
    forecasts: pd.DataFrame
    feedback: pd.DataFrame


BROKER_PRESETS: dict[str, BrokerConfig] = {
    "forecasting_balanced": BrokerConfig(),
    "forecasting_conservative": BrokerConfig(
        name="forecasting_conservative",
        description="Broker thận trọng hơn, dùng khoảng forecast lớn hơn và điều chỉnh ratio chậm hơn.",
        forecast_blend=0.25,
        safety_margin_initial=1.35,
        safety_margin_max=3.00,
        safety_margin_step_up=0.35,
        safety_margin_step_down=0.03,
        scheduling_forecast_gain=0.24,
        admission_forecast_gain=0.16,
        initial_safety_margin_by_slice={"URLLC": 1.60, "eMBB": 1.10, "mMTC": 1.10},
    ),
    "forecasting_aggressive": BrokerConfig(
        name="forecasting_aggressive",
        description="Broker quyết liệt hơn, tin vào forecast nhiều hơn và hướng tới mức utilization tài nguyên cao hơn.",
        forecast_blend=0.50,
        safety_margin_initial=0.75,
        safety_margin_min=0.30,
        safety_margin_max=2.00,
        safety_margin_step_up=0.20,
        safety_margin_step_down=0.08,
        scheduling_forecast_gain=0.42,
        admission_forecast_gain=0.08,
        initial_safety_margin_by_slice={"URLLC": 1.05, "eMBB": 0.70, "mMTC": 0.70},
    ),
    "forecasting_guarded_optimizer": BrokerConfig(
        name="forecasting_guarded_optimizer",
        description=(
            "Guarded broker preset for ML action optimization: use forecast as a soft demand signal, "
            "keep admission neutral, and avoid high fairness floors for inactive slices."
        ),
        observed_window=8,
        smoothing_alpha=0.35,
        forecast_blend=0.18,
        safety_margin_initial=0.90,
        safety_margin_min=0.35,
        safety_margin_max=1.80,
        safety_margin_step_up=0.12,
        safety_margin_step_down=0.08,
        violation_threshold=0.18,
        safe_threshold=0.04,
        scheduling_forecast_gain=0.08,
        admission_forecast_gain=0.00,
        fairness_floor_by_slice={"URLLC": 0.12, "eMBB": 0.08, "mMTC": 0.05},
        initial_safety_margin_by_slice={"URLLC": 1.05, "eMBB": 0.78, "mMTC": 0.78},
    ),
    "forecasting_demand_aware": BrokerConfig(
        name="forecasting_demand_aware",
        description=(
            "Broker để cầu thực tế dẫn dắt allocation: bỏ fairness floor cứng, hạ "
            "scheduling/admission forecast gain để không khuếch đại stacking với controller, "
            "tăng safety_margin_step_down để feedback có thể nhả áp lực khi state trở lại an toàn."
        ),
        observed_window=8,
        smoothing_alpha=0.40,
        forecast_blend=0.30,
        safety_margin_initial=1.00,
        safety_margin_min=0.40,
        safety_margin_max=2.00,
        safety_margin_step_up=0.20,
        safety_margin_step_down=0.10,
        violation_threshold=0.15,
        safe_threshold=0.05,
        scheduling_forecast_gain=0.20,
        admission_forecast_gain=0.06,
        fairness_floor_by_slice={},
        initial_safety_margin_by_slice={"URLLC": 1.10, "eMBB": 0.90, "mMTC": 0.90},
    ),
    "forecasting_demand_aware_smooth": BrokerConfig(
        name="forecasting_demand_aware_smooth",
        description=(
            "Demand-aware broker with EMA smoothing on target_ratio. It keeps the no-floor demand-aware behavior "
            "but smooths broker_raw_target_ratio across windows to reduce oscillation and eMBB reallocation jitter."
        ),
        observed_window=8,
        smoothing_alpha=0.40,
        forecast_blend=0.30,
        safety_margin_initial=1.00,
        safety_margin_min=0.40,
        safety_margin_max=2.00,
        safety_margin_step_up=0.20,
        safety_margin_step_down=0.10,
        violation_threshold=0.15,
        safe_threshold=0.05,
        scheduling_forecast_gain=0.18,
        admission_forecast_gain=0.04,
        target_ratio_ema_alpha=0.40,
        fairness_floor_by_slice={},
        initial_safety_margin_by_slice={"URLLC": 1.10, "eMBB": 0.90, "mMTC": 0.90},
    ),
    "forecasting_tail_guard_smooth": BrokerConfig(
        name="forecasting_tail_guard_smooth",
        description=(
            "Tail-guard broker for v7: keep EMA smoothing, reduce forecast amplification, "
            "and bias safety margins away from over-borrowing by eMBB under heavy load."
        ),
        observed_window=8,
        smoothing_alpha=0.40,
        forecast_blend=0.22,
        safety_margin_initial=1.05,
        safety_margin_min=0.45,
        safety_margin_max=2.00,
        safety_margin_step_up=0.18,
        safety_margin_step_down=0.08,
        violation_threshold=0.12,
        safe_threshold=0.04,
        scheduling_forecast_gain=0.10,
        admission_forecast_gain=0.03,
        target_ratio_ema_alpha=0.35,
        fairness_floor_by_slice={},
        initial_safety_margin_by_slice={"URLLC": 1.18, "eMBB": 0.86, "mMTC": 0.98},
    ),
    "forecasting_latency_safe_smooth": BrokerConfig(
        name="forecasting_latency_safe_smooth",
        description=(
            "Latency-safe broker for v8: very small forecast amplification and smoother target updates "
            "so heavy-load runs do not over-allocate transient eMBB demand."
        ),
        observed_window=8,
        smoothing_alpha=0.40,
        forecast_blend=0.15,
        safety_margin_initial=1.08,
        safety_margin_min=0.50,
        safety_margin_max=2.00,
        safety_margin_step_up=0.16,
        safety_margin_step_down=0.06,
        violation_threshold=0.10,
        safe_threshold=0.035,
        scheduling_forecast_gain=0.06,
        admission_forecast_gain=0.02,
        target_ratio_ema_alpha=0.30,
        fairness_floor_by_slice={},
        initial_safety_margin_by_slice={"URLLC": 1.25, "eMBB": 0.82, "mMTC": 1.05},
    ),
    "forecasting_heavy_urllc_guard_smooth": BrokerConfig(
        name="forecasting_heavy_urllc_guard_smooth",
        description=(
            "Heavy-load URLLC guard broker for v9: keep forecast influence small, smooth target updates, "
            "and bias feedback toward preserving URLLC headroom instead of chasing eMBB burst demand."
        ),
        observed_window=8,
        smoothing_alpha=0.40,
        forecast_blend=0.10,
        safety_margin_initial=1.12,
        safety_margin_min=0.55,
        safety_margin_max=2.00,
        safety_margin_step_up=0.14,
        safety_margin_step_down=0.05,
        violation_threshold=0.09,
        safe_threshold=0.03,
        scheduling_forecast_gain=0.04,
        admission_forecast_gain=0.01,
        target_ratio_ema_alpha=0.25,
        fairness_floor_by_slice={},
        initial_safety_margin_by_slice={"URLLC": 1.40, "eMBB": 0.78, "mMTC": 1.08},
    ),
}


def get_broker_config(name: str | None) -> BrokerConfig:
    if not name:
        return BrokerConfig()
    if name not in BROKER_PRESETS:
        valid_names = ", ".join(sorted(BROKER_PRESETS))
        raise ValueError(f"Unknown broker preset '{name}'. Valid presets: {valid_names}")
    preset = BROKER_PRESETS[name]
    return BrokerConfig(
        name=preset.name,
        description=preset.description,
        observed_window=preset.observed_window,
        forecast_horizon=preset.forecast_horizon,
        smoothing_alpha=preset.smoothing_alpha,
        forecast_blend=preset.forecast_blend,
        safety_margin_initial=preset.safety_margin_initial,
        safety_margin_min=preset.safety_margin_min,
        safety_margin_max=preset.safety_margin_max,
        safety_margin_step_up=preset.safety_margin_step_up,
        safety_margin_step_down=preset.safety_margin_step_down,
        violation_threshold=preset.violation_threshold,
        safe_threshold=preset.safe_threshold,
        scheduling_forecast_gain=preset.scheduling_forecast_gain,
        admission_forecast_gain=preset.admission_forecast_gain,
        target_ratio_ema_alpha=preset.target_ratio_ema_alpha,
        fairness_floor_by_slice=dict(preset.fairness_floor_by_slice),
        initial_safety_margin_by_slice=dict(preset.initial_safety_margin_by_slice),
    )
