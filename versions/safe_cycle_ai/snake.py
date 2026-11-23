# snake.py

from collections import deque
from copy import deepcopy


class Snake:
    def __init__(
        self,
        start_position: tuple[int, int],
        initial_length: int = 3
    ):
        x, y = start_position

        self.body = deque()

        for i in range(initial_length):
            self.body.append(
                (x - i, y)
            )

        self.direction = (1, 0)

    @property
    def head(self) -> tuple[int, int]:
        return self.body[0]

    @property
    def tail(self) -> tuple[int, int]:
        return self.body[-1]

    @property
    def length(self) -> int:
        return len(self.body)

    def contains(self, position: tuple[int, int]) -> bool:
        return position in self.body

    def move(
        self,
        new_head: tuple[int, int],
        grow: bool = False
    ) -> None:

        self.body.appendleft(new_head)

        if not grow:
            self.body.pop()

    def clone_body(self) -> deque:
        return deepcopy(self.body)