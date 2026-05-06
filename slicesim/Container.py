class Container:
    def __init__(self, init: float, capacity: float):
        """
        Khởi tạo một container với mức ban đầu và dung lượng tối đa.
        """
        self.capacity = capacity
        self.level = init
    
    def get(self, amount: float) -> bool:
        """
        Thử lấy ra một lượng `amount` khỏi container. Trả về True nếu thành công.
        """
        if amount <= self.level:
            self.level -= amount
            return True
        else:
            return False

    def put(self, amount: float) -> bool:
        """
        Thử thêm một lượng `amount` vào container. Trả về True nếu thành công.
        """
        if amount + self.level <= self.capacity:
            self.level += amount
            return True
        else:
            return False

    def __str__(self) -> str:
        return f'Container(level={self.level}, capacity={self.capacity})'
