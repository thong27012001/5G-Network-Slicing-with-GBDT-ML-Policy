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
CSV reports, and SLA-style auxiliary plots. The GBDT model evaluation report is
generated once in the global `07_Model Report/` folder because the model does
not retrain per simulation seed.

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
run_experiment.py        Main end-to-end release script (single or multi-seed)
run_multiseed.py         Multi-seed wrapper (seed-as-outer-loop, auto mean+/-std)
compare_baseline_vs_ml.py Comparison report generator used by the runners
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

Multi-seed run for the same scenario (sequential, one folder per seed):

```bash
python run_experiment.py --scenario light --seed 7 42 123
python run_experiment.py --scenario heavy --seed 7 42 123 256
```

When more than one seed is given, output folders use the
`FINAL_OUTPUT_<scenario>_seed<N>_<timestamp>` naming so each seed has its own
artifact directory. Single-seed runs also include the seed in the folder name.
Temporary raw comparison files are created under `logs/raw_runs/` and removed
after the standardized output is produced unless `--keep-raw` is passed.

## Multi-Seed Statistical Runs

`run_multiseed.py` automates multi-seed experiments across both scenarios. For
each seed it runs the configured scenarios sequentially, then aggregates
mean +/- standard deviation across seeds. Use it to produce statistically
defensible results (e.g. n=5 to n=10 seeds) without manually invoking
`run_experiment.py` repeatedly.

```bash
python run_multiseed.py                                 # interactive prompts
python run_multiseed.py --seeds 7 42 123                # both scenarios, 3 seeds
python run_multiseed.py --scenarios light --seeds 7 42  # light only, 2 seeds
python run_multiseed.py --seeds 7 42 123 256 999 1234 \
    --summary-csv reports/multiseed_n6.csv              # custom summary path
```

The seed list accepts space- or comma-separated integers in the interactive
prompt (`'7 42 123'` or `'7,42,123'`).

After all runs finish, the script:

1. Prints a `mean +/- std` aggregate table per `(scenario, metric)` to stdout.
2. Writes `multiseed_summary.csv` with one row per `(seed, metric)` and the
   resolved output directory + wall-time.
3. Writes `multiseed_summary_aggregate.csv` with `mean_pct` and `std_pct`
   columns suitable for thesis/report tables.

If a single run fails it is logged and the rest of the batch continues; the
final summary lists any failures.

Each multi-seed run uses the same standardized output format as
`run_experiment.py`: `01_output_simulation/` through
`06_tradeoff_discussion_report/`, plus `RUN_SUMMARY.md`.

To recompute statistics from existing output folders without rerunning the
simulator:

```bash
python tools/summarize_existing_outputs.py --search-root .
python tools/summarize_existing_outputs.py --search-root FINAL_OUTPUT_#1
```

This writes:

```text
existing_outputs_multiseed_summary.csv
existing_outputs_multiseed_summary_aggregate.csv
```

The full heavy scenario is intentionally large (`7500` clients,
`simulation_time=2000`) and can take hours per seed on a laptop. For quick
smoke testing, run `light` first; use `heavy` multi-seed runs on a machine that
can run unattended.

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

Each run creates one standardized folder:

```text
FINAL_OUTPUT_<scenario>_seed<N>_<YYYYMMDD_HHMMSS>/
```

Multi-seed runs additionally write `multiseed_summary.csv` and
`multiseed_summary_aggregate.csv` at the repo root (or the path given by
`--summary-csv`).

Important folders inside each output folder:

```text
01_output_simulation/
02_model_training_report_plot/
03_KPI_plot_output_with_baseline/
04_KPI_plot_output_with_ML_Policy/
05_KPI_plot_output_comparison/
06_tradeoff_discussion_report/
RUN_SUMMARY.md
```

The main comparison plots and CSV files are in
`05_KPI_plot_output_comparison/`, including `completion_ratio_hit.png`,
`delay_hit_sla_tolerance.png`, `delay_hit_relative_p75.png`,
`p95_latency_vs_sla.png`, `resource_utilization_cdf.png`,
`global_kpi_comparison.csv`, and `per_slice_comparison.csv`.

The global model report is stored once at repo root:

```text
07_Model Report/
```

It contains ROC-AUC, precision/recall/F1, confusion matrix, feature importance,
threshold tuning, and the controller/broker rule used by the ML policy.

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

### Completion-Ratio Hit Thresholds

`completion_ratio_hit.png` uses **per-(scenario, slice) thresholds** chosen so
that both Baseline and ML policy produce statistically meaningful values:

| Scenario | URLLC | eMBB | mMTC | Reason |
|----------|-------|------|------|--------|
| `light`  | 0.95  | 0.95 | 0.95 | Per-UE workload reaches >0.95 freely; default. |
| `heavy`  | 0.95  | 0.90 | 0.95 | eMBB capped at ~0.90 by simulation cutoff (~10 req/UE); 0.95 saturates BL/ML at near-zero. |

URLLC and mMTC always use 0.95 (they reach 1.00 hit regardless and are not
request-cutoff bound, so they are unaffected by the eMBB-only adjustment).

### Per-Slice p95 Latency vs SLA Target

`p95_latency_vs_sla.png` shows the 95th percentile of per-UE
`avg_completion_latency_ms` per slice for Baseline and ML Policy as grouped
bars, with the scenario p95 SLA cap drawn as a green dashed line and the
PASS/FAIL margin annotated. The SLA p95 caps are read from
`sla_reference_<scenario>.csv` (`max_p95_latency_ms`):

| Scenario | URLLC | eMBB | mMTC |
|----------|-------|------|------|
| `light`  | 10 ms | 30 ms | 100 ms |
| `heavy`  | 5 ms  | 40 ms | 150 ms |

The chart is generated automatically by `run_experiment.py` and
`run_multiseed.py`; the SLA p95 line is drawn only when the scenario is known
(otherwise the bars are shown without the cap).

Override at the CLI:

```bash
python tools/export_sla_kpi_plots.py FINAL_OUTPUT_heavy_seed42_<ts> --scenario heavy
python tools/export_sla_kpi_plots.py FINAL_OUTPUT_light_seed42_<ts> --scenario light
```

Without `--scenario`, the script auto-detects from the directory name
(`FINAL_OUTPUT_<scenario>_*`). `run_experiment.py` and `run_multiseed.py`
automatically pass the correct thresholds based on the scenario being run.
