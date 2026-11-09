# pathfinding.py

import heapq
from collections import deque

from board import Board


# ============================================================
# МАНХЭТТЕНСКОЕ РАССТОЯНИЕ
# ============================================================

def manhattan_distance(
    a: tuple[int, int],
    b: tuple[int, int]
) -> int:

    return (
        abs(a[0] - b[0])
        + abs(a[1] - b[1])
    )


# ============================================================
# A*
# ============================================================

def a_star(
    board: Board,
    start: tuple[int, int],
    goal: tuple[int, int],
    blocked: set[tuple[int, int]]
):

    if start == goal:
        return []

    open_set = []

    counter = 0

    heapq.heappush(
        open_set,
        (
            0,
            counter,
            start
        )
    )

    came_from = {}

    g_score = {
        start: 0
    }

    visited = set()

    while open_set:

        _, _, current = heapq.heappop(
            open_set
        )

        if current in visited:
            continue

        visited.add(current)

        if current == goal:

            path = []

            while current != start:

                path.append(current)

                current = came_from[current]

            path.reverse()

            return path

        for neighbor in board.neighbors(
            current
        ):

            if neighbor in blocked:
                continue

            new_cost = (
                g_score[current] + 1
            )

            if (
                neighbor not in g_score
                or new_cost < g_score[neighbor]
            ):

                g_score[neighbor] = new_cost

                came_from[neighbor] = current

                priority = (
                    new_cost
                    + manhattan_distance(
                        neighbor,
                        goal
                    )
                )

                counter += 1

                heapq.heappush(
                    open_set,
                    (
                        priority,
                        counter,
                        neighbor
                    )
                )

    return None


# ============================================================
# BFS С РАССТОЯНИЯМИ
# ============================================================

def flood_fill_distances(
    board: Board,
    start: tuple[int, int],
    blocked: set[tuple[int, int]]
):
    """
    Возвращает словарь:

        клетка -> расстояние от start

    Например:

        {
            (3, 4): 0,
            (3, 5): 1,
            (4, 5): 2,
            ...
        }

    Это позволяет сразу узнать:

    - сколько пространства доступно;
    - какие яблоки доступны;
    - насколько далеко яблоки;
    - можно ли добраться до хвоста.
    """

    if start in blocked:
        return {}

    distances = {
        start: 0
    }

    queue = deque([start])

    while queue:

        current = queue.popleft()

        current_distance = (
            distances[current]
        )

        for neighbor in board.neighbors(
            current
        ):

            if neighbor in distances:
                continue

            if neighbor in blocked:
                continue

            distances[neighbor] = (
                current_distance + 1
            )

            queue.append(neighbor)

    return distances


# ============================================================
# ДОСТУПНАЯ ПЛОЩАДЬ
# ============================================================

def reachable_area(
    board: Board,
    start: tuple[int, int],
    snake_body
):

    blocked = set(snake_body)

    # Хвост скоро освободится.
    blocked.discard(
        snake_body[-1]
    )

    distances = flood_fill_distances(
        board,
        start,
        blocked
    )

    return len(distances)


# ============================================================
# ДОСТУПЕН ЛИ ХВОСТ
# ============================================================

def can_reach_tail(
    board: Board,
    snake_body
):

    if len(snake_body) <= 2:
        return True

    head = snake_body[0]
    tail = snake_body[-1]

    blocked = set(snake_body)

    blocked.discard(head)
    blocked.discard(tail)

    distances = flood_fill_distances(
        board,
        head,
        blocked
    )

    return tail in distances