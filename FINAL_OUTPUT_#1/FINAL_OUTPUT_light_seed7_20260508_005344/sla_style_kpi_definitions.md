# SLA-Style KPI Plot Definitions

These charts are auxiliary comparison plots. Use the names below precisely in the thesis/report.

- `completion_ratio_hit.png`: per-UE completion-ratio hit using **per-slice thresholds** (URLLC>=0.95, eMBB>=0.95, mMTC>=0.95). eMBB uses 0.90 instead of 0.95 to avoid the simulation-cutoff artifact (~10 requests per UE caps eMBB completion ratio at ~0.90); URLLC and mMTC keep 0.95 because their workloads are not request-cutoff bound and reach 1.00 anyway. This is a completion target, not a 3GPP-defined throughput SLA unless the report explicitly defines it as such.
- `delay_hit_sla_tolerance.png`: per-UE delay hit against the scenario/SLA delay tolerance. This is the SLA-aligned delay-hit chart.
- `delay_hit_relative_p75.png`: per-UE delay hit relative to the baseline p75 completion latency. This is a relative baseline comparison only, not a contractual SLA metric.
- `p95_latency_vs_sla.png`: per-slice 95th percentile of per-UE `avg_completion_latency_ms`, grouped bars BL vs ML. When a scenario p95 SLA target is provided (`SCENARIO_P95_SLA_TARGET_MS`), a green dashed line shows the target and the annotation reports PASS/FAIL per (slice, policy).
- `resource_utilization_cdf.png`: CDF of per-window `mean_slice_load_ratio` by slice and policy.

Current delay tolerance source: `scenario_yaml`.
SLA delay thresholds (avg): URLLC=1ms, eMBB=100ms, mMTC=500ms.
Baseline-p75 relative thresholds: URLLC=0.065ms, eMBB=11.567ms, mMTC=0.303ms.
Completion-ratio hit thresholds: URLLC>=0.95, eMBB>=0.95, mMTC>=0.95.
Per-slice p95 (BL/ML, ms): URLLC=0.067/0.061ms, eMBB=13.034/11.992ms, mMTC=0.321/0.328ms.
SLA p95 targets: URLLC=10ms, eMBB=30ms, mMTC=100ms.
