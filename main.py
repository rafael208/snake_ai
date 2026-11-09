# main.py (историческая CLI-версия)

from game import Game


def main() -> None:
    print("Snake AI — консольный запуск")
    width = int(input("Ширина поля (5–30): "))
    height = int(input("Высота поля (5–30): "))
    apples = int(input("Количество яблок: "))

    game = Game(width, height, apples, Game.SMART)

    while game.running and not game.won:
        game.update()

    if game.won:
        print(f"Победа! Ходов: {game.moves}")
    else:
        print(f"Проигрыш. Ходов: {game.moves}")


if __name__ == "__main__":
    main()
