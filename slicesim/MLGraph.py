from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import pandas as pd

from .Graph import Graph


class MLPolicyGraph(Graph):
    """Graph variant for closed-loop ML policy simulation snapshots.

    It keeps the same map and KPI layout as Graph.py, then adds a small
    policy badge so the exported figure cannot be mistaken for a baseline run.
    """

    def __init__(
        self,
        *args: Any,
        policy_label: str = "ML Policy",
        actions: pd.DataFrame | None = None,
        predictions: pd.DataFrame | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.policy_label = policy_label
        self.actions = actions if actions is not None else pd.DataFrame()
        self.predictions = predictions if predictions is not None else pd.DataFrame()

    def draw_all(self, *stats: Any) -> None:
        super().draw_all(*stats)
        self._draw_policy_badge()

    def _draw_policy_badge(self) -> None:
        self.fig.suptitle(f"{self.policy_label} closed-loop simulation", fontsize=14, fontweight="bold", y=0.995)

        lines = ["Policy source: GBDT risk + controller action"]
        if not self.actions.empty:
            action_lines = []
            if {"slice_name", "target_ratio"}.issubset(self.actions.columns):
                ratios = self.actions.groupby("slice_name")["target_ratio"].mean().sort_index()
                action_lines.append("mean rho: " + ", ".join(f"{name}={value:.3f}" for name, value in ratios.items()))
            if "admission_guard_factor" in self.actions.columns:
                action_lines.append(f"mean guard={self.actions['admission_guard_factor'].mean():.3f}")
            if "scheduling_weight" in self.actions.columns:
                action_lines.append(f"mean schedW={self.actions['scheduling_weight'].mean():.3f}")
            if action_lines:
                lines.extend(action_lines)

        if not self.predictions.empty and "sla_violation_prob" in self.predictions.columns:
            lines.append(f"mean SLA risk={self.predictions['sla_violation_prob'].mean():.3f}")

        self.fig.text(
            0.012,
            0.012,
            "\n".join(lines),
            fontsize=8,
            ha="left",
            va="bottom",
            bbox={"boxstyle": "round,pad=0.35", "facecolor": "white", "edgecolor": "0.35", "alpha": 0.88},
        )


def render_ml_policy_graph(
    context: Any,
    output_path: str | Path,
    *,
    actions: pd.DataFrame | None = None,
    predictions: pd.DataFrame | None = None,
    policy_label: str = "ML Policy",
) -> Path:
    """Render a Graph.py-style figure from a finished ML closed-loop context."""

    settings = context.settings
    x_vals = settings["statistics_params"]["x"]
    y_vals = settings["statistics_params"]["y"]
    xlim_left = int(settings["simulation_time"] * settings["statistics_params"]["warmup_ratio"])
    xlim_right = int(settings["simulation_time"] * (1 - settings["statistics_params"]["cooldown_ratio"])) + 1

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    graph = MLPolicyGraph(
        context.base_stations,
        context.clients,
        (xlim_left, xlim_right),
        ((x_vals["min"], x_vals["max"]), (y_vals["min"], y_vals["max"])),
        output_dpi=settings["plotting_params"].get("plot_file_dpi", 300),
        scatter_size=settings["plotting_params"].get("scatter_size", 15),
        output_filename=str(output_path),
        policy_label=policy_label,
        actions=actions,
        predictions=predictions,
    )
    graph.draw_all(
        *context.stats.get_stats(),
        context.stats.get_slice_latency_stats(),
        context.stats.get_slice_first_service_latency_stats(),
    )
    graph.save_fig()
    plt.close(graph.fig)
    return output_path
