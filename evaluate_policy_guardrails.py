from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd


SLICE_ORDER = ["URLLC", "eMBB", "mMTC"]
STRICT_GUARDRAIL_KWARGS = {
    "max_block_delta": 0.0,
    "max_connected_drop": 0.01,
    "max_bandwidth_drop_pct": 0.0,
    "max_avg_latency_regression_pct": 2.0,
    "max_p95_latency_regression_pct": 0.0,
    "max_latency_violation_ratio_delta": 0.0,
    "max_state_sla_violation_delta": None,
    "max_completion_drop_by_slice": {"URLLC": 0.005, "eMBB": 0.0, "mMTC": 0.005},
    "max_request_latency_violation_drop_by_slice": {"URLLC": 0.0, "eMBB": 0.0, "mMTC": 0.0},
    "max_urllc_latency_regression_pct": 0.0,
    "min_sla_margin_improvement_pct": None,
    "require_sla_margin_improvement": False,
}


def _metric_row(frame: pd.DataFrame, metric: str) -> pd.Series:
    rows = frame[frame["metric"] == metric]
    if rows.empty:
        raise KeyError(f"Metric not found in global comparison: {metric}")
    return rows.iloc[0]


def _slice_row(frame: pd.DataFrame, slice_name: str) -> pd.Series:
    rows = frame[frame["slice_name"] == slice_name]
    if rows.empty:
        raise KeyError(f"Slice not found in per-slice comparison: {slice_name}")
    return rows.iloc[0]


def _add_check(checks: list[dict], name: str, value: float, threshold: float, passed: bool, note: str) -> None:
    checks.append(
        {
            "name": name,
            "value": float(value),
            "threshold": float(threshold),
            "passed": bool(passed),
            "note": note,
        }
    )


def evaluate_guardrails(
    comparison_dir: Path,
    *,
    max_block_delta: float = 0.05,
    max_connected_drop: float = 0.03,
    max_bandwidth_drop_pct: float = 10.0,
    max_avg_latency_regression_pct: float = 10.0,
    max_p95_latency_regression_pct: float = 50.0,
    max_latency_violation_ratio_delta: float | None = 0.05,
    max_state_sla_violation_delta: float | None = 0.05,
    max_completion_drop_by_slice: dict[str, float] | None = None,
    max_request_latency_violation_drop_by_slice: dict[str, float] | None = None,
    max_urllc_latency_regression_pct: float = 10.0,
    min_sla_margin_improvement_pct: float | None = None,
    require_sla_margin_improvement: bool = False,
) -> dict:
    global_path = comparison_dir / "global_kpi_comparison.csv"
    per_slice_path = comparison_dir / "per_slice_comparison.csv"
    if not global_path.exists():
        raise FileNotFoundError(global_path)
    if not per_slice_path.exists():
        raise FileNotFoundError(per_slice_path)

    global_frame = pd.read_csv(global_path)
    per_slice_frame = pd.read_csv(per_slice_path)
    checks: list[dict] = []

    block = _metric_row(global_frame, "block_ratio")
    block_delta = float(block["delta_ml_minus_baseline"])
    _add_check(
        checks,
        "global_block_ratio_delta",
        block_delta,
        max_block_delta,
        block_delta <= max_block_delta,
        "ML should not create a large admission-blocking penalty.",
    )

    connected = _metric_row(global_frame, "connected_clients_ratio")
    connected_delta = float(connected["delta_ml_minus_baseline"])
    _add_check(
        checks,
        "global_connected_clients_delta",
        connected_delta,
        -max_connected_drop,
        connected_delta >= -max_connected_drop,
        "ML should not disconnect noticeably more clients than baseline.",
    )

    bandwidth = _metric_row(global_frame, "total_bandwidth_usage")
    bandwidth_delta_pct = float(bandwidth["delta_pct"])
    _add_check(
        checks,
        "global_total_bandwidth_delta_pct",
        bandwidth_delta_pct,
        -max_bandwidth_drop_pct,
        bandwidth_delta_pct >= -max_bandwidth_drop_pct,
        "ML should preserve most system throughput while optimizing latency/SLA.",
    )

    avg_latency = _metric_row(global_frame, "avg_latency_ms")
    avg_latency_delta_pct = float(avg_latency["delta_pct"])
    _add_check(
        checks,
        "global_avg_latency_delta_pct",
        avg_latency_delta_pct,
        max_avg_latency_regression_pct,
        avg_latency_delta_pct <= max_avg_latency_regression_pct,
        "ML should not increase average latency beyond the accepted bound.",
    )

    p95_latency = _metric_row(global_frame, "p95_latency_ms")
    p95_latency_delta_pct = float(p95_latency["delta_pct"])
    _add_check(
        checks,
        "global_p95_latency_delta_pct",
        p95_latency_delta_pct,
        max_p95_latency_regression_pct,
        p95_latency_delta_pct <= max_p95_latency_regression_pct,
        "ML should not worsen latency tail beyond the accepted bound.",
    )

    if max_latency_violation_ratio_delta is not None:
        latency_violation = _metric_row(global_frame, "latency_violation_ratio")
        latency_violation_delta = float(latency_violation["delta_ml_minus_baseline"])
        _add_check(
            checks,
            "global_latency_violation_ratio_delta",
            latency_violation_delta,
            max_latency_violation_ratio_delta,
            latency_violation_delta <= max_latency_violation_ratio_delta,
            "Actual latency-violation ratio should not increase.",
        )

    if max_state_sla_violation_delta is not None:
        state_sla = _metric_row(global_frame, "avg_state_sla_violation_share")
        state_sla_delta = float(state_sla["delta_ml_minus_baseline"])
        _add_check(
            checks,
            "global_state_sla_violation_delta",
            state_sla_delta,
            max_state_sla_violation_delta,
            state_sla_delta <= max_state_sla_violation_delta,
            "State-level SLA label share should not increase beyond the accepted bound.",
        )

    if max_completion_drop_by_slice is None:
        max_completion_drop_by_slice = {"URLLC": 0.005, "eMBB": 0.03, "mMTC": 0.03}
    if max_request_latency_violation_drop_by_slice is None:
        max_request_latency_violation_drop_by_slice = {}

    for slice_name in SLICE_ORDER:
        slice_row = _slice_row(per_slice_frame, slice_name)
        max_completion_drop = max_completion_drop_by_slice.get(slice_name, 0.03)
        completion_delta = float(slice_row["completion_ratio_ml"] - slice_row["completion_ratio_baseline"])
        _add_check(
            checks,
            f"{slice_name.lower()}_completion_ratio_delta",
            completion_delta,
            -max_completion_drop,
            completion_delta >= -max_completion_drop,
            f"{slice_name} completion ratio should not regress beyond the accepted bound.",
        )
        if slice_name in max_request_latency_violation_drop_by_slice:
            max_latency_violation_delta = max_request_latency_violation_drop_by_slice[slice_name]
            latency_violation_delta = float(slice_row["request_latency_violation_event_ratio_delta"])
            _add_check(
                checks,
                f"{slice_name.lower()}_request_latency_violation_ratio_delta",
                latency_violation_delta,
                max_latency_violation_delta,
                latency_violation_delta <= max_latency_violation_delta,
                f"{slice_name} request latency-violation event ratio should not increase.",
            )

    urllc = _slice_row(per_slice_frame, "URLLC")
    urllc_latency_baseline = float(urllc["avg_completion_latency_ms_baseline"])
    urllc_latency_ml = float(urllc["avg_completion_latency_ms_ml"])
    if abs(urllc_latency_baseline) < 1e-12:
        urllc_latency_delta_pct = 0.0 if abs(urllc_latency_ml) < 1e-12 else 100.0
    else:
        urllc_latency_delta_pct = (urllc_latency_ml - urllc_latency_baseline) / abs(urllc_latency_baseline) * 100.0
    _add_check(
        checks,
        "urllc_completion_latency_delta_pct",
        urllc_latency_delta_pct,
        max_urllc_latency_regression_pct,
        urllc_latency_delta_pct <= max_urllc_latency_regression_pct,
        "URLLC latency should not regress materially.",
    )

    if require_sla_margin_improvement or min_sla_margin_improvement_pct is not None:
        if min_sla_margin_improvement_pct is None:
            min_sla_margin_improvement_pct = 0.0
        has_margin_column = "avg_sla_safety_margin_improvement_pct" in per_slice_frame.columns
        for slice_name in SLICE_ORDER:
            if has_margin_column:
                slice_row = _slice_row(per_slice_frame, slice_name)
                margin_improvement = float(slice_row["avg_sla_safety_margin_improvement_pct"])
                passed = (
                    margin_improvement > min_sla_margin_improvement_pct
                    if require_sla_margin_improvement
                    else margin_improvement >= min_sla_margin_improvement_pct
                )
            else:
                margin_improvement = float("nan")
                passed = False
            _add_check(
                checks,
                f"{slice_name.lower()}_sla_safety_margin_improvement_pct",
                margin_improvement,
                min_sla_margin_improvement_pct,
                passed,
                f"{slice_name} SLA safety margin must improve versus baseline.",
            )

    passed = all(check["passed"] for check in checks)
    return {
        "run": {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "comparison_dir": str(comparison_dir),
        },
        "passed": passed,
        "checks": checks,
    }


def evaluate_strict_guardrails(comparison_dir: Path) -> dict:
    return evaluate_guardrails(comparison_dir, **STRICT_GUARDRAIL_KWARGS)


def _write_report(comparison_dir: Path, payload: dict) -> tuple[Path, Path]:
    json_path = comparison_dir / "policy_guardrail_report.json"
    md_path = comparison_dir / "policy_guardrail_report.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    rows = [
        "| Check | Value | Threshold | Pass | Note |",
        "|---|---:|---:|---|---|",
    ]
    for check in payload["checks"]:
        rows.append(
            "| {name} | {value:.4f} | {threshold:.4f} | {passed} | {note} |".format(
                name=check["name"],
                value=float(check["value"]),
                threshold=float(check["threshold"]),
                passed="PASS" if check["passed"] else "FAIL",
                note=check["note"],
            )
        )

    md_text = "\n".join(
        [
            "# Policy Guardrail Report",
            "",
            f"- Comparison dir: `{payload['run']['comparison_dir']}`",
            f"- Passed: `{payload['passed']}`",
            "",
            *rows,
            "",
        ]
    )
    md_path.write_text(md_text, encoding="utf-8")
    return json_path, md_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate closed-loop ML policy guardrails from comparison CSV files.")
    parser.add_argument("--comparison-dir", required=True, help="Directory containing global/per-slice comparison CSVs.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Require SLA improvement and no regression on throughput, latency, block, connected, and completion KPIs.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    comparison_dir = Path(args.comparison_dir)
    if args.strict:
        payload = evaluate_strict_guardrails(comparison_dir)
    else:
        payload = evaluate_guardrails(comparison_dir)
    json_path, md_path = _write_report(comparison_dir, payload)
    print(f"passed={payload['passed']}")
    for check in payload["checks"]:
        status = "PASS" if check["passed"] else "FAIL"
        print(f"{status} {check['name']}: value={check['value']:.4f}, threshold={check['threshold']:.4f}")
    print(f"json={json_path}")
    print(f"markdown={md_path}")


if __name__ == "__main__":
    main()
