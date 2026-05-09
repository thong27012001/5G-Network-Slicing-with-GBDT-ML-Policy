"""Bộ runner replay và closed-loop online cho slicing với ML controller."""

from __future__ import annotations

from contextlib import contextmanager
import logging
from pathlib import Path

import pandas as pd

from broker.slice_broker import SliceBroker
from control.admm_controller import ADMMRatioController
from control.gbdt_controller import GBDTController
from integration.history_store import HistoryStore
from integration.simulation_adapter import (
    OnlineSimulationAdapter,
    ReplaySimulationAdapter,
    build_client_summary_from_context,
    build_slice_latency_series_from_context,
)
from ml.feature_builder import add_temporal_features
from ml.feature_schema import TEMPORAL_LAGS, infer_temporal_feature_columns
from ml.predictor import GBDTPredictor


@contextmanager
def _legacy_output_log(log_path: str | Path | None):
    """Enable the simulator's legacy logging stream for one online run."""
    if log_path is None:
        yield None
        return

    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    previous_disable_level = logging.root.manager.disable
    previous_level = root_logger.level
    previous_handlers = list(root_logger.handlers)
    file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(message)s"))

    for handler in previous_handlers:
        root_logger.removeHandler(handler)
    root_logger.addHandler(file_handler)
    root_logger.setLevel(logging.INFO)
    logging.disable(logging.NOTSET)
    try:
        yield log_path
    finally:
        root_logger.removeHandler(file_handler)
        file_handler.close()
        for handler in previous_handlers:
            root_logger.addHandler(handler)
        root_logger.setLevel(previous_level)
        logging.disable(previous_disable_level)


def _write_legacy_run_summary(context) -> None:
    """Write the same end-of-run client/stat summary used by slicesim.__main__."""
    for client in context.clients:
        logging.info(client)
        logging.info(f"\tTotal connected time: {client.total_connected_time:>5}")
        logging.info(f"\tTotal unconnected time: {client.total_unconnected_time:>5}")
        logging.info(f"\tTotal request count: {client.total_request_count:>5}")
        logging.info(f"\tTotal consume time: {client.total_consume_time:>5}")
        logging.info(f"\tTotal usage: {client.total_usage:>5}")
        logging.info(f"\tTotal completed requests: {client.total_completed_requests:>5}")
        logging.info(f"\tTotal latency (ms): {client.total_latency_ms:>8.3f}")
        logging.info(f"\tTotal max latency (ms): {client.max_latency_ms:>8.3f}")
        logging.info(f"\tTotal latency violations: {client.latency_violation_count:>5}")
        logging.info("")

    logging.info(context.stats.get_stats())


def build_controller(controller_type: str = "gbdt", preset_name: str = "balanced"):
    """Create a controller with the common decide(...) action interface."""
    normalized = str(controller_type or "gbdt").strip().lower()
    if normalized in {"gbdt", "ml", "risk", "risk_aware"}:
        return GBDTController(preset_name=preset_name)
    if normalized in {"admm", "admm_ratio", "admm_optimizer"}:
        return ADMMRatioController(preset_name=preset_name)
    raise ValueError("Unknown controller_type '%s'. Valid values: gbdt, admm." % controller_type)


def _prepare_prediction_window(
    history: HistoryStore,
    current_time: int | float,
    feature_columns: list[str],
) -> pd.DataFrame:
    history_frame = history.combined()
    if history_frame.empty:
        return history_frame

    history_frame = history_frame.sort_values(["slice_name", "base_station_id", "time"]).reset_index(drop=True)
    if infer_temporal_feature_columns(feature_columns):
        history_frame = add_temporal_features(history_frame, lags=TEMPORAL_LAGS)
    current_window = history_frame[history_frame["time"] == int(current_time)].copy()
    if current_window.empty:
        return current_window
    missing_columns = [column for column in feature_columns if column not in current_window.columns]
    if missing_columns:
        for column in missing_columns:
            current_window[column] = 0
    return current_window


def run_replay_closed_loop(
    excel_path: str | Path,
    sla_path: str | Path,
    model_dir: str | Path,
    output_dir: str | Path,
    controller=None,
    controller_type: str = "gbdt",
    controller_preset: str = "balanced",
) -> dict[str, Path]:
    """Chạy replay output của simulator theo từng time window để tách riêng hành vi prediction và controller."""
    adapter = ReplaySimulationAdapter(excel_path, sla_path, include_temporal_features=True)
    predictor = GBDTPredictor(model_dir)
    controller = controller or build_controller(controller_type, controller_preset)
    history = HistoryStore(max_windows=8)

    prediction_frames: list[pd.DataFrame] = []
    action_frames: list[pd.DataFrame] = []

    for time_value, state_window in adapter.iter_windows():
        history.append(state_window)
        prediction_window = predictor.predict(state_window)
        action_window = controller.decide(state_window, prediction_window, effective_time=time_value + 1)
        prediction_frames.append(prediction_window)
        action_frames.append(action_window)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    predictions = pd.concat(prediction_frames, ignore_index=True) if prediction_frames else pd.DataFrame()
    actions = pd.concat(action_frames, ignore_index=True) if action_frames else pd.DataFrame()

    prediction_path = adapter.export_frame(predictions, output_dir / "replay_predictions.csv")
    action_path = adapter.export_frame(actions, output_dir / "replay_actions.csv")

    return {
        "prediction_path": prediction_path,
        "action_path": action_path,
    }


def run_online_closed_loop(
    config_path: str | Path,
    sla_path: str | Path,
    model_dir: str | Path,
    output_dir: str | Path,
    seed: int | None = None,
    controller=None,
    controller_type: str = "gbdt",
    controller_preset: str = "balanced",
    use_broker: bool = False,
    broker_preset: str = "forecasting_balanced",
    render_graph: bool = False,
    graph_output_path: str | Path | None = None,
    graph_policy_label: str = "ML Policy",
    log_path: str | Path | None = None,
) -> dict[str, Path]:
    """Chạy simulator theo kiểu online, dự đoán risk của window kế tiếp và áp action ngay lập tức."""
    adapter = OnlineSimulationAdapter(config_path, sla_path, seed=seed)
    predictor = GBDTPredictor(model_dir)
    controller = controller or build_controller(controller_type, controller_preset)
    broker = SliceBroker(controller, preset_name=broker_preset) if use_broker else None
    history = HistoryStore(max_windows=8)

    prediction_frames: list[pd.DataFrame] = []
    action_frames: list[pd.DataFrame] = []
    broker_forecast_frames: list[pd.DataFrame] = []
    broker_feedback_frames: list[pd.DataFrame] = []
    state_frames: list[pd.DataFrame] = []
    raw_state_frames: list[pd.DataFrame] = []

    with _legacy_output_log(log_path) as resolved_log_path:
        while adapter.has_next_window():
            state_window = adapter.run_one_window()
            if state_window.empty:
                continue
            raw_state_frames.append(state_window)
            history.append(state_window)
            state_for_prediction = _prepare_prediction_window(
                history,
                current_time=state_window["time"].iloc[0],
                feature_columns=predictor.feature_columns,
            )
            if state_for_prediction.empty:
                state_frames.append(state_window)
                continue

            prediction_window = predictor.predict(state_for_prediction)
            effective_time = int(state_window["time"].iloc[0]) + 1
            if broker is not None:
                broker_decision = broker.decide(
                    state_df=state_for_prediction,
                    history_df=history.combined(),
                    prediction_df=prediction_window,
                    effective_time=effective_time,
                )
                action_window = broker_decision.actions
                broker_forecast_frames.append(broker_decision.forecasts)
                broker_feedback_frames.append(broker_decision.feedback)
            else:
                action_window = controller.decide(
                    state_for_prediction,
                    prediction_window,
                    effective_time=effective_time,
                )
            adapter.apply_actions(action_window)

            state_frames.append(state_for_prediction)
            prediction_frames.append(prediction_window)
            action_frames.append(action_window)

        if resolved_log_path is not None:
            _write_legacy_run_summary(adapter.context)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    states = pd.concat(state_frames, ignore_index=True) if state_frames else pd.DataFrame()
    raw_states = pd.concat(raw_state_frames, ignore_index=True) if raw_state_frames else pd.DataFrame()
    predictions = pd.concat(prediction_frames, ignore_index=True) if prediction_frames else pd.DataFrame()
    actions = pd.concat(action_frames, ignore_index=True) if action_frames else pd.DataFrame()
    broker_forecasts = (
        pd.concat(broker_forecast_frames, ignore_index=True) if broker_forecast_frames else pd.DataFrame()
    )
    broker_feedback = (
        pd.concat(broker_feedback_frames, ignore_index=True) if broker_feedback_frames else pd.DataFrame()
    )
    client_summary = build_client_summary_from_context(adapter.context)
    slice_completion_latency = build_slice_latency_series_from_context(adapter.context, first_service=False)
    slice_first_service_latency = build_slice_latency_series_from_context(adapter.context, first_service=True)

    state_path = adapter.export_frame(states, output_dir / "online_states.csv")
    raw_state_path = adapter.export_frame(raw_states, output_dir / "online_states_raw.csv")
    prediction_path = adapter.export_frame(predictions, output_dir / "online_predictions.csv")
    action_path = adapter.export_frame(actions, output_dir / "online_actions.csv")
    broker_forecast_path = adapter.export_frame(broker_forecasts, output_dir / "online_broker_forecasts.csv")
    broker_feedback_path = adapter.export_frame(broker_feedback, output_dir / "online_broker_feedback.csv")
    client_summary_path = adapter.export_frame(client_summary, output_dir / "online_client_summary.csv")
    slice_completion_latency_path = adapter.export_frame(
        slice_completion_latency,
        output_dir / "online_slice_completion_latency.csv",
    )
    slice_first_service_latency_path = adapter.export_frame(
        slice_first_service_latency,
        output_dir / "online_slice_first_service_latency.csv",
    )

    policy_graph_path = None
    if render_graph:
        from slicesim.MLGraph import render_ml_policy_graph

        policy_graph_path = render_ml_policy_graph(
            adapter.context,
            graph_output_path or output_dir / "ml_policy_simulation.png",
            actions=actions,
            predictions=predictions,
            policy_label=graph_policy_label,
        )

    result = {
        "state_path": state_path,
        "raw_state_path": raw_state_path,
        "prediction_path": prediction_path,
        "action_path": action_path,
        "broker_forecast_path": broker_forecast_path,
        "broker_feedback_path": broker_feedback_path,
        "client_summary_path": client_summary_path,
        "slice_completion_latency_path": slice_completion_latency_path,
        "slice_first_service_latency_path": slice_first_service_latency_path,
    }
    if policy_graph_path is not None:
        result["policy_graph_path"] = policy_graph_path
    if log_path is not None:
        result["log_path"] = Path(log_path)
    return result


def run_online_baseline(
    config_path: str | Path,
    sla_path: str | Path,
    output_dir: str | Path,
    seed: int | None = None,
    render_graph: bool = False,
    graph_output_path: str | Path | None = None,
    graph_policy_label: str = "Baseline Policy",
    log_path: str | Path | None = None,
) -> dict[str, Path]:
    """Chạy simulator online không dùng action từ ML và xuất đầy đủ artifact của baseline."""
    adapter = OnlineSimulationAdapter(config_path, sla_path, seed=seed)
    raw_state_frames: list[pd.DataFrame] = []

    with _legacy_output_log(log_path) as resolved_log_path:
        while adapter.has_next_window():
            state_window = adapter.run_one_window()
            if state_window.empty:
                continue
            raw_state_frames.append(state_window)

        if resolved_log_path is not None:
            _write_legacy_run_summary(adapter.context)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_states = pd.concat(raw_state_frames, ignore_index=True) if raw_state_frames else pd.DataFrame()
    client_summary = build_client_summary_from_context(adapter.context)
    slice_completion_latency = build_slice_latency_series_from_context(adapter.context, first_service=False)
    slice_first_service_latency = build_slice_latency_series_from_context(adapter.context, first_service=True)

    raw_state_path = adapter.export_frame(raw_states, output_dir / "baseline_states.csv")
    client_summary_path = adapter.export_frame(client_summary, output_dir / "baseline_client_summary.csv")
    slice_completion_latency_path = adapter.export_frame(
        slice_completion_latency,
        output_dir / "baseline_slice_completion_latency.csv",
    )
    slice_first_service_latency_path = adapter.export_frame(
        slice_first_service_latency,
        output_dir / "baseline_slice_first_service_latency.csv",
    )

    policy_graph_path = None
    if render_graph:
        import matplotlib

        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt

        from slicesim.Graph import Graph

        settings = adapter.context.settings
        x_vals = settings["statistics_params"]["x"]
        y_vals = settings["statistics_params"]["y"]
        xlim_left = int(settings["simulation_time"] * settings["statistics_params"]["warmup_ratio"])
        xlim_right = int(settings["simulation_time"] * (1 - settings["statistics_params"]["cooldown_ratio"])) + 1
        policy_graph_path = Path(graph_output_path or output_dir / "baseline_simulation.png")
        policy_graph_path.parent.mkdir(parents=True, exist_ok=True)

        graph = Graph(
            adapter.context.base_stations,
            adapter.context.clients,
            (xlim_left, xlim_right),
            ((x_vals["min"], x_vals["max"]), (y_vals["min"], y_vals["max"])),
            output_dpi=settings["plotting_params"].get("plot_file_dpi", 300),
            scatter_size=settings["plotting_params"].get("scatter_size", 15),
            output_filename=str(policy_graph_path),
        )
        graph.draw_all(
            *adapter.context.stats.get_stats(),
            adapter.context.stats.get_slice_latency_stats(),
            adapter.context.stats.get_slice_first_service_latency_stats(),
        )
        graph.fig.suptitle(f"{graph_policy_label} simulation", fontsize=14, fontweight="bold", y=0.995)
        graph.save_fig()
        plt.close(graph.fig)

    result = {
        "raw_state_path": raw_state_path,
        "client_summary_path": client_summary_path,
        "slice_completion_latency_path": slice_completion_latency_path,
        "slice_first_service_latency_path": slice_first_service_latency_path,
    }
    if policy_graph_path is not None:
        result["policy_graph_path"] = policy_graph_path
    if log_path is not None:
        result["log_path"] = Path(log_path)
    return result
