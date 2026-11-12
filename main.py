# main.py (промежуточная версия: меню без соревнования)

import pygame

from game import Game
from menu import Menu
from ui import UI


def main() -> None:
    pygame.init()

    try:
        menu = Menu()

        while True:
            settings = menu.run()
            if settings is None:
                break

            mode = settings["mode"]
            if mode == Game.COMPETITION:
                # Соревнование появится в следующем коммите.
                mode = Game.SMART

            game = Game(
                settings["width"],
                settings["height"],
                settings["apple_count"],
                mode,
            )
            ui = UI(game)
            action = ui.run()

            menu.set_defaults(
                game.board.width,
                game.board.height,
                game.apple_count,
                game.mode,
            )

            if action == "quit":
                break
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
