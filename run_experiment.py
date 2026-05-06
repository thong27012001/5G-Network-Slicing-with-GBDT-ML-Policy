from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import pandas as pd


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
SLICE_ORDER = ["URLLC", "eMBB", "mMTC"]


def _repo_root() -> Path:
    return Path(__file__).resolve().parent


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _select_scenario(cli_value: str | None) -> str:
    if cli_value:
        return cli_value

    print("Select a scenario:")
    for index, (name, config) in enumerate(SCENARIOS.items(), start=1):
        print(f"  {index}. {name} - {config['description']}")

    while True:
        value = input("Enter 1/2 or scenario name [light]: ").strip() or "light"
        if value in SCENARIOS:
            return value
        if value.isdigit():
            index = int(value)
            names = list(SCENARIOS)
            if 1 <= index <= len(names):
                return names[index - 1]
        print("Invalid scenario. Choose 'light' or 'heavy'.")


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame[column], errors="coerce")


def _sla_hit_summary(
    baseline_clients: pd.DataFrame,
    ml_clients: pd.DataFrame,
) -> pd.DataFrame:
    baseline = baseline_clients.copy()
    ml = ml_clients.copy()
    for frame in (baseline, ml):
        frame["avg_completion_latency_ms"] = _numeric(frame, "avg_completion_latency_ms")
        frame["completion_ratio"] = _numeric(frame, "completion_ratio")

    delay_thresholds = (
        baseline.groupby("slice_name")["avg_completion_latency_ms"]
        .quantile(0.75)
        .reindex(SLICE_ORDER)
    )

    rows: list[dict[str, float | str]] = []
    for slice_name in SLICE_ORDER:
        base_slice = baseline[baseline["slice_name"] == slice_name]
        ml_slice = ml[ml["slice_name"] == slice_name]
        threshold = float(delay_thresholds.get(slice_name, 0.0) or 0.0)
        base_delay_hit = float((base_slice["avg_completion_latency_ms"] <= threshold).mean()) if not base_slice.empty else 0.0
        ml_delay_hit = float((ml_slice["avg_completion_latency_ms"] <= threshold).mean()) if not ml_slice.empty else 0.0
        base_throughput_hit = float((base_slice["completion_ratio"] >= 0.95).mean()) if not base_slice.empty else 0.0
        ml_throughput_hit = float((ml_slice["completion_ratio"] >= 0.95).mean()) if not ml_slice.empty else 0.0

        rows.append(
            {
                "metric": "delay_hit_percentage",
                "slice_name": slice_name,
                "baseline": base_delay_hit,
                "ml_policy": ml_delay_hit,
                "threshold": threshold,
                "threshold_unit": "ms",
                "rule": "avg_completion_latency_ms <= baseline_p75_by_slice",
            }
        )
        rows.append(
            {
                "metric": "throughput_sla_hit_percentage",
                "slice_name": slice_name,
                "baseline": base_throughput_hit,
                "ml_policy": ml_throughput_hit,
                "threshold": 0.95,
                "threshold_unit": "ratio",
                "rule": "completion_ratio >= 0.95",
            }
        )
    return pd.DataFrame(rows)


def _plot_hit_bars(
    summary: pd.DataFrame,
    metric: str,
    title: str,
    y_label: str,
    footnote: str,
    output_path: Path,
) -> None:
    plot_frame = summary[summary["metric"] == metric].set_index("slice_name").reindex(SLICE_ORDER)
    x = range(len(SLICE_ORDER))
    width = 0.35

    fig, ax = plt.subplots(figsize=(9.5, 6.0))
    baseline_values = plot_frame["baseline"].fillna(0.0).astype(float).tolist()
    ml_values = plot_frame["ml_policy"].fillna(0.0).astype(float).tolist()

    ax.bar(
        [value - width / 2 for value in x],
        baseline_values,
        width,
        label="Baseline",
        color="#df3f3f",
        hatch="...",
        edgecolor="white",
        linewidth=1.2,
    )
    ax.bar(
        [value + width / 2 for value in x],
        ml_values,
        width,
        label="ML Policy",
        color="#2f8ccf",
        hatch="xx",
        edgecolor="white",
        linewidth=1.2,
    )

    for xpos, value in zip([value - width / 2 for value in x], baseline_values):
        ax.text(xpos, min(value + 0.02, 1.08), f"{value:.2f}", ha="center", va="bottom", fontsize=10)
    for xpos, value in zip([value + width / 2 for value in x], ml_values):
        ax.text(xpos, min(value + 0.02, 1.08), f"{value:.2f}", ha="center", va="bottom", fontsize=10)

    ax.set_title(title, fontsize=17, pad=8)
    ax.set_xlabel("Slice Type")
    ax.set_ylabel(y_label)
    ax.set_xticks(list(x))
    ax.set_xticklabels(SLICE_ORDER)
    ax.set_ylim(0.0, 1.10)
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    ax.legend(loc="upper left")
    fig.text(0.5, 0.02, footnote, ha="center", va="center", color="#666666", fontsize=9)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(output_path, dpi=220)
    plt.close(fig)


def _generate_sla_hit_outputs(output_dir: Path) -> None:
    baseline_clients = pd.read_csv(output_dir / "baseline_run" / "baseline_client_summary.csv")
    ml_clients = pd.read_csv(output_dir / "ml_run" / "online_client_summary.csv")
    summary = _sla_hit_summary(baseline_clients, ml_clients)
    summary.to_csv(output_dir / "sla_hit_summary.csv", index=False)

    delay_thresholds = (
        summary[summary["metric"] == "delay_hit_percentage"]
        .set_index("slice_name")["threshold"]
        .reindex(SLICE_ORDER)
    )
    threshold_text = ", ".join(
        f"{slice_name}={float(delay_thresholds[slice_name]):.3f}ms"
        for slice_name in SLICE_ORDER
        if pd.notna(delay_thresholds[slice_name])
    )
    _plot_hit_bars(
        summary,
        metric="delay_hit_percentage",
        title="Delay Hit Percentage",
        y_label="Delay Hit Percentage",
        footnote=f"Hit per UE: avg_completion_latency_ms <= baseline p75 threshold; thresholds: {threshold_text}",
        output_path=output_dir / "delay_hit_percentage.png",
    )
    _plot_hit_bars(
        summary,
        metric="throughput_sla_hit_percentage",
        title="Throughput SLA Hit Percentage",
        y_label="Throughput SLA Hit Percentage",
        footnote="Hit per UE: completion_ratio >= 0.95",
        output_path=output_dir / "throughput_sla_hit_percentage.png",
    )


def _copy_map_shortcuts(output_dir: Path) -> None:
    shortcuts = {
        output_dir / "baseline_run" / "baseline_simulation.png": output_dir / "baseline_simulation_map.png",
        output_dir / "ml_run" / "ml_policy_simulation.png": output_dir / "ml_policy_simulation_map.png",
    }
    for source, target in shortcuts.items():
        if source.exists():
            shutil.copy2(source, target)


def _write_run_summary(output_dir: Path, scenario: str, command: list[str]) -> None:
    text = [
        f"# Experiment Output: {scenario}",
        "",
        "This folder was generated by `run_experiment.py`.",
        "",
        "## Command",
        "",
        "```text",
        " ".join(command),
        "```",
        "",
        "## Key files",
        "",
        "- `baseline_simulation_map.png`: baseline simulation map and KPI charts.",
        "- `ml_policy_simulation_map.png`: ML closed-loop simulation map and KPI charts.",
        "- `baseline_vs_ml_global_kpis.png`: global KPI comparison.",
        "- `baseline_vs_ml_per_slice_bars.png`: per-slice KPI comparison.",
        "- `delay_hit_percentage.png`: delay SLA hit percentage by slice.",
        "- `throughput_sla_hit_percentage.png`: throughput SLA hit percentage by slice.",
        "- `global_kpi_comparison.csv`: global metric table.",
        "- `per_slice_comparison.csv`: per-slice metric table.",
        "- `sla_hit_summary.csv`: source data for the SLA hit plots.",
        "- `baseline_vs_ml_report.md`: detailed generated comparison report.",
        "",
    ]
    (output_dir / "RUN_SUMMARY.md").write_text("\n".join(text), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run baseline vs ML policy simulation for one release scenario.")
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), help="Scenario to run. If omitted, prompts interactively.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed shared by baseline and ML runs.")
    parser.add_argument("--output-root", default=".", help="Directory where FINAL_OUTPUT_<scenario>_<timestamp> is created.")
    parser.add_argument("--model-dir", default=DEFAULT_MODEL_DIR, help="Path to the trained SLA-risk GBDT model directory.")
    parser.add_argument("--controller-preset", default=DEFAULT_CONTROLLER_PRESET, help="ML controller preset.")
    parser.add_argument("--broker-preset", default=DEFAULT_BROKER_PRESET, help="Forecasting broker preset.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    repo_root = _repo_root()
    scenario = _select_scenario(args.scenario)
    scenario_config = SCENARIOS[scenario]

    output_root = Path(args.output_root)
    if not output_root.is_absolute():
        output_root = repo_root / output_root
    output_dir = output_root / f"FINAL_OUTPUT_{scenario}_{_timestamp()}"
    output_dir.mkdir(parents=True, exist_ok=False)

    command = [
        sys.executable,
        str(repo_root / "compare_baseline_vs_ml.py"),
        "--config",
        str(repo_root / scenario_config["config"]),
        "--sla-path",
        str(repo_root / scenario_config["sla"]),
        "--model-dir",
        str(repo_root / args.model_dir),
        "--controller-type",
        "gbdt",
        "--controller-preset",
        args.controller_preset,
        "--use-broker",
        "--broker-preset",
        args.broker_preset,
        "--seed",
        str(args.seed),
        "--output-dir",
        str(output_dir),
        "--pipeline-output-root",
        "",
    ]

    print(f"Running scenario: {scenario}")
    print(f"Output folder: {output_dir}")
    subprocess.run(command, cwd=repo_root, check=True)
    _copy_map_shortcuts(output_dir)
    _generate_sla_hit_outputs(output_dir)
    _write_run_summary(output_dir, scenario, command)
    print("\nExperiment completed.")
    print(f"Final output: {output_dir}")


if __name__ == "__main__":
    main()
