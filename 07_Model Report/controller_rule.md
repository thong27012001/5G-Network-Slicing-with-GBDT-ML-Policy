# Controller Rule

The model report is global, but this section records the controller and broker
rule used by the release runner.

## Closed-Loop Decision Flow

1. The online state frame is converted into the same feature schema used during training.
2. The multi-horizon GBDT model predicts SLA-violation risk for each `(slice, base station)` row.
3. Horizon risks are blended using the weights in `horizon_models.json`.
4. Per-slice thresholds from model metadata convert calibrated probability into a warning/active-risk signal.
5. The controller maps risk, load, latency pressure, and slice priority into runtime actions.
6. The broker optionally smooths/adjusts the controller action using short-window demand forecast and safety feedback.

## Controller Formula

The controller uses the preset `balanced_ml_v3_gentle`.

```text
urgency_score =
    alpha_risk * predicted_sla_risk
  + beta_load * slice_load
  + gamma_latency * latency_pressure
  + delta_priority * slice_priority_weight

target_ratio = bounded_simplex_normalize(urgency_score)
scheduling_weight = priority_weight * (1 + scheduling gains from risk/latency/load)
admission_guard = clamp(1 + admission_risk_gain * risk + admission_block_gain * block_ratio)
```

Important controller parameters:

- `alpha_risk`: `0.3`
- `beta_load`: `0.28`
- `gamma_latency`: `0.22`
- `delta_priority`: `0.2`
- `scheduling_risk_gain`: `1.0`
- `scheduling_latency_gain`: `1.1`
- `scheduling_load_gain`: `0.2`
- `admission_risk_gain`: `0.3`
- `admission_block_gain`: `0.05`
- `risk_probability_ceiling`: `0.85`
- `max_step_change`: `0.08`
- `admission_guard_ceiling`: `1.15`
- `min_ratio_by_slice`: `{'URLLC': 0.2, 'eMBB': 0.15, 'mMTC': 0.1}`

## Broker Rule

The broker uses the preset `forecasting_balanced`.

Important broker parameters:

- `observed_window`: `8`
- `forecast_horizon`: `1`
- `forecast_blend`: `0.35`
- `smoothing_alpha`: `0.45`
- `scheduling_forecast_gain`: `0.18`
- `admission_forecast_gain`: `0.04`
- `target_ratio_ema_alpha`: `1.0`
- `fairness_floor_by_slice`: `{'URLLC': 0.2, 'eMBB': 0.12, 'mMTC': 0.08}`
