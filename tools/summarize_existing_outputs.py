"""Aggregate KPI deltas from existing FINAL_OUTPUT folders.

Use this when simulation outputs were generated across several runs or copied
from another machine and you only need to recompute mean +/- std tables.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd


OUTPUT_RE = re.compile(r"^FINAL_OUTPUT_(?P<scenario>[^_]+)_seed(?P<seed>\d+)_")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _find_output_dirs(root: Path) -> list[Path]:
    candidates: list[Path] = []
    for path in root.rglob("FINAL_OUTPUT_*_seed*_*"):
        if not path.is_dir():
            continue
        if OUTPUT_RE.match(path.name):
            candidates.append(path)
    return sorted(set(candidates))


def _comparison_csv(output_dir: Path) -> Path | None:
    candidates = [
        output_dir / "05_KPI_plot_output_comparison" / "global_kpi_comparison.csv",
        output_dir / "global_kpi_comparison.csv",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def summarize_outputs(search_root: Path) -> pd.DataFrame:
    rows: list[dict] = []
    for output_dir in _find_output_dirs(search_root):
        match = OUTPUT_RE.match(output_dir.name)
        if not match:
            continue
        csv_path = _comparison_csv(output_dir)
        if csv_path is None:
            continue
        frame = pd.read_csv(csv_path)
        for _, row in frame.iterrows():
            rows.append(
                {
                    "scenario": match.group("scenario"),
                    "seed": int(match.group("seed")),
                    "metric": row.get("metric"),
                    "baseline": row.get("baseline"),
                    "ml": row.get("ml_policy"),
                    "delta_pct": row.get("delta_pct"),
                    "output_dir": str(output_dir),
                }
            )
    if not rows:
        return pd.DataFrame(
            columns=["scenario", "seed", "metric", "baseline", "ml", "delta_pct", "output_dir"]
        )
    return pd.DataFrame(rows).drop_duplicates(["scenario", "seed", "metric", "output_dir"])


def aggregate_summary(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame(columns=["scenario", "metric", "n", "mean_pct", "std_pct"])
    aggregate = (
        summary.groupby(["scenario", "metric"], as_index=False)["delta_pct"]
        .agg(n="count", mean_pct="mean", std_pct="std")
        .fillna({"std_pct": 0.0})
    )
    return aggregate.sort_values(["scenario", "metric"]).reset_index(drop=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Aggregate existing FINAL_OUTPUT KPI deltas.")
    parser.add_argument(
        "--search-root",
        default=".",
        help="Root directory to recursively scan for FINAL_OUTPUT_<scenario>_seed* folders.",
    )
    parser.add_argument("--summary-csv", default="existing_outputs_multiseed_summary.csv")
    parser.add_argument("--aggregate-csv", default="existing_outputs_multiseed_summary_aggregate.csv")
    return parser


def main() -> None:
    repo_root = _repo_root()
    args = build_parser().parse_args()
    search_root = Path(args.search_root)
    if not search_root.is_absolute():
        search_root = repo_root / search_root

    summary = summarize_outputs(search_root)
    aggregate = aggregate_summary(summary)

    summary_path = Path(args.summary_csv)
    aggregate_path = Path(args.aggregate_csv)
    if not summary_path.is_absolute():
        summary_path = repo_root / summary_path
    if not aggregate_path.is_absolute():
        aggregate_path = repo_root / aggregate_path
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    aggregate_path.parent.mkdir(parents=True, exist_ok=True)

    summary.to_csv(summary_path, index=False)
    aggregate.to_csv(aggregate_path, index=False)

    print(f"Parsed runs: {summary[['scenario', 'seed', 'output_dir']].drop_duplicates().shape[0] if not summary.empty else 0}")
    print(f"Wrote per-run summary: {summary_path}")
    print(f"Wrote aggregate stats:  {aggregate_path}")
    if not aggregate.empty:
        print(aggregate.to_string(index=False))


if __name__ == "__main__":
    main()
