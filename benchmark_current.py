"""Benchmark the current FAST + danger-aware AI on the same conditions.

Output:
    benchmarks/current_results.json

Run from the project root:
    python benchmark_current.py
"""

from __future__ import annotations

import json
import random
import statistics
from pathlib import Path

from config import FPS
from game import Game


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "benchmarks" / "current_results.json"

CONFIGURATIONS = [
    (5, 5, 1, 3),
    (5, 5, 3, 3),
    (5, 5, 10, 3),
    (6, 6, 1, 3),
    (6, 6, 3, 3),
    (6, 6, 10, 3),
    (7, 7, 1, 3),
    (7, 7, 3, 3),
    (7, 7, 10, 3),
    (10, 10, 1, 3),
    (10, 10, 3, 3),
    (10, 10, 10, 3),
    (15, 15, 1, 2),
    (15, 15, 3, 2),
    (15, 15, 10, 2),
    (20, 20, 1, 2),
    (20, 20, 3, 2),
    (20, 20, 10, 2),
    (30, 30, 1, 1),
    (30, 30, 3, 1),
    (30, 30, 10, 1),
]


def run_game(width, height, apples, seed):
    random.seed(seed)
    game = Game(width, height, apples, Game.SMART)

    limit = width * height * width * height * 4 + 1000
    modes = set()

    while game.running and not game.won and game.moves < limit:
        modes.add(game.ai.mode)
        game.update()

    modes.add(game.ai.mode)

    return {
        "seed": seed,
        "won": bool(game.won),
        "crashed": not game.running,
        "moves": game.moves,
        "length": len(game.snake.body),
        "fast_enabled": bool(game.ai.fast_enabled),
        "modes": sorted(modes),
    }


def main():
    rows = []
    details = []

    for width, height, apples, games in CONFIGURATIONS:
        results = [
            run_game(width, height, apples, seed)
            for seed in range(1, games + 1)
        ]
        details.extend(
            {"width": width, "height": height, "apples": apples, **result}
            for result in results
        )

        won = sum(1 for result in results if result["won"])
        moves = [result["moves"] for result in results]
        avg_moves = statistics.mean(moves)
        game_minutes = avg_moves / FPS / 60.0
        cells = width * height

        rows.append(
            {
                "width": width,
                "height": height,
                "apples": apples,
                "games": games,
                "wins": won,
                "avg_moves": round(avg_moves, 1),
                "game_minutes": round(game_minutes, 1),
                "moves_per_apple": round(avg_moves / max(1, cells - 3), 1),
            }
        )
        print(
            f"{width}x{height} apples={apples}: "
            f"{won}/{games} wins, moves={avg_moves:.0f}, "
            f"game={game_minutes:.1f} min"
        )

    payload = {
        "algorithm": "FAST safe BFS + danger-aware switch to CYCLE",
        "fps": FPS,
        "game_minutes_formula": "moves / FPS / 60",
        "configurations": rows,
        "details": details,
    }

    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"written {RESULTS}")


if __name__ == "__main__":
    main()
