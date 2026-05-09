"""Export SLA-style KPI plots: throughput hit %, delay hit %, utilization CDF.

For each comparison run directory (e.g. artifacts/comparisons/e2e_*), produces:

    completion_ratio_hit.png            -- bar chart per slice, BL vs ML
    delay_hit_sla_tolerance.png         -- DELAY HIT vs scenario SLA tolerance
                                          (real SLA — values are absolute, not
                                          relative to baseline)
    delay_hit_relative_p75.png          -- DELAY HIT relative to baseline 75th
                                          percentile (per-scenario relative
                                          comparison; not a real SLA metric)
    resource_utilization_cdf.png        -- CDF of mean_slice_load_ratio per
                                          slice/policy

Definitions (per UE, from client_summary.csv):
    Completion-ratio Hit per UE = completion_ratio >= THROUGHPUT_HIT_RATIO (0.95)

    Delay Hit per UE (sla_tolerance mode):
        avg_completion_latency_ms <= delay_tolerance_per_slice
        Default thresholds match scenario YAML:
            URLLC = 1.0 ms, eMBB = 100 ms, mMTC = 500 ms
        Override with --tolerance-source sla_table to use the SLA reference
        table (max_avg_latency_ms column).

    Delay Hit per UE (relative_p75 mode):
        avg_completion_latency_ms <= P75(baseline latencies)
        This is a relative comparison metric, NOT a real SLA threshold.
        Useful for visualising whether ML reduces latency relative to the
        baseline latency distribution.

Both delay-hit modes are produced; the SLA-tolerance version is the real KPI
to report against scenarios. The relative-p75 version is supplementary.

Utilization CDF reads from baseline_states.csv / online_states_raw.csv
(per-window load ratio).

Usage:
    python tools/export_sla_kpi_plots.py <comparison_dir> [<comparison_dir> ...]
    python tools/export_sla_kpi_plots.py --all
    python tools/export_sla_kpi_plots.py --all --tolerance-source sla_table
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

SLICE_ORDER = ("URLLC", "eMBB", "mMTC")
THROUGHPUT_HIT_RATIO = 0.95
SLICE_COLOR = {"URLLC": "#2ca02c", "eMBB": "#d62728", "mMTC": "#1f77b4"}

# Real SLA delay tolerance per slice (ms). Two sources are supported via
# --tolerance-source flag.
SCENARIO_DELAY_TOLERANCE_MS = {"URLLC": 1.0, "eMBB": 100.0, "mMTC": 500.0}


def _ensure_utf8_stdout() -> None:
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def _load_client(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    needed = {"slice_name", "completion_ratio", "avg_completion_latency_ms"}
    missing = needed - set(df.columns)
    if missing:
        raise SystemExit(f"Missing columns in {path}: {missing}")
    return df


def _load_state(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    needed = {"slice_name", "mean_slice_load_ratio"}
    missing = needed - set(df.columns)
    if missing:
        raise SystemExit(f"Missing columns in {path}: {missing}")
    return df


def _load_sla_tolerance_from_table(sla_table_path: Path) -> dict[str, float]:
    """Read max_avg_latency_ms from sla_reference_table.csv as SLA tolerance."""
    if not sla_table_path.exists():
        raise SystemExit(f"SLA reference table not found: {sla_table_path}")
    df = pd.read_csv(sla_table_path)
    out = {}
    for slice_name in SLICE_ORDER:
        row = df[df["slice_name"] == slice_name]
        if row.empty:
            out[slice_name] = float("nan")
        else:
            out[slice_name] = float(row.iloc[0]["max_avg_latency_ms"])
    return out


def _throughput_hit(client_df: pd.DataFrame) -> dict[str, float]:
    out = {}
    for slice_name in SLICE_ORDER:
        sub = client_df[client_df["slice_name"] == slice_name]
        if sub.empty:
            out[slice_name] = float("nan")
            continue
        out[slice_name] = float((sub["completion_ratio"] >= THROUGHPUT_HIT_RATIO).mean())
    return out


def _delay_hit(client_df: pd.DataFrame, thresholds: dict[str, float]) -> dict[str, float]:
    out = {}
    for slice_name in SLICE_ORDER:
        sub = client_df[client_df["slice_name"] == slice_name]
        threshold = thresholds.get(slice_name, float("nan"))
        if sub.empty or pd.isna(threshold):
            out[slice_name] = float("nan")
            continue
        out[slice_name] = float((sub["avg_completion_latency_ms"] <= threshold).mean())
    return out


def _baseline_p75_thresholds(bl_client: pd.DataFrame) -> dict[str, float]:
    out: dict[str, float] = {}
    for slice_name in SLICE_ORDER:
        baseline = bl_client.loc[
            bl_client["slice_name"] == slice_name,
            "avg_completion_latency_ms",
        ]
        if baseline.empty:
            out[slice_name] = float("nan")
        else:
            out[slice_name] = float(np.percentile(baseline, 75))
    return out


def _plot_bar(
    bl: dict[str, float],
    ml: dict[str, float],
    title: str,
    ylabel: str,
    output_path: Path,
    annotation: str | None = None,
) -> None:
    fig, ax = plt.subplots(figsize=(7, 4.5))
    width = 0.35
    x = np.arange(len(SLICE_ORDER))
    bl_vals = [bl[s] for s in SLICE_ORDER]
    ml_vals = [ml[s] for s in SLICE_ORDER]

    ax.bar(
        x - width / 2,
        bl_vals,
        width,
        label="Baseline",
        color="#d62728",
        hatch="...",
        edgecolor="white",
        linewidth=0.5,
        alpha=0.9,
    )
    ax.bar(
        x + width / 2,
        ml_vals,
        width,
        label="ML Policy",
        color="#1f77b4",
        hatch="xxx",
        edgecolor="white",
        linewidth=0.5,
        alpha=0.9,
    )

    for i, (bv, mv) in enumerate(zip(bl_vals, ml_vals)):
        ax.text(i - width / 2, min(bv + 0.02, 1.02), f"{bv:.2f}", ha="center", fontsize=8)
        ax.text(i + width / 2, min(mv + 0.02, 1.02), f"{mv:.2f}", ha="center", fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels(SLICE_ORDER)
    ax.set_xlabel("Slice Type")
    ax.set_ylabel(ylabel)
    ax.set_ylim(0, 1.1)
    legend_loc = "lower right" if max(bl_vals + ml_vals) < 0.85 else "upper left"
    ax.legend(loc=legend_loc)
    ax.set_title(title)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    if annotation:
        ax.text(
            0.5,
            -0.18,
            annotation,
            transform=ax.transAxes,
            ha="center",
            va="top",
            fontsize=7,
            color="0.4",
        )
    fig.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def _plot_cdf(
    bl_state: pd.DataFrame,
    ml_state: pd.DataFrame,
    output_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(7, 4.5))
    style_map = {"Baseline": "-", "ML Policy": "--"}
    marker_map = {"Baseline": "o", "ML Policy": "s"}

    for slice_name in SLICE_ORDER:
        for label, df in [("Baseline", bl_state), ("ML Policy", ml_state)]:
            sub = df[df["slice_name"] == slice_name]
            if sub.empty:
                continue
            util = (sub["mean_slice_load_ratio"].clip(0, 1) * 100).sort_values().to_numpy()
            cdf = np.arange(1, len(util) + 1) / len(util)
            ax.plot(
                util,
                cdf,
                linestyle=style_map[label],
                color=SLICE_COLOR[slice_name],
                marker=marker_map[label],
                markevery=max(1, len(util) // 12),
                markersize=4,
                label=f"{slice_name} ({label})",
                linewidth=1.5,
            )

    ax.set_xlabel("Percentage of Resource Utilization")
    ax.set_ylabel("CDF")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 1.02)
    ax.legend(loc="lower right", fontsize=8, ncol=2)
    ax.grid(linestyle="--", alpha=0.4)
    ax.set_title("CDF of Resource Utilization per Slice")
    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def export_for_run(
    comparison_dir: Path,
    sla_tolerances: dict[str, float],
    tolerance_source: str,
) -> list[Path]:
    bl_client_path = comparison_dir / "baseline_run" / "baseline_client_summary.csv"
    ml_client_path = comparison_dir / "ml_run" / "online_client_summary.csv"
    bl_state_path = comparison_dir / "baseline_run" / "baseline_states.csv"
    ml_state_path = comparison_dir / "ml_run" / "online_states_raw.csv"
    for p in (bl_client_path, ml_client_path, bl_state_path, ml_state_path):
        if not p.exists():
            raise SystemExit(f"Missing input: {p}")

    bl_client = _load_client(bl_client_path)
    ml_client = _load_client(ml_client_path)
    bl_state = _load_state(bl_state_path)
    ml_state = _load_state(ml_state_path)

    # Completion-ratio hit (single mode: completion_ratio >= 0.95)
    thr_bl = _throughput_hit(bl_client)
    thr_ml = _throughput_hit(ml_client)

    # Delay hit -- two modes:
    # 1) SLA tolerance: per-scenario absolute SLA threshold
    dly_bl_sla = _delay_hit(bl_client, sla_tolerances)
    dly_ml_sla = _delay_hit(ml_client, sla_tolerances)
    # 2) Relative p75: 75th percentile of baseline latencies
    p75_thresholds = _baseline_p75_thresholds(bl_client)
    dly_bl_p75 = _delay_hit(bl_client, p75_thresholds)
    dly_ml_p75 = _delay_hit(ml_client, p75_thresholds)

    out_thr = comparison_dir / "completion_ratio_hit.png"
    out_dly_sla = comparison_dir / "delay_hit_sla_tolerance.png"
    out_dly_p75 = comparison_dir / "delay_hit_relative_p75.png"
    out_cdf = comparison_dir / "resource_utilization_cdf.png"
    out_note = comparison_dir / "sla_style_kpi_definitions.md"
    legacy_thr = comparison_dir / "sla_throughput_hit.png"
    legacy_thr.unlink(missing_ok=True)

    _plot_bar(
        thr_bl,
        thr_ml,
        "Completion Ratio Hit Percentage",
        "Completion-Ratio Hit Percentage",
        out_thr,
        annotation=f"Hit per UE: completion_ratio >= {THROUGHPUT_HIT_RATIO:.2f}",
    )
    sla_anno = ", ".join(
        f"{s}={sla_tolerances[s]:.0f}ms" for s in SLICE_ORDER if not pd.isna(sla_tolerances[s])
    )
    _plot_bar(
        dly_bl_sla,
        dly_ml_sla,
        "Delay SLA Hit Percentage (real SLA tolerance)",
        "Delay Hit Percentage",
        out_dly_sla,
        annotation=f"Hit per UE: avg_completion_latency_ms <= {tolerance_source} tolerance ({sla_anno})",
    )
    p75_anno = ", ".join(
        f"{s}={p75_thresholds[s]:.3f}ms" for s in SLICE_ORDER if not pd.isna(p75_thresholds[s])
    )
    _plot_bar(
        dly_bl_p75,
        dly_ml_p75,
        "Delay Hit Relative to Baseline P75 (not contractual SLA)",
        "Delay Hit Ratio (relative)",
        out_dly_p75,
        annotation=f"Relative metric only: threshold = baseline p75 latency ({p75_anno})",
    )
    _plot_cdf(bl_state, ml_state, out_cdf)

    note = f"""# SLA-Style KPI Plot Definitions

These charts are auxiliary comparison plots. Use the names below precisely in the thesis/report.

- `completion_ratio_hit.png`: per-UE completion-ratio hit. A UE is counted as hit when `completion_ratio >= {THROUGHPUT_HIT_RATIO:.2f}`. This is a completion target, not a 3GPP-defined throughput SLA unless the report explicitly defines it as such.
- `delay_hit_sla_tolerance.png`: per-UE delay hit against the scenario/SLA delay tolerance. This is the SLA-aligned delay-hit chart.
- `delay_hit_relative_p75.png`: per-UE delay hit relative to the baseline p75 completion latency. This is a relative baseline comparison only, not a contractual SLA metric.
- `resource_utilization_cdf.png`: CDF of per-window `mean_slice_load_ratio` by slice and policy.

Current delay tolerance source: `{tolerance_source}`.
SLA delay thresholds: {sla_anno}.
Baseline-p75 relative thresholds: {p75_anno}.
"""
    out_note.write_text(note, encoding="utf-8")

    print(f"[{comparison_dir.name}] Completion-ratio hit (BL/ML):")
    for s in SLICE_ORDER:
        print(f"    {s:6s}: {thr_bl[s]:.3f}  /  {thr_ml[s]:.3f}")
    print(f"[{comparison_dir.name}] Delay hit (SLA tolerance, source={tolerance_source}): {sla_anno}")
    for s in SLICE_ORDER:
        print(f"    {s:6s}: {dly_bl_sla[s]:.3f}  /  {dly_ml_sla[s]:.3f}")
    print(f"[{comparison_dir.name}] Delay hit (relative baseline-p75, supplementary): {p75_anno}")
    for s in SLICE_ORDER:
        print(f"    {s:6s}: {dly_bl_p75[s]:.3f}  /  {dly_ml_p75[s]:.3f}")
    print(
        f"[{comparison_dir.name}] Wrote: {out_thr.name}, {out_dly_sla.name}, "
        f"{out_dly_p75.name}, {out_cdf.name}, {out_note.name}"
    )
    return [out_thr, out_dly_sla, out_dly_p75, out_cdf, out_note]


def main() -> None:
    _ensure_utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dirs", nargs="*", help="Comparison output dirs")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run on all artifacts/comparisons/e2e_*_longterm_* dirs",
    )
    parser.add_argument(
        "--tolerance-source",
        choices=("scenario_yaml", "sla_table"),
        default="scenario_yaml",
        help="Where to read per-slice delay tolerance from. "
        "'scenario_yaml' uses hardcoded SCENARIO_DELAY_TOLERANCE_MS (URLLC=1ms, eMBB=100ms, mMTC=500ms). "
        "'sla_table' reads max_avg_latency_ms from sla_reference_table.csv.",
    )
    parser.add_argument(
        "--sla-table-path",
        default=str(ROOT / "sla_reference_table.csv"),
        help="Path to sla_reference_table.csv (used when --tolerance-source=sla_table)",
    )
    args = parser.parse_args()

    if args.tolerance_source == "scenario_yaml":
        sla_tolerances = SCENARIO_DELAY_TOLERANCE_MS.copy()
    else:
        sla_tolerances = _load_sla_tolerance_from_table(Path(args.sla_table_path))

    targets: list[Path] = []
    if args.all:
        base = ROOT / "artifacts" / "comparisons"
        targets.extend(sorted(base.glob("e2e_*_longterm_*")))
    targets.extend(Path(d) for d in args.dirs)

    if not targets:
        parser.error("Provide comparison dir paths or --all")

    for tgt in targets:
        try:
            export_for_run(tgt, sla_tolerances, args.tolerance_source)
        except SystemExit as exc:
            print(f"[skip] {tgt}: {exc}")


if __name__ == "__main__":
    main()
