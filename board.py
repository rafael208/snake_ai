# board.py

from typing import Iterable


class Board:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height

    def is_inside(self, position: tuple[int, int]) -> bool:
        x, y = position

        return (
            0 <= x < self.width
            and 0 <= y < self.height
        )

    def neighbors(
        self,
        position: tuple[int, int]
    ) -> list[tuple[int, int]]:

        x, y = position

        directions = (
            (0, -1),
            (1, 0),
            (0, 1),
            (-1, 0)
        )

        result = []

        for dx, dy in directions:
            new_position = (
                x + dx,
                y + dy
            )

            if self.is_inside(new_position):
                result.append(new_position)

        return result

    def all_cells(self) -> Iterable[tuple[int, int]]:
        for y in range(self.height):
            for x in range(self.width):
                yield x, y

    @property
    def total_cells(self) -> int:
        return self.width * self.height