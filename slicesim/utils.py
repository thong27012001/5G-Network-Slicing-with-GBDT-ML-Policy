import logging
import math
from typing import List, Tuple

try:
    from sklearn.neighbors import KDTree as kdt
except Exception:  # pragma: no cover - allows the simulator to run without sklearn
    kdt = None


def distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """
    Tính khoảng cách Euclid giữa hai điểm.
    """
    return math.sqrt(sum((i - j) ** 2 for i, j in zip(a, b)))


def _query_nearest(client_coordinates, base_station_coordinates, k: int = 1):
    """
    Tìm base station gần nhất bằng sklearn nếu có, nếu không thì dùng cách duyệt trực tiếp.
    """
    if not base_station_coordinates:
        return [], []

    effective_k = min(k, len(base_station_coordinates))
    if kdt is not None:
        tree = kdt(base_station_coordinates, leaf_size=2)
        return tree.query(client_coordinates, k=effective_k)

    distances = []
    indices = []
    for client_coordinate in client_coordinates:
        ranked = sorted(
            (
                (distance(client_coordinate, base_station_coordinate), base_station_index)
                for base_station_index, base_station_coordinate in enumerate(base_station_coordinates)
            ),
            key=lambda item: item[0],
        )[:effective_k]
        distances.append([item[0] for item in ranked])
        indices.append([item[1] for item in ranked])
    return distances, indices


def kdtree(clients, base_stations):
    """
    Gán client vào base station bằng cách tìm láng giềng gần nhất.
    """
    client_coordinates = [(client.x, client.y) for client in clients]
    base_station_coordinates = [base_station.coverage.center for base_station in base_stations]
    distances, indices = _query_nearest(client_coordinates, base_station_coordinates, k=1)

    for client, nearest_distances, nearest_indices in zip(clients, distances, indices):
        if nearest_distances[0] <= base_stations[nearest_indices[0]].coverage.radius:
            client.base_station = base_stations[nearest_indices[0]]


class KDTree:
    last_run_time = None
    limit = None

    @staticmethod
    def run(clients, base_stations, run_at: int, assign: bool = True):
        """
        Chạy bước gán láng giềng gần nhất cho client và base station.
        """
        logging.debug(f"KDTREE CALL [{run_at}] - limit: {KDTree.limit}")
        if run_at == KDTree.last_run_time:
            return
        KDTree.last_run_time = run_at

        client_coordinates = [(client.x, client.y) for client in clients]
        base_station_coordinates = [base_station.coverage.center for base_station in base_stations]
        k = min(KDTree.limit, len(base_stations)) if KDTree.limit else len(base_stations)
        distances, indices = _query_nearest(client_coordinates, base_station_coordinates, k=k)

        for client, nearest_distances, nearest_indices in zip(clients, distances, indices):
            if assign and nearest_distances[0] <= base_stations[nearest_indices[0]].coverage.radius:
                client.base_station = base_stations[nearest_indices[0]]
            client.closest_base_stations = [
                (nearest_distance, base_stations[base_station_index])
                for nearest_distance, base_station_index in zip(nearest_distances, nearest_indices)
            ]


def format_bps(size: float, pos=None, return_float: bool = False) -> str:
    """
    Định dạng giá trị bit trên giây thành chuỗi dễ đọc hơn.
    """
    power, n = 1000, 0
    power_labels = {0: "", 1: "K", 2: "M", 3: "G", 4: "T"}
    while size >= power:
        size /= power
        n += 1
    if return_float:
        return f"{size:.3f} {power_labels[n]}bps"
    return f"{size:.0f} {power_labels[n]}bps"
