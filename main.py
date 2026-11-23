# main.py

import os

# Окно приложения должно открываться по центру экрана.
os.environ.setdefault("SDL_VIDEO_CENTERED", "1")

import pygame

from competition import Competition
from config import COMPETITION_TARGET, FPS
from game import Game
from menu import Menu
from ui import UI


def main() -> None:
    """
    Графическое меню → игра (или соревнование) → снова меню.

    Никакого консольного ввода: размер поля, число яблок, скорость
    и режим выбираются в окне меню.
    """
    pygame.init()

    try:
        menu = Menu()

        while True:

            settings = menu.run()

            if settings is None:
                break

            if settings["mode"] == Game.COMPETITION:

                competition = Competition(
                    settings["width"],
                    settings["height"],
                    settings["apple_count"],
                    target=settings.get(
                        "competition_target",
                        COMPETITION_TARGET,
                    ),
                    full_board=settings.get(
                        "competition_full_board",
                        False,
                    ),
                    fps=settings.get("fps", FPS),
                )

                action = competition.run()

                menu.set_defaults(
                    settings["width"],
                    settings["height"],
                    settings["apple_count"],
                    Game.COMPETITION,
                    settings.get(
                        "competition_target",
                        COMPETITION_TARGET,
                    ),
                    settings.get(
                        "competition_full_board",
                        False,
                    ),
                    speed=settings.get("fps", FPS),
                )

            else:

                game = Game(
                    settings["width"],
                    settings["height"],
                    settings["apple_count"],
                    settings["mode"],
                )

                ui = UI(
                    game,
                    fps=settings.get("fps", FPS),
                )

                action = ui.run()

                # Запоминаем параметры последней партии для следующего меню.
                # ui.game может быть уже новым объектом после перезапуска (R).
                menu.set_defaults(
                    ui.game.board.width,
                    ui.game.board.height,
                    ui.game.apple_count,
                    ui.game.mode,
                    speed=ui.fps,
                )

            if action == "quit":
                break

    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
