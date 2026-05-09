# SLA-Style KPI Plot Definitions

These charts are auxiliary comparison plots. Use the names below precisely in the thesis/report.

- `completion_ratio_hit.png`: per-UE completion-ratio hit. A UE is counted as hit when `completion_ratio >= 0.95`. This is a completion target, not a 3GPP-defined throughput SLA unless the report explicitly defines it as such.
- `delay_hit_sla_tolerance.png`: per-UE delay hit against the scenario/SLA delay tolerance. This is the SLA-aligned delay-hit chart.
- `delay_hit_relative_p75.png`: per-UE delay hit relative to the baseline p75 completion latency. This is a relative baseline comparison only, not a contractual SLA metric.
- `resource_utilization_cdf.png`: CDF of per-window `mean_slice_load_ratio` by slice and policy.

Current delay tolerance source: `scenario_yaml`.
SLA delay thresholds: URLLC=1ms, eMBB=100ms, mMTC=500ms.
Baseline-p75 relative thresholds: URLLC=0.070ms, eMBB=24.656ms, mMTC=0.425ms.
