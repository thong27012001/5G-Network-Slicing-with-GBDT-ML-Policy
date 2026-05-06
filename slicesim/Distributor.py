class Distributor:
    def __init__(self, name: str, distribution, *dist_params, divide_scale: float = 1):
        """
        Khởi tạo bộ sinh phân phối cho usage hoặc chuyển động.
        """
        self.name = name
        self.distribution = distribution
        self.dist_params = dist_params
        self.divide_scale = divide_scale

    def generate(self) -> float:
        """
        Sinh ra một giá trị từ phân phối.
        """
        return self.distribution(*self.dist_params)

    def generate_scaled(self) -> float:
        """
        Sinh ra một giá trị từ phân phối và chia theo hệ số scale.
        """
        return self.distribution(*self.dist_params) / self.divide_scale

    def generate_movement(self) -> tuple:
        """
        Sinh ra bộ giá trị chuyển động `(x, y)` từ phân phối.
        """
        x = self.distribution(*self.dist_params) / self.divide_scale
        y = self.distribution(*self.dist_params) / self.divide_scale
        return x, y

    def __str__(self) -> str:
        dist_name = getattr(self.distribution, '__name__', str(self.distribution))
        return f'[{self.name}: {dist_name}: {self.dist_params}]'
