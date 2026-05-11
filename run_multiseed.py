"""Run baseline vs ML policy across multiple seeds for both release scenarios.

Seed-as-outer-loop: for each seed, runs the configured scenarios (default: light, heavy)
sequentially, then moves to the next seed. Per-scenario completion is reported with
its KPI delta; per-seed and overall aggregates (mean +/- std) are printed at the end.

Usage:
    python run_multiseed.py --seeds 7 42 123
    python run_multiseed.py                       # interactive
    python run_multiseed.py --scenarios light --seeds 7 42 123
    python run_multiseed.py --seeds 7 42 --summary-csv my_summary.csv

Outputs:
    - One FINAL_OUTPUT_<scenario>_seed<N>_<timestamp>/ directory per (scenario, seed).
    - Summary CSV (default: multiseed_summary.csv) with per-run rows.
    - Aggregate CSV (multiseed_summary_aggregate.csv) with mean +/- std per
      (scenario, metric).
"""
from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from statistics import mean, stdev

from organize_pipeline_outputs import organize_pipeline_outputs
from tools.export_sla_kpi_plots import (
    SCENARIO_DELAY_TOLERANCE_MS,
    export_for_run,
    p95_targets_for_scenario,
    thresholds_for_scenario,
)


SCENARIOS = {
    "light": {
        "config": "slicesim/scenario-light.yml",
        "sla": "sla_reference_light.csv",
        "description": "Light high-activity 5G slicing workload",
    },
    "heavy": {
        "config": "slicesim/scenario-heavy.yml",
        "sla": "sla_reference_heavy.csv",
        "description": "Heavy high-activity 5G slicing workload",
    },
}

DEFAULT_MODEL_DIR = "models/sla_risk_gbdt"
DEFAULT_CONTROLLER_PRESET = "balanced_ml_v3_gentle"
DEFAULT_BROKER_PRESET = "forecasting_balanced"

REPORT_KPIS = (
    "total_bandwidth_usage",
    "avg_latency_ms",
    "p95_latency_ms",
    "latency_violation_ratio",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _parse_seed_list(text: str) -> list[int] | None:
    tokens = [tok for tok in text.replace(",", " ").split() if tok]
    if not tokens:
        return None
    try:
        return [int(tok) for tok in tokens]
    except ValueError:
        return None


def _select_seeds(cli_value: list[int] | None) -> list[int]:
    if cli_value:
        return cli_value

    print("\nSelect seed(s) for multi-seed run:")
    print("  - Single seed: '42'")
    print("  - Multi-seed:  '7 42 123' or '7,42,123'")
    print("  - Blank for default '7 42 123'")

    while True:
        raw = input("Enter seeds [7 42 123]: ").strip() or "7 42 123"
        seeds = _parse_seed_list(raw)
        if seeds:
            return seeds
        print("Invalid seed list. Use integers separated by space or comma.")


def _select_scenarios(cli_value: list[str] | None) -> list[str]:
    if cli_value:
        return cli_value
    return list(SCENARIOS)


def _format_duration(seconds: float) -> str:
    total = int(round(seconds))
    minutes, sec = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h{minutes:02d}m{sec:02d}s"
    return f"{minutes}m{sec:02d}s"


def _read_global_kpi(output_dir: Path) -> dict[str, dict[str, float]]:
    """Parse global_kpi_comparison.csv into {metric: {baseline, ml, delta_pct}}."""
    csv_path = output_dir / "05_KPI_plot_output_comparison" / "global_kpi_comparison.csv"
    if not csv_path.exists():
        csv_path = output_dir / "global_kpi_comparison.csv"
    out: dict[str, dict[str, float]] = {}
    with csv_path.open() as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            try:
                out[row["metric"]] = {
                    "baseline": float(row["baseline"]),
                    "ml": float(row["ml_policy"]),
                    "delta_pct": float(row["delta_pct"]),
                }
            except (KeyError, ValueError):
                continue
    return out


def _post_process(output_dir: Path, scenario: str) -> None:
    shortcuts = {
        output_dir / "baseline_run" / "baseline_simulation.png": output_dir / "baseline_simulation_map.png",
        output_dir / "ml_run" / "ml_policy_simulation.png": output_dir / "ml_policy_simulation_map.png",
        output_dir / "baseline_run" / "output.txt": output_dir / "baseline_output.txt",
        output_dir / "ml_run" / "output.txt": output_dir / "ml_policy_output.txt",
    }
    for source, target in shortcuts.items():
        if source.exists():
            shutil.copy2(source, target)
    try:
        export_for_run(
            output_dir,
            SCENARIO_DELAY_TOLERANCE_MS.copy(),
            "scenario_yaml",
            completion_thresholds=thresholds_for_scenario(scenario),
            p95_sla_targets=p95_targets_for_scenario(scenario),
        )
    except Exception as exc:  # pragma: no cover - best-effort post-processing
        print(f"     [warn] SLA-hit export failed: {exc}")


def _write_run_summary(output_dir: Path, scenario: str, command: list[str]) -> None:
    text = [
        f"# Experiment Output: {scenario}",
        "",
        "This standardized folder was generated by `run_multiseed.py`.",
        "",
        "## Command",
        "",
        "```text",
        " ".join(command),
        "```",
        "",
        "## Key files",
        "",
        "- `01_output_simulation/`: raw baseline and ML simulation CSV outputs.",
        "- `02_model_training_report_plot/`: model artifact summary copied from the model directory.",
        "- `03_KPI_plot_output_with_baseline/`: baseline-only KPI tables and raw files.",
        "- `04_KPI_plot_output_with_ML_Policy/`: ML-policy KPI/action/prediction files.",
        "- `05_KPI_plot_output_comparison/`: baseline-vs-ML CSV/PNG comparison artifacts.",
        "- `06_tradeoff_discussion_report/`: generated trade-off discussion report.",
        "- `../07_Model Report/`: global GBDT model report shared by all simulation seeds.",
        "",
    ]
    (output_dir / "RUN_SUMMARY.md").write_text("\n".join(text), encoding="utf-8")


def _run_one(scenario: str, seed: int, args: argparse.Namespace) -> tuple[Path, float]:
    repo_root = _repo_root()
    cfg = SCENARIOS[scenario]

    output_root = Path(args.output_root)
    if not output_root.is_absolute():
        output_root = repo_root / output_root

    timestamp = _timestamp()
    output_dir = output_root / f"FINAL_OUTPUT_{scenario}_seed{seed}_{timestamp}"
    raw_root = output_root / "logs" / "raw_runs"
    raw_dir = raw_root / f"raw_{scenario}_seed{seed}_{timestamp}"
    raw_dir.mkdir(parents=True, exist_ok=False)

    command = [
        sys.executable,
        str(repo_root / "compare_baseline_vs_ml.py"),
        "--config", str(repo_root / cfg["config"]),
        "--sla-path", str(repo_root / cfg["sla"]),
        "--model-dir", str(repo_root / args.model_dir),
        "--controller-type", "gbdt",
        "--controller-preset", args.controller_preset,
        "--use-broker",
        "--broker-preset", args.broker_preset,
        "--seed", str(seed),
        "--output-dir", str(raw_dir),
        "--pipeline-output-root", "",
    ]

    t0 = time.time()
    subprocess.run(command, cwd=repo_root, check=True)
    elapsed = time.time() - t0

    _post_process(raw_dir, scenario)
    organize_pipeline_outputs(
        scenario=f"{scenario}_seed{seed}",
        comparison_dir=raw_dir,
        model_dir=repo_root / args.model_dir,
        output_dir=output_dir,
        overwrite=True,
    )
    _write_run_summary(output_dir, f"{scenario} seed {seed}", command)
    if not args.keep_raw:
        shutil.rmtree(raw_dir)
    return output_dir, elapsed


def _format_kpi_line(kpi: dict[str, dict[str, float]]) -> str:
    parts = []
    for metric in REPORT_KPIS:
        if metric in kpi:
            parts.append(f"{metric}={kpi[metric]['delta_pct']:+.2f}%")
    return ", ".join(parts) if parts else "(no global KPIs read)"


def _aggregate(records: list[dict]) -> list[dict]:
    by_key: dict[tuple[str, str], list[float]] = {}
    for rec in records:
        for metric, vals in rec["kpi"].items():
            by_key.setdefault((rec["scenario"], metric), []).append(vals["delta_pct"])

    summary: list[dict] = []
    for (scen, metric), vals in sorted(by_key.items()):
        n = len(vals)
        m = mean(vals) if n else float("nan")
        s = stdev(vals) if n > 1 else 0.0
        summary.append({"scenario": scen, "metric": metric, "n": n, "mean_pct": m, "std_pct": s})
    return summary


def _write_summary_csv(records: list[dict], summary: list[dict], summary_path: Path) -> Path:
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    with summary_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["scenario", "seed", "metric", "baseline", "ml", "delta_pct", "output_dir", "elapsed_seconds"],
        )
        writer.writeheader()
        for rec in records:
            for metric, vals in rec["kpi"].items():
                writer.writerow({
                    "scenario": rec["scenario"],
                    "seed": rec["seed"],
                    "metric": metric,
                    "baseline": vals["baseline"],
                    "ml": vals["ml"],
                    "delta_pct": vals["delta_pct"],
                    "output_dir": rec["output_dir"],
                    "elapsed_seconds": f"{rec['elapsed']:.1f}",
                })

    aggregate_path = summary_path.with_name(summary_path.stem + "_aggregate.csv")
    with aggregate_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["scenario", "metric", "n", "mean_pct", "std_pct"])
        writer.writeheader()
        for row in summary:
            writer.writerow({
                "scenario": row["scenario"],
                "metric": row["metric"],
                "n": row["n"],
                "mean_pct": f"{row['mean_pct']:.4f}",
                "std_pct": f"{row['std_pct']:.4f}",
            })
    return aggregate_path


def _print_aggregate(summary: list[dict]) -> None:
    print("\n" + "=" * 78)
    print(" AGGREGATE: Delta% (ML vs Baseline) - mean +/- std")
    print("=" * 78)
    print(f"{'scenario':<10}  {'metric':<28}  {'n':>3}  {'mean':>10}  {'std':>9}")
    print("-" * 78)
    for row in summary:
        print(
            f"{row['scenario']:<10}  {row['metric']:<28}  {row['n']:>3d}  "
            f"{row['mean_pct']:>+9.3f}%  {row['std_pct']:>8.3f}%"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Automate baseline vs ML policy runs across multiple seeds for both release "
            "scenarios. Seed-as-outer-loop: for each seed, runs all scenarios sequentially."
        )
    )
    parser.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        default=None,
        help="Seeds to run (e.g. --seeds 7 42 123). If omitted, prompts interactively.",
    )
    parser.add_argument(
        "--scenarios",
        nargs="+",
        choices=sorted(SCENARIOS),
        default=None,
        help=f"Scenarios to run. Default: {sorted(SCENARIOS)}",
    )
    parser.add_argument(
        "--output-root",
        default=".",
        help="Directory where FINAL_OUTPUT_<scenario>_seed<N>_<timestamp> dirs are created.",
    )
    parser.add_argument(
        "--summary-csv",
        default="multiseed_summary.csv",
        help="Per-run summary CSV (relative to repo root unless absolute).",
    )
    parser.add_argument("--model-dir", default=DEFAULT_MODEL_DIR, help="Path to GBDT model directory.")
    parser.add_argument("--controller-preset", default=DEFAULT_CONTROLLER_PRESET, help="ML controller preset.")
    parser.add_argument("--broker-preset", default=DEFAULT_BROKER_PRESET, help="Forecasting broker preset.")
    parser.add_argument(
        "--keep-raw",
        action="store_true",
        help="Keep temporary raw comparison folders under logs/raw_runs.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    repo_root = _repo_root()

    seeds = _select_seeds(args.seeds)
    scenarios = _select_scenarios(args.scenarios)
    total_runs = len(seeds) * len(scenarios)

    print("\n" + "=" * 78)
    print(f" Multi-seed run: {len(seeds)} seed(s) x {len(scenarios)} scenario(s) = {total_runs} runs")
    print(f"   Seeds:     {seeds}")
    print(f"   Scenarios: {scenarios}")
    print("=" * 78)

    records: list[dict] = []
    failures: list[dict] = []
    overall_t0 = time.time()
    run_idx = 0

    for seed_idx, seed in enumerate(seeds, start=1):
        seed_t0 = time.time()
        print(f"\n--- Seed {seed} ({seed_idx}/{len(seeds)}) ---")
        seed_records: list[dict] = []

        for scenario in scenarios:
            run_idx += 1
            print(f"  [{run_idx}/{total_runs}] Running {scenario} (seed={seed}) ...")
            try:
                output_dir, elapsed = _run_one(scenario, seed, args)
            except subprocess.CalledProcessError as exc:
                print(f"  [FAIL] {scenario} seed={seed}: exit code {exc.returncode}")
                failures.append({"scenario": scenario, "seed": seed, "returncode": exc.returncode})
                continue

            kpi = _read_global_kpi(output_dir)
            rec = {
                "scenario": scenario,
                "seed": seed,
                "output_dir": str(output_dir),
                "kpi": kpi,
                "elapsed": elapsed,
            }
            records.append(rec)
            seed_records.append(rec)
            print(f"  [OK]   {scenario} seed={seed} ({_format_duration(elapsed)})")
            print(f"         {_format_kpi_line(kpi)}")
            print(f"         output: {output_dir.name}")

        seed_elapsed = time.time() - seed_t0
        print(f"  Seed {seed} done: {len(seed_records)}/{len(scenarios)} scenarios in {_format_duration(seed_elapsed)}")

    overall_elapsed = time.time() - overall_t0
    print(f"\n{'=' * 78}")
    print(f" Completed {len(records)}/{total_runs} runs in {_format_duration(overall_elapsed)}")
    if failures:
        print(f" Failures: {len(failures)} -> {failures}")
    print("=" * 78)

    if not records:
        print("\nNo successful runs to aggregate.")
        return

    summary = _aggregate(records)
    _print_aggregate(summary)

    summary_csv = Path(args.summary_csv)
    if not summary_csv.is_absolute():
        summary_csv = repo_root / summary_csv
    aggregate_path = _write_summary_csv(records, summary, summary_csv)
    print(f"\nWrote per-run summary: {summary_csv}")
    print(f"Wrote aggregate stats:  {aggregate_path}")


if __name__ == "__main__":
    main()
