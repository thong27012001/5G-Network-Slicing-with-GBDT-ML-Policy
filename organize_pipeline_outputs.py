from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


PIPELINE_FOLDERS = {
    "simulation": "01_output_simulation",
    "model": "02_model_training_report_plot",
    "baseline": "03_KPI_plot_output_with_baseline",
    "ml": "04_KPI_plot_output_with_ML_Policy",
    "comparison": "05_KPI_plot_output_comparison",
    "tradeoff": "06_tradeoff_discussion_report",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parent


def _resolve(repo_root: Path, value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = repo_root / path
    return path


def _safe_token(value: str) -> str:
    value = value.strip().replace("\\", "-").replace("/", "-")
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_.-")
    return value or "scenario"


def _date_token(value: str | None = None) -> str:
    if value:
        for fmt in ("%d/%m/%y", "%d-%m-%y", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, fmt).strftime("%d-%m-%y")
            except ValueError:
                pass
        return _safe_token(value)
    return datetime.now().strftime("%d-%m-%y")


def _copy_file(src: Path | None, dst_dir: Path, *, new_name: str | None = None) -> Path | None:
    if src is None or not src.exists() or not src.is_file():
        return None
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / (new_name or src.name)
    shutil.copy2(src, dst)
    return dst


def _copy_tree(src: Path | None, dst: Path) -> Path | None:
    if src is None or not src.exists() or not src.is_dir():
        return None
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return dst


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def _metric_lookup(global_comparison: pd.DataFrame, metric: str, column: str, default: float = float("nan")) -> float:
    if global_comparison.empty or metric not in set(global_comparison.get("metric", [])):
        return default
    row = global_comparison.loc[global_comparison["metric"] == metric]
    if row.empty or column not in row.columns:
        return default
    return float(row.iloc[0][column])


def _slice_lookup(per_slice: pd.DataFrame, slice_name: str, column: str, default: float = float("nan")) -> float:
    if per_slice.empty or "slice_name" not in per_slice.columns or column not in per_slice.columns:
        return default
    row = per_slice.loc[per_slice["slice_name"] == slice_name]
    if row.empty:
        return default
    return float(row.iloc[0][column])


def _fmt(value: float, digits: int = 4) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{value:.{digits}f}"


def _make_policy_summary(global_comparison: pd.DataFrame, policy_column: str, output_path: Path) -> None:
    if global_comparison.empty or policy_column not in global_comparison.columns:
        return
    summary = global_comparison[["metric", policy_column]].rename(columns={policy_column: "value"})
    summary.to_csv(output_path, index=False)


def _write_root_readme(
    root: Path,
    scenario: str,
    comparison_dir: Path,
    model_dir: Path | None,
    global_comparison: pd.DataFrame,
    per_slice: pd.DataFrame,
) -> None:
    total_bw_delta = _metric_lookup(global_comparison, "total_bandwidth_usage", "delta_pct")
    block_delta = _metric_lookup(global_comparison, "block_ratio", "delta_ml_minus_baseline")
    connected_delta = _metric_lookup(global_comparison, "connected_clients_ratio", "delta_ml_minus_baseline")
    p95_delta = _metric_lookup(global_comparison, "p95_latency_ms", "delta_pct")
    state_sla_base = _metric_lookup(global_comparison, "avg_state_sla_violation_share", "baseline")
    state_sla_ml = _metric_lookup(global_comparison, "avg_state_sla_violation_share", "ml_policy")
    embb_completion_delta = _slice_lookup(per_slice, "eMBB", "completion_ratio_delta")
    urllc_latency_delta = _slice_lookup(per_slice, "URLLC", "avg_completion_latency_ms_delta")

    readme = f"""# Pipeline Output - {scenario}

Thư mục này gom artifact của một lần chạy end-to-end theo đúng luồng: mô phỏng, mô hình, KPI baseline, KPI ML, so sánh KPI và thảo luận trade-off.

## Cấu trúc

- `01_output_simulation`: dữ liệu thô từ baseline và ML run.
- `02_model_training_report_plot`: artifact mô hình, metadata và tóm tắt huấn luyện.
- `03_KPI_plot_output_with_baseline`: KPI của baseline.
- `04_KPI_plot_output_with_ML_Policy`: KPI/action/prediction của ML policy.
- `05_KPI_plot_output_comparison`: bảng và hình so sánh baseline vs ML.
- `06_tradeoff_discussion_report`: báo cáo nhận xét trade-off và guardrail.

## Tóm tắt nhanh

| KPI | Kết quả |
|---|---:|
| Total bandwidth delta | `{_fmt(total_bw_delta, 2)}%` |
| Block ratio delta | `{_fmt(block_delta, 4)}` |
| Connected clients delta | `{_fmt(connected_delta, 4)}` |
| p95 latency delta | `{_fmt(p95_delta, 2)}%` |
| State SLA share baseline -> ML | `{_fmt(state_sla_base, 4)} -> {_fmt(state_sla_ml, 4)}` |
| eMBB completion delta | `{_fmt(embb_completion_delta, 4)}` |
| URLLC completion latency delta | `{_fmt(urllc_latency_delta, 4)} ms` |

## Nguồn

- Comparison source: `{comparison_dir}`
- Model source: `{model_dir or 'N/A'}`
"""
    root.joinpath("README.md").write_text(readme, encoding="utf-8")


def _write_folder_readmes(root: Path, scenario: str) -> None:
    descriptions = {
        "simulation": (
            "Dữ liệu mô phỏng thô. `baseline_run` là run không dùng ML; `ml_run` là run có predictor, controller và broker."
        ),
        "model": (
            "Artifact mô hình GBDT: `metadata.json`, `feature_columns.json`, `label_config.json`, model và báo cáo huấn luyện nếu có."
        ),
        "baseline": (
            "KPI của chính sách baseline. Dùng folder này để xem baseline riêng trước khi so sánh với ML."
        ),
        "ml": (
            "KPI, prediction và action của ML Policy. Các file action/prediction giúp phân tích controller đã cấp phát tài nguyên như thế nào."
        ),
        "comparison": (
            "Bảng CSV và hình so sánh Baseline vs ML Policy. Đây là nhóm hình/chỉ số chính để đưa vào báo cáo."
        ),
        "tradeoff": (
            "Báo cáo nhận xét trade-off: metric nào cải thiện, metric nào đánh đổi, và guardrail pass/fail."
        ),
    }
    for key, folder_name in PIPELINE_FOLDERS.items():
        folder = root / folder_name
        folder.mkdir(parents=True, exist_ok=True)
        folder.joinpath("README.md").write_text(
            f"# {folder_name}\n\nScenario: `{scenario}`\n\n{descriptions[key]}\n",
            encoding="utf-8",
        )


def _write_model_summary(model_dir: Path | None, output_dir: Path) -> None:
    metadata: dict[str, Any] = {}
    if model_dir and model_dir.exists() and (model_dir / "metadata.json").exists():
        metadata = json.loads((model_dir / "metadata.json").read_text(encoding="utf-8"))

    summary = f"""# Tóm Tắt Mô Hình

- Model directory: `{model_dir or 'N/A'}`
- Dataset: `{metadata.get('dataset', 'N/A')}`
- Target: `{metadata.get('target_column', 'N/A')}`
- Horizon: `{metadata.get('horizon', 'N/A')}`
- Split strategy: `{metadata.get('split_strategy', 'N/A')}`
- Sample weight mode: `{metadata.get('sample_weight_mode', 'N/A')}`
- Calibration: `{metadata.get('calibration', metadata.get('calibration_method', 'N/A'))}`
- Thresholds by slice: `{metadata.get('decision_thresholds_by_slice', 'N/A')}`

Ghi chú: nếu thư mục này không có plot huấn luyện, hãy chạy thêm `plot_gbdt_diagnostics.py` hoặc `plot_gbdt_shap.py` cho model tương ứng.
"""
    output_dir.joinpath("model_training_summary.md").write_text(summary, encoding="utf-8")


def _write_tradeoff_report(
    output_dir: Path,
    global_comparison: pd.DataFrame,
    per_slice: pd.DataFrame,
    guardrail_path: Path | None,
) -> None:
    total_bw_delta = _metric_lookup(global_comparison, "total_bandwidth_usage", "delta_pct")
    block_delta = _metric_lookup(global_comparison, "block_ratio", "delta_ml_minus_baseline")
    connected_delta = _metric_lookup(global_comparison, "connected_clients_ratio", "delta_ml_minus_baseline")
    avg_latency_delta = _metric_lookup(global_comparison, "avg_latency_ms", "delta_pct")
    p95_delta = _metric_lookup(global_comparison, "p95_latency_ms", "delta_pct")
    state_sla_base = _metric_lookup(global_comparison, "avg_state_sla_violation_share", "baseline")
    state_sla_ml = _metric_lookup(global_comparison, "avg_state_sla_violation_share", "ml_policy")
    embb_completion_delta = _slice_lookup(per_slice, "eMBB", "completion_ratio_delta")
    urllc_latency_delta = _slice_lookup(per_slice, "URLLC", "avg_completion_latency_ms_delta")

    verdict_parts = []
    if not pd.isna(total_bw_delta) and total_bw_delta > 0:
        verdict_parts.append("ML tăng throughput tổng.")
    if not pd.isna(embb_completion_delta) and embb_completion_delta > 0:
        verdict_parts.append("ML cải thiện completion ratio của eMBB.")
    if not pd.isna(urllc_latency_delta) and urllc_latency_delta < 0:
        verdict_parts.append("ML giảm completion latency của URLLC.")
    if not pd.isna(p95_delta) and p95_delta > 0:
        verdict_parts.append("Đánh đổi: p95 latency tăng, cần phân tích thêm tail latency.")
    if not pd.isna(state_sla_ml) and not pd.isna(state_sla_base) and state_sla_ml > state_sla_base:
        verdict_parts.append("Đánh đổi: state-level SLA violation share tăng.")

    report = f"""# Trade-off Discussion Report

## Nhận xét nhanh

{' '.join(verdict_parts) if verdict_parts else 'Chưa đủ dữ liệu để kết luận trade-off.'}

## Bảng chỉ số chính

| Chỉ số | Giá trị |
|---|---:|
| Total bandwidth delta | `{_fmt(total_bw_delta, 2)}%` |
| Block ratio delta | `{_fmt(block_delta, 4)}` |
| Connected clients delta | `{_fmt(connected_delta, 4)}` |
| Average latency delta | `{_fmt(avg_latency_delta, 2)}%` |
| p95 latency delta | `{_fmt(p95_delta, 2)}%` |
| State SLA share baseline -> ML | `{_fmt(state_sla_base, 4)} -> {_fmt(state_sla_ml, 4)}` |
| eMBB completion delta | `{_fmt(embb_completion_delta, 4)}` |
| URLLC completion latency delta | `{_fmt(urllc_latency_delta, 4)} ms` |

## Guardrail

- Guardrail report: `{guardrail_path.name if guardrail_path and guardrail_path.exists() else 'N/A'}`
"""
    output_dir.joinpath("tradeoff_discussion_report.md").write_text(report, encoding="utf-8")


def organize_pipeline_outputs(
    *,
    scenario: str,
    comparison_dir: str | Path,
    model_dir: str | Path | None = None,
    training_report_dir: str | Path | None = None,
    output_root: str | Path = "final_output",
    run_date: str | None = None,
    overwrite: bool = False,
) -> Path:
    repo_root = _repo_root()
    comparison_dir = _resolve(repo_root, comparison_dir)
    model_dir = _resolve(repo_root, model_dir)
    training_report_dir = _resolve(repo_root, training_report_dir)
    output_root = _resolve(repo_root, output_root)
    assert comparison_dir is not None
    assert output_root is not None

    if not comparison_dir.exists():
        raise FileNotFoundError(f"Comparison directory not found: {comparison_dir}")

    safe_scenario = _safe_token(scenario)
    folder_name = f"output_{safe_scenario}_{_date_token(run_date)}"
    pipeline_root = output_root / folder_name
    if pipeline_root.exists():
        if overwrite:
            shutil.rmtree(pipeline_root)
        else:
            counter = 2
            while (output_root / f"{folder_name}_{counter}").exists():
                counter += 1
            pipeline_root = output_root / f"{folder_name}_{counter}"

    pipeline_root.mkdir(parents=True, exist_ok=True)
    _write_folder_readmes(pipeline_root, scenario)

    simulation_dir = pipeline_root / PIPELINE_FOLDERS["simulation"]
    model_dir_out = pipeline_root / PIPELINE_FOLDERS["model"]
    baseline_dir_out = pipeline_root / PIPELINE_FOLDERS["baseline"]
    ml_dir_out = pipeline_root / PIPELINE_FOLDERS["ml"]
    comparison_dir_out = pipeline_root / PIPELINE_FOLDERS["comparison"]
    tradeoff_dir_out = pipeline_root / PIPELINE_FOLDERS["tradeoff"]

    _copy_tree(comparison_dir / "baseline_run", simulation_dir / "baseline_run")
    _copy_tree(comparison_dir / "ml_run", simulation_dir / "ml_run")

    _copy_tree(comparison_dir / "baseline_run", baseline_dir_out / "baseline_run")
    _copy_tree(comparison_dir / "ml_run", ml_dir_out / "ml_run")

    for filename in ["metadata.json", "feature_columns.json", "label_config.json", "model.joblib", "horizon_models.json"]:
        _copy_file(model_dir / filename if model_dir else None, model_dir_out)
    if training_report_dir and training_report_dir.exists():
        for pattern in ("training_report.*", "*.png", "*.svg", "*.csv", "*.json"):
            for file_path in training_report_dir.glob(pattern):
                _copy_file(file_path, model_dir_out)
    _write_model_summary(model_dir, model_dir_out)

    comparison_files = [
        "global_kpi_comparison.csv",
        "per_slice_comparison.csv",
        "per_base_station_comparison.csv",
        "per_base_station_slice_comparison.csv",
        "resource_allocation_summary.csv",
        "ml_action_ratio_timeseries.csv",
        "baseline_vs_ml_global_kpis.png",
        "baseline_vs_ml_per_slice_bars.png",
        "baseline_vs_ml_per_slice_bars.svg",
        "baseline_vs_ml_per_slice_bars_throughput.png",
        "baseline_vs_ml_per_slice_bars_latency.png",
        "baseline_vs_ml_per_slice_bars_completion_ratio.png",
        "baseline_vs_ml_per_slice_bars_sla_margin_improvement.png",
        "baseline_vs_ml_per_slice_bars_improvement_heatmap.png",
        "baseline_vs_ml_timeseries.png",
        "ml_action_distribution.png",
    ]
    for filename in comparison_files:
        _copy_file(comparison_dir / filename, comparison_dir_out)

    for filename in ["baseline_vs_ml_report.md", "baseline_vs_ml_report.json"]:
        _copy_file(comparison_dir / filename, tradeoff_dir_out)
    guardrail_path = None
    for filename in ["policy_guardrail_report.md", "policy_guardrail_report.json"]:
        copied = _copy_file(comparison_dir / filename, tradeoff_dir_out)
        if filename.endswith(".md") and copied:
            guardrail_path = copied

    global_comparison = _read_csv(comparison_dir / "global_kpi_comparison.csv")
    per_slice = _read_csv(comparison_dir / "per_slice_comparison.csv")
    _make_policy_summary(global_comparison, "baseline", baseline_dir_out / "baseline_kpi_summary.csv")
    _make_policy_summary(global_comparison, "ml_policy", ml_dir_out / "ml_policy_kpi_summary.csv")
    _write_tradeoff_report(tradeoff_dir_out, global_comparison, per_slice, guardrail_path)
    _write_root_readme(pipeline_root, scenario, comparison_dir, model_dir, global_comparison, per_slice)

    return pipeline_root


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Organize end-to-end run artifacts into a structured output folder.")
    parser.add_argument("--scenario", required=True, help="Scenario name, e.g. light-realistic.")
    parser.add_argument("--comparison-dir", required=True, help="Directory produced by compare_baseline_vs_ml.py.")
    parser.add_argument("--model-dir", help="Trained model directory.")
    parser.add_argument("--training-report-dir", help="Optional training report/diagnostic directory.")
    parser.add_argument("--output-root", default="final_output")
    parser.add_argument("--run-date", help="Date token. Accepts DD/MM/YY, DD-MM-YY, or YYYY-MM-DD. Default: today.")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    output_dir = organize_pipeline_outputs(
        scenario=args.scenario,
        comparison_dir=args.comparison_dir,
        model_dir=args.model_dir,
        training_report_dir=args.training_report_dir,
        output_root=args.output_root,
        run_date=args.run_date,
        overwrite=args.overwrite,
    )
    print(f"Pipeline output organized at: {output_dir}")


if __name__ == "__main__":
    main()
