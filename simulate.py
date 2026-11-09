# simulate.py
"""
Проверка автопилота без графики.

    python simulate.py                 # быстрый набор полей
    python simulate.py 15 9 3 20       # поле 15x9, 3 яблока, 20 партий

Для каждой партии проверяется: победа, отсутствие столкновений
и отсутствие "зацикливания" (лимит ходов).
"""

import random
import sys
import time

from game import Game


def play(width, height, apples, seed):
    random.seed(seed)
    game = Game(width, height, apples, Game.SMART)

    # Честная верхняя граница: ~1 круг на каждое яблоко.
    limit = game.board.total_cells ** 2 + 1000

    while game.running and not game.won and game.moves < limit:
        game.update()

    if game.won:
        return "WIN", game.moves
    if not game.running:
        return "CRASH", game.moves
    return "STUCK", game.moves


def run(width, height, apples, games):
    results = [play(width, height, apples, seed) for seed in range(games)]
    wins = sum(1 for r, _ in results if r == "WIN")
    moves = [m for r, m in results if r == "WIN"]
    avg = sum(moves) / len(moves) if moves else 0
    cells = width * height
    print(
        f"{width:>2}x{height:<2} яблок={apples:<2} "
        f"побед {wins}/{games}  "
        f"ходов в среднем {avg:8.0f}  "
        f"(на яблоко {avg / max(cells - 3, 1):5.1f}, "
        f"чистый цикл ~ {cells / 2:5.1f})"
    )
    return wins == games


def main():
    if len(sys.argv) >= 4:
        w, h, a = map(int, sys.argv[1:4])
        n = int(sys.argv[4]) if len(sys.argv) > 4 else 10
        ok = run(w, h, a, n)
    else:
        ok = True
        start = time.time()
        for w, h in [(5, 5), (6, 5), (5, 6), (7, 7), (8, 8),
                     (9, 6), (11, 13), (10, 10), (15, 15), (20, 20)]:
            for a in (1, 3, 10):
                ok &= run(w, h, a, 5)
        print(f"Время: {time.time() - start:.1f} с")

    print("ВСЁ OK" if ok else "ЕСТЬ ПРОБЛЕМЫ")


if __name__ == "__main__":
    main()
