import math


class Coverage:
    def __init__(self, center: tuple, radius: float):
        """
        Khởi tạo vùng phủ với tâm và bán kính.
        """
        self.center = center
        self.radius = radius

    def _get_gaussian_distance(self, p: tuple) -> float:
        """
        Tính khoảng cách Euclid từ điểm p tới tâm vùng phủ.
        """
        return math.sqrt(sum((i-j)**2 for i,j in zip(p, self.center)))

    def is_in_coverage(self, x: float, y: float) -> bool:
        """
        Kiểm tra xem điểm `(x, y)` có nằm trong bán kính phủ sóng hay không.
        """
        return self._get_gaussian_distance((x,y)) <= self.radius

    def __str__(self) -> str:
        x, y = self.center
        return f'[c=({x:<4}, {y:>4}), r={self.radius:>4}]'
