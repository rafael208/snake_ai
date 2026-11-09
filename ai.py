# ai.py (историческая жадная версия)

from collections import deque


class SnakeAI:
    """Простой жадный автопилот: идёт к ближайшему яблоку по BFS."""

    def __init__(self, board):
        self.board = board
        self.neighbors = {
            cell: board.neighbors(cell)
            for cell in board.all_cells()
        }

    def choose_move(self, snake_body, apples):
        body = list(snake_body)
        apples = set(apples or ())
        if not body:
            return None

        head = body[0]
        tail = body[-1]
        blocked = set(body)
        blocked.discard(tail)

        previous = {head: None}
        queue = deque([head])

        while queue:
            current = queue.popleft()
            for neighbor in self.neighbors[current]:
                if neighbor in previous or neighbor in blocked:
                    continue
                previous[neighbor] = current
                queue.append(neighbor)

        targets = [apple for apple in apples if apple in previous]
        if not targets:
            return None

        target = min(
            targets,
            key=lambda apple: self._path_length(previous, head, apple),
        )

        path = []
        cell = target
        while cell != head:
            path.append(cell)
            cell = previous[cell]
        path.reverse()
        return path[0]

    @staticmethod
    def _path_length(previous, head, target):
        length = 0
        cell = target
        while cell != head:
            length += 1
            cell = previous[cell]
        return length
