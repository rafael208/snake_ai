# game.py

import random
from collections import deque

from board import Board
from snake import Snake
from ai import SnakeAI


class Game:
    SMART = "SMART"
    MANUAL = "MANUAL"
    COMPETITION = "COMPETITION"

    def __init__(
        self,
        width: int,
        height: int,
        apple_count: int,
        mode: str = SMART,
        rng=None,
    ):

        self.board = Board(
            width,
            height
        )

        # Свой генератор случайных чисел позволяет двум партиям
        # соревнования не влиять на появление яблок друг у друга.
        self.rng = rng if rng is not None else random

        start = (
            width // 2,
            height // 2
        )

        self.snake = Snake(
            start,
            initial_length=3
        )

        self.ai = SnakeAI(
            self.board
        )

        self.apples = set()

        self.apple_count = apple_count

        self.mode = mode

        self.running = True
        self.paused = False
        self.won = False

        self.moves = 0

        self.last_ai_move = None

        self.spawn_initial_apples()

    # ========================================================
    # ЯБЛОКИ
    # ========================================================

    def spawn_initial_apples(self):

        while len(self.apples) < self.apple_count:

            cell = (
                self.rng.randrange(
                    self.board.width
                ),
                self.rng.randrange(
                    self.board.height
                )
            )

            if cell in self.snake.body:
                continue

            if cell in self.apples:
                continue

            self.apples.add(cell)

    def spawn_apple(self):

        free_cells = []

        occupied = set(
            self.snake.body
        )

        occupied.update(
            self.apples
        )

        for cell in self.board.all_cells():

            if cell not in occupied:
                free_cells.append(cell)

        if not free_cells:
            return

        self.apples.add(
            self.rng.choice(
                free_cells
            )
        )

    # ========================================================
    # ХОД ЗМЕЙКИ
    # ========================================================

    def move(self, new_head):

        if new_head is None:
            self.running = False
            return

        current_head = self.snake.head

        # Проверяем, соседняя ли клетка.
        if new_head not in self.board.neighbors(
            current_head
        ):
            return

        eating = (
            new_head in self.apples
        )

        occupied = set(
            self.snake.body
        )

        # Хвост уйдет при обычном движении.
        if not eating:
            occupied.discard(
                self.snake.tail
            )

        # Столкновение.
        if new_head in occupied:

            self.running = False
            return

        # Двигаемся.
        self.snake.move(
            new_head,
            grow=eating
        )

        self.moves += 1

        if eating:

            self.apples.remove(
                new_head
            )

            self.spawn_apple()

        # Победа: змейка заняла всё поле
        # (проверяем здесь, чтобы работало и в MANUAL).
        if len(self.snake.body) >= self.board.total_cells:
            self.won = True

    # ========================================================
    # SMART
    # ========================================================

    def update_smart(self):

        new_head = self.ai.choose_move(
            self.snake.body,
            self.apples
        )

        self.last_ai_move = new_head

        self.move(
            new_head
        )

    # ========================================================
    # ПЕРЕКЛЮЧЕНИЕ РЕЖИМА
    # ========================================================

    def set_mode(self, mode):

        self.mode = mode

    # ========================================================
    # ОБНОВЛЕНИЕ
    # ========================================================

    def update(self):

        if (
            self.paused
            or not self.running
            or self.won
        ):
            return

        if self.mode == self.SMART:

            self.update_smart()

        # В MANUAL режиме
        # движение выполняется из UI
        # по нажатию клавиш.

        if len(self.snake.body) >= (
            self.board.total_cells
        ):

            self.won = True