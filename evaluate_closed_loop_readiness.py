from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from compare_baseline_vs_ml import _global_metric_summary, _per_slice_comparison_table, _per_slice_summary
from integration.closed_loop_runner import run_online_baseline, run_online_closed_loop


DEFAULT_SCENARIOS = ("medium", "heavy")
DEFAULT_SEEDS = (7, 42, 123)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _resolve_config_path(repo_root: Path, scenario: str) -> Path:
    scenario_path = Path(scenario)
    if scenario_path.exists():
        return scenario_path
    candidates = [
        repo_root / "slicesim" / f"scenario-{scenario}-output.yml",
        repo_root / "slicesim" / f"scenario-{scenario}.yml",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _read_csv(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path)


def _run_pair(
    config_path: Path,
    sla_path: Path,
    model_dir: Path,
    controller_type: str,
    controller_preset: str,
    use_broker: bool,
    broker_preset: str,
    seed: int,
    output_dir: Path,
) -> tuple[dict, pd.DataFrame]:
    baseline_paths = run_online_baseline(
        config_path=config_path,
        sla_path=sla_path,
        output_dir=output_dir / "baseline",
        seed=seed,
    )
    ml_paths = run_online_closed_loop(
        config_path=config_path,
        sla_path=sla_path,
        model_dir=model_dir,
        output_dir=output_dir / "ml",
        seed=seed,
        controller_type=controller_type,
        controller_preset=controller_preset,
        use_broker=use_broker,
        broker_preset=broker_preset,
    )

    baseline_state = _read_csv(baseline_paths["raw_state_path"])
    ml_state = _read_csv(ml_paths["raw_state_path"])
    baseline_client_summary = _read_csv(baseline_paths["client_summary_path"])
    ml_client_summary = _read_csv(ml_paths["client_summary_path"])
    baseline_completion = _read_csv(baseline_paths["slice_completion_latency_path"])
    ml_completion = _read_csv(ml_paths["slice_completion_latency_path"])
    baseline_first = _read_csv(baseline_paths["slice_first_service_latency_path"])
    ml_first = _read_csv(ml_paths["slice_first_service_latency_path"])

    baseline_global = _global_metric_summary(baseline_state)
    ml_global = _global_metric_summary(ml_state)

    baseline_per_slice = _per_slice_summary(
        baseline_state,
        baseline_client_summary,
        baseline_completion,
        baseline_first,
    )
    ml_per_slice = _per_slice_summary(
        ml_state,
        ml_client_summary,
        ml_completion,
        ml_first,
    )
    per_slice_comparison = _per_slice_comparison_table(baseline_per_slice, ml_per_slice)

    return {
        "baseline_global": baseline_global,
        "ml_global": ml_global,
        "baseline_paths": {key: str(value) for key, value in baseline_paths.items()},
        "ml_paths": {key: str(value) for key, value in ml_paths.items()},
    }, per_slice_comparison


def _build_global_row(
    scenario: str,
    seed: int,
    baseline_global: dict[str, float],
    ml_global: dict[str, float],
) -> dict[str, float | int | str]:
    metrics = [
        "connected_clients_ratio",
        "coverage_ratio",
        "block_ratio",
        "avg_slice_load_ratio",
        "avg_latency_ms",
        "p95_latency_ms",
        "latency_violation_ratio",
        "avg_state_sla_violation_share",
        "total_bandwidth_usage",
    ]
    row: dict[str, float | int | str] = {"scenario": scenario, "seed": int(seed)}
    for metric in metrics:
        baseline_value = float(baseline_global.get(metric, 0.0))
        ml_value = float(ml_global.get(metric, 0.0))
        row[f"{metric}_baseline"] = baseline_value
        row[f"{metric}_ml"] = ml_value
        row[f"{metric}_delta"] = ml_value - baseline_value
    return row


def _mean_std_summary(frame: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    numeric_columns = [
        column
        for column in frame.columns
        if column not in set(group_columns + ["seed"]) and pd.api.types.is_numeric_dtype(frame[column])
    ]
    if not numeric_columns:
        return frame[group_columns].drop_duplicates().reset_index(drop=True)
    grouped = frame.groupby(group_columns, as_index=False)
    mean_frame = grouped[numeric_columns].mean().rename(
        columns={column: f"{column}_mean" for column in numeric_columns}
    )
    std_frame = grouped[numeric_columns].std(ddof=1).fillna(0.0).rename(
        columns={column: f"{column}_std" for column in numeric_columns}
    )
    return mean_frame.merge(std_frame, on=group_columns, how="left")


def _scenario_summary(global_frame: pd.DataFrame, per_slice_frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    global_summary = (
        _mean_std_summary(global_frame, ["scenario"])
        .sort_values("scenario")
        .reset_index(drop=True)
    )
    global_seed_counts = (
        global_frame.groupby("scenario", as_index=False)["seed"]
        .nunique()
        .rename(columns={"seed": "num_seeds"})
    )
    global_summary = global_seed_counts.merge(global_summary, on="scenario", how="left")

    per_slice_summary = (
        _mean_std_summary(per_slice_frame, ["scenario", "slice_name"])
        .sort_values(["scenario", "slice_name"])
        .reset_index(drop=True)
    )
    per_slice_seed_counts = (
        per_slice_frame.groupby(["scenario", "slice_name"], as_index=False)["seed"]
        .nunique()
        .rename(columns={"seed": "num_seeds"})
    )
    per_slice_summary = per_slice_seed_counts.merge(
        per_slice_summary,
        on=["scenario", "slice_name"],
        how="left",
    )
    return global_summary, per_slice_summary


def _evaluate_gate(global_summary: pd.DataFrame, per_slice_summary: pd.DataFrame) -> tuple[bool, list[str]]:
    notes: list[str] = []
    ready = True
    per_slice_index = per_slice_summary.set_index(["scenario", "slice_name"]) if not per_slice_summary.empty else None

    for _, row in global_summary.iterrows():
        scenario = row["scenario"]
        latency_delta = float(row["avg_latency_ms_delta_mean"])
        block_delta = float(row["block_ratio_delta_mean"])
        if latency_delta > 0:
            ready = False
            notes.append(f"{scenario}: ML does not improve global average latency ({latency_delta:+.3f} ms mean).")
        else:
            notes.append(f"{scenario}: ML improves global average latency by {-latency_delta:.3f} ms mean.")
        if block_delta > 0:
            ready = False
            notes.append(f"{scenario}: ML does not reduce block ratio ({block_delta:+.4f} mean).")
        else:
            notes.append(f"{scenario}: ML reduces block ratio by {-block_delta:.4f} mean.")

        if per_slice_index is not None and (scenario, "URLLC") in per_slice_index.index:
            urllc_row = per_slice_index.loc[(scenario, "URLLC")]
            metric_name = "avg_recorded_first_service_latency_ms_delta"
            if metric_name not in urllc_row.index:
                metric_name = "avg_first_service_latency_ms_delta"
            metric_mean_name = f"{metric_name}_mean"
            if metric_mean_name in urllc_row.index:
                metric_name = metric_mean_name
            urllc_first_service_delta = float(urllc_row[metric_name])
            if urllc_first_service_delta > 0:
                ready = False
                notes.append(
                    f"{scenario}: URLLC first-service latency is worse than baseline ({urllc_first_service_delta:+.3f} ms, metric={metric_name})."
                )
            else:
                notes.append(
                    f"{scenario}: URLLC first-service latency improves by {-urllc_first_service_delta:.3f} ms (metric={metric_name})."
                )

    if ready:
        notes.insert(0, "Closed-loop readiness gate passed for the tested scenarios and seeds.")
    else:
        notes.insert(0, "Closed-loop readiness gate not passed yet; the controller still needs improvement.")
    return ready, notes


def _write_markdown_table(frame: pd.DataFrame, float_digits: int = 4) -> str:
    if frame.empty:
        return "| _Empty_ |\n|---|\n| _No data_ |"
    display = frame.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: f"{value:.{float_digits}f}")
    header = "| " + " | ".join(display.columns) + " |"
    separator = "|" + "|".join(["---"] * len(display.columns)) + "|"
    rows = ["| " + " | ".join(str(value) for value in row) + " |" for row in display.itertuples(index=False, name=None)]
    return "\n".join([header, separator] + rows)


def _write_report(
    output_dir: Path,
    report_payload: dict,
    global_summary: pd.DataFrame,
    per_slice_summary: pd.DataFrame,
) -> tuple[Path, Path]:
    json_path = output_dir / "closed_loop_readiness_report.json"
    md_path = output_dir / "closed_loop_readiness_report.md"
    json_path.write_text(json.dumps(report_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    notes_md = "\n".join(f"- {line}" for line in report_payload["notes"])
    md_text = f"""# Closed-Loop Readiness Report

## Run Summary

- Timestamp: `{report_payload['run']['timestamp']}`
- Scenarios: `{", ".join(report_payload['run']['scenarios'])}`
- Controller preset: `{report_payload['run']['controller_preset']}`
- Model: `{report_payload['run']['model_dir']}`
- Seeds: `{", ".join(str(seed) for seed in report_payload['run']['seeds'])}`

## Readiness Gate

- Ready: `{report_payload['readiness']['ready']}`

## Scenario-Level Summary

Columns ending in `_mean` and `_std` report mean and sample standard deviation across seeds.

{_write_markdown_table(global_summary, float_digits=4)}

## Scenario + Slice Summary

Columns ending in `_mean` and `_std` report mean and sample standard deviation across seeds.

{_write_markdown_table(per_slice_summary, float_digits=4)}

## Notes

{notes_md}
"""
    md_path.write_text(md_text, encoding="utf-8")
    return json_path, md_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate closed-loop readiness by comparing baseline vs ML across scenarios and seeds."
    )
    parser.add_argument(
        "--scenarios",
        nargs="+",
        default=list(DEFAULT_SCENARIOS),
        help="Scenarios to evaluate. Default: medium heavy",
    )
    parser.add_argument(
        "--sla-path",
        default=str(_repo_root() / "sla_reference_table.csv"),
        help="Path to the SLA reference CSV.",
    )
    parser.add_argument("--model-dir", required=True, help="Path to the trained GBDT model directory.")
    parser.add_argument(
        "--controller-type",
        default="gbdt",
        choices=["gbdt", "admm"],
        help="Controller implementation used by the ML run. Default: gbdt",
    )
    parser.add_argument("--controller-preset", default="balanced", help="ML controller preset. Default: balanced")
    parser.add_argument("--use-broker", action="store_true", help="Enable the forecasting-aware slice broker.")
    parser.add_argument(
        "--broker-preset",
        default="forecasting_balanced",
        help="Broker preset used when --use-broker is enabled.",
    )
    parser.add_argument(
        "--seeds",
        nargs="+",
        type=int,
        default=list(DEFAULT_SEEDS),
        help="Seeds used for stability checks. Default: 7 42 123",
    )
    parser.add_argument("--output-dir", help="Directory for evaluation artifacts.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    logging.getLogger().setLevel(logging.ERROR)

    repo_root = _repo_root()
    sla_path = Path(args.sla_path)
    model_dir = Path(args.model_dir)
    if not sla_path.exists():
        raise FileNotFoundError(f"Missing SLA reference file: {sla_path}")
    if not model_dir.exists():
        raise FileNotFoundError(f"Missing model directory: {model_dir}")

    output_dir = Path(args.output_dir) if args.output_dir else (
        repo_root / "artifacts" / "closed_loop_readiness" / f"{args.controller_preset}_{_timestamp()}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    global_rows: list[dict] = []
    per_slice_frames: list[pd.DataFrame] = []
    run_artifacts: dict[str, dict[str, dict[str, str]]] = {}

    for scenario in args.scenarios:
        config_path = _resolve_config_path(repo_root, scenario)
        if not config_path.exists():
            raise FileNotFoundError(f"Missing scenario config: {config_path}")

        run_artifacts[scenario] = {}
        for seed in args.seeds:
            print(f"Running closed-loop readiness pair for scenario={scenario}, seed={seed} ...")
            run_payload, per_slice_comparison = _run_pair(
                config_path=config_path,
                sla_path=sla_path,
                model_dir=model_dir,
                controller_type=args.controller_type,
                controller_preset=args.controller_preset,
                use_broker=args.use_broker,
                broker_preset=args.broker_preset,
                seed=seed,
                output_dir=output_dir / scenario / f"seed_{seed}",
            )
            global_rows.append(
                _build_global_row(
                    scenario=scenario,
                    seed=seed,
                    baseline_global=run_payload["baseline_global"],
                    ml_global=run_payload["ml_global"],
                )
            )
            per_slice_comparison.insert(0, "seed", seed)
            per_slice_comparison.insert(0, "scenario", scenario)
            per_slice_frames.append(per_slice_comparison)
            run_artifacts[scenario][str(seed)] = {
                "baseline": run_payload["baseline_paths"],
                "ml": run_payload["ml_paths"],
            }

    global_frame = pd.DataFrame(global_rows)
    per_slice_frame = pd.concat(per_slice_frames, ignore_index=True) if per_slice_frames else pd.DataFrame()

    per_run_global_csv = output_dir / "closed_loop_per_run_global.csv"
    per_run_slice_csv = output_dir / "closed_loop_per_run_per_slice.csv"
    global_frame.to_csv(per_run_global_csv, index=False)
    per_slice_frame.to_csv(per_run_slice_csv, index=False)

    global_summary, per_slice_summary = _scenario_summary(global_frame, per_slice_frame)
    global_summary_csv = output_dir / "closed_loop_scenario_summary.csv"
    per_slice_summary_csv = output_dir / "closed_loop_scenario_slice_summary.csv"
    global_summary.to_csv(global_summary_csv, index=False)
    per_slice_summary.to_csv(per_slice_summary_csv, index=False)

    ready, notes = _evaluate_gate(global_summary, per_slice_summary)
    report_payload = {
        "run": {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "scenarios": args.scenarios,
            "controller_preset": args.controller_preset,
            "controller_type": args.controller_type,
            "use_broker": bool(args.use_broker),
            "broker_preset": args.broker_preset if args.use_broker else None,
            "model_dir": str(model_dir),
            "seeds": [int(seed) for seed in args.seeds],
        },
        "readiness": {
            "ready": bool(ready),
        },
        "artifacts": {
            "per_run_global_csv": str(per_run_global_csv),
            "per_run_slice_csv": str(per_run_slice_csv),
            "scenario_summary_csv": str(global_summary_csv),
            "scenario_slice_summary_csv": str(per_slice_summary_csv),
            "runs": run_artifacts,
        },
        "notes": notes,
    }
    json_path, md_path = _write_report(output_dir, report_payload, global_summary, per_slice_summary)

    print("\nClosed-loop readiness evaluation completed.")
    print(f"- Per-run global CSV: {per_run_global_csv}")
    print(f"- Per-run per-slice CSV: {per_run_slice_csv}")
    print(f"- Scenario summary CSV: {global_summary_csv}")
    print(f"- Scenario slice summary CSV: {per_slice_summary_csv}")
    print(f"- Report JSON: {json_path}")
    print(f"- Report Markdown: {md_path}")
    print(f"- Ready: {ready}")


if __name__ == "__main__":
    main()
