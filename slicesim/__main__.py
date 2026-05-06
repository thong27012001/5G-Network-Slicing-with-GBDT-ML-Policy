import logging
import os
import sys

from .Graph import Graph
from .runtime import build_simulation_context, load_config_file


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if len(sys.argv) != 2:
        logging.error("Please type an input file.")
        logging.error("python -m slicesim <input-file>")
        exit(1)

    config_filename = os.path.join(os.path.dirname(__file__), sys.argv[1])
    try:
        data = load_config_file(config_filename)
    except FileNotFoundError:
        logging.error(f"File Not Found: {config_filename}")
        exit(0)
    except Exception as exc:
        logging.error(f"Error reading config: {exc}")
        exit(1)

    try:
        context = build_simulation_context(data)
    except Exception as exc:
        logging.error(f"Config validation error: {exc}")
        exit(1)

    settings = context.settings
    base_stations = context.base_stations
    clients = context.clients
    stats = context.stats

    root_logger = logging.getLogger()
    file_handler = None
    previous_disable_level = logging.root.manager.disable
    if settings["logging"]:
        file_handler = logging.FileHandler(settings["log_file"], mode="w", encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(message)s"))
        root_logger.addHandler(file_handler)
    else:
        logging.disable(logging.CRITICAL)

    context.env.process(stats.collect())
    context.env.run(until=int(settings["simulation_time"]))

    for client in clients:
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

    logging.info(stats.get_stats())

    # PRB / resource allocation proxy export (NetSim-inspired). See docs/prb_proxy_metrics.md.
    prb_export_config = settings.get("prb_export", {}) or {}
    if prb_export_config.get("enabled", False):
        scenario_stem = os.path.splitext(os.path.basename(sys.argv[1]))[0]
        output_dir_template = str(prb_export_config.get(
            "output_dir", "artifacts/prb_metrics/<scenario_name>"
        ))
        output_dir = output_dir_template.replace("<scenario_name>", scenario_stem)
        artifacts = stats.export_prb_csv(output_dir)
        if artifacts:
            previous_disable_for_export = logging.root.manager.disable
            logging.disable(logging.NOTSET)
            for name, path in artifacts.items():
                logging.info(f"[PRB] {name}: {path}")
            logging.disable(previous_disable_for_export)

    if settings["plotting_params"]["plotting"]:
        x_vals = settings["statistics_params"]["x"]
        y_vals = settings["statistics_params"]["y"]
        xlim_left = int(settings["simulation_time"] * settings["statistics_params"]["warmup_ratio"])
        xlim_right = int(
            settings["simulation_time"] * (1 - settings["statistics_params"]["cooldown_ratio"])
        ) + 1

        graph = Graph(
            base_stations,
            clients,
            (xlim_left, xlim_right),
            ((x_vals["min"], x_vals["max"]), (y_vals["min"], y_vals["max"])),
            output_dpi=settings["plotting_params"]["plot_file_dpi"],
            scatter_size=settings["plotting_params"]["scatter_size"],
            output_filename=settings["plotting_params"]["plot_file"],
        )
        graph.draw_all(
            *stats.get_stats(),
            stats.get_slice_latency_stats(),
            stats.get_slice_first_service_latency_stats(),
        )
        if settings["plotting_params"]["plot_save"]:
            graph.save_fig()
        if settings["plotting_params"]["plot_show"]:
            graph.show_plot()

    if file_handler is not None:
        root_logger.removeHandler(file_handler)
        file_handler.close()
    logging.disable(previous_disable_level)


if __name__ == "__main__":
    main()
