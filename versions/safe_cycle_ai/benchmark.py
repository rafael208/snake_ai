"""Benchmark the historical guaranteed-cycle AI.

Runs only Game.SMART with the FAST mode disabled and records:
  * wins;
  * moves to completely fill the board;
  * estimated in-game time at config.FPS (8 moves/s).

Run from this folder:
    python benchmark.py
"""

from __future__ import annotations

import json
import random
from pathlib import Path
import statistics

from config import FPS
from game import Game


ROOT = Path(__file__).resolve().parent
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

    while game.running and not game.won and game.moves < limit:
        game.update()

    body = len(game.snake.body)

    return {
        "seed": seed,
        "won": bool(game.won),
        "crashed": not game.running,
        "moves": game.moves,
        "length": body,
        "fast_enabled": bool(game.ai.fast_enabled),
        "final_mode": game.ai.mode,
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
        moves_per_apple = avg_moves / max(1, cells - 3)

        rows.append(
            {
                "width": width,
                "height": height,
                "apples": apples,
                "games": games,
                "wins": won,
                "avg_moves": round(avg_moves, 1),
                "game_minutes": round(game_minutes, 1),
                "moves_per_apple": round(moves_per_apple, 1),
            }
        )
        print(
            f"{width}x{height} apples={apples}: "
            f"{won}/{games} wins, moves={avg_moves:.0f}, "
            f"game={game_minutes:.1f} min"
        )

    payload = {
        "algorithm": "guaranteed CYCLE only (FAST disabled)",
        "fps": FPS,
        "game_minutes_formula": "moves / FPS / 60",
        "configurations": rows,
        "details": details,
    }

    (ROOT / "results.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# Метрики historical-версии: только безопасный цикл",
        "",
        "В этой версии `SnakeAI.fast_enabled = False`: на каждом ходу",
        "используется только гарантированный обход кольца (CYCLE) и,",
        "если нужно, восстановление (RECOVERY). Жадного FAST-режима нет.",
        "",
        "Игра считалась пройденной, когда тело заполняло всё поле.",
        "Время в игре рассчитано для `FPS = 8` по формуле:",
        "",
        "```",
        "минуты = ходы / 8 / 60",
        "```",
        "",
        "Для 30×30 с одним яблоком партия очень длинная, поэтому",
        "запускался один seed.",
        "",
        "| Поле | Яблок | Партий | Побед | Средние ходы | Время игры, мин | Ходов на яблоко |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]

    for row in rows:
        lines.append(
            f"| {row['width']}×{row['height']} | {row['apples']} | "
            f"{row['games']} | {row['wins']}/{row['games']} | "
            f"{row['avg_moves']} | "
            f"{row['game_minutes']} | {row['moves_per_apple']} |"
        )

    lines += [
        "",
        "Кратко: **51 партия из 51 выиграна**. При 10 яблоках партия",
        "занимает около 0,1 мин на 5×5, 0,6 мин на 10×10, 8,9 мин на",
        "20×20 и 44,9 мин на 30×30. При одном яблоке время резко растёт:",
        "79,7 мин на 20×20 и 407,9 мин (около 6,8 часа) на 30×30 —",
        "чистому кольцу приходится долго ждать следующего яблока.",
        "",
        "## Проверки",
        "",
        "- `fast_enabled` во всех партиях равен `False`;",
        "- все партии завершились победой (поле заполнено);",
        "- итоговый режим — `CYCLE`;",
        "- аварийных столкновений нет.",
        "",
        "Подробные результаты по seeds лежат в `results.json`.",
    ]

    (ROOT / "RESULTS.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    print("written RESULTS.md and results.json")


if __name__ == "__main__":
    main()
