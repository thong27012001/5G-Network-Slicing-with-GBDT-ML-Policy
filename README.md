# 5G Network Slicing with GBDT ML Policy

This repository provides a compact 5G network slicing simulator with a trained
GBDT-based closed-loop policy for SLA-risk-aware resource allocation.

The release version keeps two runnable scenarios:

- `light`: light high-activity workload
- `heavy`: heavy high-activity workload

For each scenario, the main script runs two simulations with the same seed:

1. `Baseline`: fixed/open-loop slicing policy from the scenario configuration.
2. `ML Policy`: closed-loop GBDT SLA-risk predictor + controller + forecasting broker.

The generated output folder contains simulation maps, KPI comparison plots,
CSV reports, and SLA-style auxiliary plots.

## Project Workflow

```text
Scenario YAML
  -> Baseline simulator run
  -> ML closed-loop simulator run
       -> SLA-risk GBDT predictor
       -> controller action: target_ratio, scheduling_weight, admission_guard_factor
       -> forecasting broker smoothing and safety feedback
  -> KPI comparison report
  -> simulation maps and SLA hit plots
```

## Repository Layout

```text
broker/                  Forecasting broker and broker presets
control/                 GBDT controller, action constraints, action normalization
integration/             Online simulation adapters and closed-loop runner
ml/                      Feature schema, predictor, training utilities
models/sla_risk_gbdt/    Trained multi-horizon GBDT SLA-risk model
slicesim/                Discrete-event 5G slicing simulator
run_experiment.py        Main end-to-end release script
compare_baseline_vs_ml.py Comparison report generator used by the runner
```

## Installation

Use Python 3.12 or newer.

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

macOS/Linux:

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Run an End-to-End Experiment

Interactive scenario selection:

```bash
python run_experiment.py
```

Run a specific scenario:

```bash
python run_experiment.py --scenario light
python run_experiment.py --scenario heavy
```

Optional arguments:

```bash
python run_experiment.py --scenario light --seed 42
python run_experiment.py --scenario heavy --output-root results
```

## Input Files

The release runner uses these scenario inputs:

```text
slicesim/scenario-light.yml
slicesim/scenario-heavy.yml
```

SLA reference files:

```text
sla_reference_light.csv
sla_reference_heavy.csv
```

Model artifact:

```text
models/sla_risk_gbdt/
```

## Output Files

Each run creates one folder:

```text
FINAL_OUTPUT_<scenario>_<YYYYMMDD_HHMMSS>/
```

Important files inside the output folder:

```text
baseline_simulation_map.png
ml_policy_simulation_map.png
baseline_output.txt
ml_policy_output.txt
baseline_vs_ml_global_kpis.png
baseline_vs_ml_per_slice_bars.png
baseline_vs_ml_timeseries.png
ml_action_distribution.png
delay_hit_sla_tolerance.png
delay_hit_relative_p75.png
completion_ratio_hit.png
resource_utilization_cdf.png
global_kpi_comparison.csv
per_slice_comparison.csv
resource_allocation_summary.csv
ml_action_ratio_timeseries.csv
sla_style_kpi_definitions.md
baseline_vs_ml_report.md
RUN_SUMMARY.md
```

The `baseline_run/` and `ml_run/` subfolders also contain raw state, prediction,
action, client-level CSV files, and their own legacy-style `output.txt` logs.

## Policy Summary

The baseline policy is open-loop: slice ratios and admission/scheduling
parameters are fixed by the YAML scenario.

The ML policy is closed-loop: each simulation window is measured, converted into
features, passed through the trained GBDT SLA-risk predictor, and translated into
runtime resource-control actions by the controller and broker.

The main trade-off to inspect is throughput/resource-usage improvement versus
p95/tail latency and fairness. `delay_hit_sla_tolerance.png` is the SLA-aligned
delay-hit chart. `delay_hit_relative_p75.png` is only a relative comparison
against baseline p75 latency, not a contractual SLA metric.
