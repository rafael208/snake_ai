# ui.py

import math
from pathlib import Path

import pygame

from config import (
    ACCENT_COLOR,
    BOARD_BORDER_COLOR,
    BOARD_COLOR,
    DANGER_COLOR,
    FPS,
    HUD_HEIGHT,
    MUTED_TEXT_COLOR,
    RENDER_FPS,
    SHOW_AI_PATH,
    SNAKE_BODY_COLOR,
    SNAKE_HEAD_COLOR,
    SUCCESS_COLOR,
    TEXT_COLOR,
)

from game import Game
from layout import center_window, compute_game_layout


ASSET_DIR = Path(__file__).resolve().parent / "assets"


class UI:

    def __init__(
        self,
        game: Game,
        screen=None,
        layout=None,
    ):

        self.game = game

        self.previous_body = list(game.snake.body)
        self.animation_start = pygame.time.get_ticks()
        self.animation_duration = 1000.0 / FPS
        self.trail = []

        self.layout = layout or compute_game_layout(
            game.board.width,
            game.board.height,
        )

        if screen is None:
            self.screen = pygame.display.set_mode(
                (
                    self.layout.window_width,
                    self.layout.window_height,
                )
            )

            pygame.display.set_caption(
                f"Snake AI — {game.board.width}×"
                f"{game.board.height}"
            )

            center_window()
        else:
            # Режим соревнования рисует в обычную Surface,
            # а затем отправляет её в своё окно SDL2.
            self.screen = screen

        self.clock = pygame.time.Clock()

        self._fonts = {}

        # В соревновании окна называют себя «ИИ» и «ИГРОК».
        self.mode_label = None

        # Набор PNG-ассетов: blue — обычная игра, green — ИИ.
        self.asset_theme = "blue"
        self._assets = {}
        self._scaled_assets = {}
        self._rotated_assets = {}
        self._shadow_assets = {}

        # Кэш статичного фона, доски и подложки HUD: перерисовываем
        # их только при изменении размера окна.
        self._background_cache = None
        self._background_key = None
        self._board_cache = None
        self._board_key = None
        self._hud_cache = None
        self._hud_key = None

        self.manual_direction = (
            1,
            0
        )

        self._sync_manual_direction()

        self.show_path = SHOW_AI_PATH

        self.exit_action = None

        # Цвета змейки (в соревновании у игрока они синие).
        self.snake_head_color = SNAKE_HEAD_COLOR
        self.snake_body_color = SNAKE_BODY_COLOR

        # Необязательные строки для HUD (используются соревнованием).
        self.extra_status = None
        self.extra_controls = None

        # В игре клавиши не должны повторяться: ход делает игровой цикл.
        pygame.key.set_repeat(0)

        self._reset_trail()

    # ========================================================
    # ГЕОМЕТРИЯ
    # ========================================================

    @property
    def cell_size(self) -> int:
        return self.layout.cell_size

    def cell_center(self, x: int, y: int) -> tuple[int, int]:
        return self.layout.cell_center(x, y)

    def cell_rect(self, x: int, y: int) -> pygame.Rect:
        return self.layout.cell_rect(x, y)

    # ========================================================
    # ШРИФТЫ
    # ========================================================

    def _font(self, size: int, bold: bool = False) -> pygame.font.Font:
        key = (int(size), bool(bold))

        font = self._fonts.get(key)

        if font is None:
            font = pygame.font.SysFont(
                "Segoe UI",
                int(size),
                bold=bool(bold),
            )
            self._fonts[key] = font

        return font

    def _fit_surface(
        self,
        text: str,
        size: int,
        max_width: int,
        color,
        bold: bool = False,
    ) -> pygame.Surface:
        """Рендер с уменьшением шрифта, пока строка не влезет по ширине."""
        current = int(size)

        while current > 9:
            surface = self._font(current, bold).render(text, True, color)
            if surface.get_width() <= max_width:
                return surface
            current -= 1

        return self._font(9, bold).render(text, True, color)

    # ========================================================
    # ЦВЕТА И СТАТИЧНЫЕ ПОДЛОЖКИ
    # ========================================================

    @staticmethod
    def _mix(color_a, color_b, t: float):
        t = max(0.0, min(1.0, t))
        return tuple(
            int(a + (b - a) * t)
            for a, b in zip(color_a, color_b)
        )

    def _vertical_gradient(
        self,
        size: tuple[int, int],
        top,
        bottom,
    ) -> pygame.Surface:
        width, height = size
        surface = pygame.Surface(size)

        for y in range(height):
            t = y / max(1, height - 1)
            pygame.draw.line(
                surface,
                self._mix(top, bottom, t),
                (0, y),
                (width, y),
            )

        return surface

    def _build_background(self) -> None:
        width, height = self.screen.get_size()
        key = (width, height)

        if self._background_key == key and self._background_cache:
            return

        surface = self._vertical_gradient(
            (width, height),
            (6, 13, 9),
            (14, 30, 20),
        )

        # Мягкое свечение в центре поля.
        glow = pygame.Surface((width, height), pygame.SRCALPHA)
        glow_x = width // 2
        glow_y = max(1, int(self.layout.hud_y * 0.52))
        max_radius = max(width, height)

        for step in range(18, 0, -1):
            radius = int(max_radius * step / 18)
            alpha = max(1, 3 + step // 3)
            pygame.draw.circle(
                glow,
                (40, 120, 82, alpha),
                (glow_x, glow_y),
                radius,
            )

        surface.blit(glow, (0, 0))

        # Едва заметная сетка на фоне.
        for x in range(0, width, 40):
            pygame.draw.line(
                surface,
                (20, 38, 28),
                (x, 0),
                (x, height),
            )
        for y in range(0, height, 40):
            pygame.draw.line(
                surface,
                (20, 38, 28),
                (0, y),
                (width, y),
            )

        self._background_cache = surface
        self._background_key = key

    def _build_board(self) -> None:
        width = self.layout.grid_width
        height = self.layout.grid_height
        cell = self.layout.cell_size
        key = (width, height, cell)

        if self._board_key == key and self._board_cache:
            return

        surface = pygame.Surface((width, height), pygame.SRCALPHA)

        pygame.draw.rect(
            surface,
            BOARD_COLOR,
            (0, 0, width, height),
            border_radius=14,
        )

        # Шахматные клетки — готовые PNG-тайлы, без сетки и пиксельных
        # линий. smoothscale сглаживает их под текущий размер клетки.
        for y in range(self.game.board.height):
            for x in range(self.game.board.width):
                name = (
                    "board_light"
                    if (x + y) % 2 == 0
                    else "board_dark"
                )
                surface.blit(
                    self._scaled_asset(name, cell),
                    (x * cell, y * cell),
                )

        # Верхний блик рамки.
        pygame.draw.line(
            surface,
            (73, 132, 99),
            (18, 1),
            (width - 18, 1),
            1,
        )

        # Скругляем углы маской.
        mask = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.rect(
            mask,
            (255, 255, 255, 255),
            (0, 0, width, height),
            border_radius=14,
        )
        surface.blit(
            mask,
            (0, 0),
            special_flags=pygame.BLEND_RGBA_MULT,
        )

        self._board_cache = surface
        self._board_key = key

    def _build_hud(self) -> None:
        width = self.layout.window_width
        key = width

        if self._hud_key == key and self._hud_cache:
            return

        surface = self._vertical_gradient(
            (width, HUD_HEIGHT),
            (15, 35, 24),
            (8, 20, 13),
        )

        pygame.draw.line(
            surface,
            (48, 88, 64),
            (0, 0),
            (width, 0),
            2,
        )
        pygame.draw.line(
            surface,
            (30, 65, 44),
            (0, 2),
            (width, 2),
            1,
        )

        self._hud_cache = surface
        self._hud_key = key

    # ========================================================
    # PNG-АССЕТЫ
    # ========================================================

    def _asset(self, name: str) -> pygame.Surface:
        image = self._assets.get(name)

        if image is None:
            path = ASSET_DIR / f"{name}.png"
            image = pygame.image.load(str(path))

            if pygame.display.get_surface() is not None:
                image = image.convert_alpha()

            self._assets[name] = image

        return image

    def _scaled_asset(self, name: str, size: int) -> pygame.Surface:
        key = (name, int(size))
        image = self._scaled_assets.get(key)

        if image is None:
            image = pygame.transform.smoothscale(
                self._asset(name),
                (int(size), int(size)),
            )
            self._scaled_assets[key] = image

        return image

    def _sprite(
        self,
        name: str,
        size: int,
        angle: int = 0,
    ) -> pygame.Surface:
        key = (name, int(size), int(angle) % 360)
        image = self._rotated_assets.get(key)

        if image is None:
            image = self._scaled_asset(name, size)
            if angle:
                image = pygame.transform.rotate(image, angle)
            self._rotated_assets[key] = image

        return image

    def _shadow(
        self,
        name: str,
        size: int,
        angle: int = 0,
    ) -> pygame.Surface:
        key = (name, int(size), int(angle) % 360)
        image = self._shadow_assets.get(key)

        if image is None:
            image = self._sprite(name, size, angle).copy()
            image.fill(
                (0, 0, 0, 105),
                special_flags=pygame.BLEND_RGBA_MULT,
            )
            self._shadow_assets[key] = image

        return image

    def _blit_tile(
        self,
        name: str,
        center: tuple[int, int],
        size: int,
        angle: int = 0,
        shadow: bool = True,
    ) -> None:
        if shadow:
            draw_size = size + 2
            shadow_sprite = self._shadow(name, draw_size, angle)
            self.screen.blit(
                shadow_sprite,
                (
                    center[0] - draw_size // 2 + 2,
                    center[1] - draw_size // 2 + 3,
                ),
            )

        draw_size = size + 2
        sprite = self._sprite(name, draw_size, angle)
        self.screen.blit(
            sprite,
            (
                center[0] - draw_size // 2,
                center[1] - draw_size // 2,
            ),
        )

    # ========================================================
    # НАПРАВЛЕНИЕ
    # ========================================================

    def _sync_manual_direction(self) -> None:
        body = self.game.snake.body

        if len(body) < 2:
            self.manual_direction = (1, 0)
            return

        head_x, head_y = body[0]
        neck_x, neck_y = body[1]

        dx = head_x - neck_x
        dy = head_y - neck_y

        if (dx, dy) != (0, 0):
            self.manual_direction = (dx, dy)

    def direction_to_position(self, direction):
        x, y = self.game.snake.head
        dx, dy = direction
        return (x + dx, y + dy)

    def _set_manual_direction(self, direction) -> None:
        """Запрещает разворот на 180 градусов (мгновенное столкновение)."""
        body = self.game.snake.body

        if len(body) > 1:
            head_x, head_y = body[0]
            neck_x, neck_y = body[1]
            current = (head_x - neck_x, head_y - neck_y)

            if direction == (-current[0], -current[1]):
                return

        self.manual_direction = direction

    # ========================================================
    # ОБРАБОТКА КЛАВИШ
    # ========================================================

    def handle_events(self) -> bool:

        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                self.exit_action = "quit"
                return False

            if event.type != pygame.KEYDOWN:
                continue

            # ------------------------------------------------
            # ESC — назад в графическое меню
            # ------------------------------------------------

            if event.key == pygame.K_ESCAPE:
                self.exit_action = "menu"
                return False

            # ------------------------------------------------
            # SPACE — пауза
            # ------------------------------------------------

            if event.key == pygame.K_SPACE:
                if self.game.running and not self.game.won:
                    self.game.paused = not self.game.paused

            # ------------------------------------------------
            # M — смена режима
            # ------------------------------------------------

            elif event.key == pygame.K_m:
                self._toggle_mode()

            # ------------------------------------------------
            # P — показать/скрыть путь ИИ
            # ------------------------------------------------

            elif event.key == pygame.K_p:
                self.show_path = not self.show_path

            # ------------------------------------------------
            # R — перезапуск
            # ------------------------------------------------

            elif event.key == pygame.K_r:
                self.restart()

            # ------------------------------------------------
            # Enter — перезапуск после финала
            # ------------------------------------------------

            elif event.key in (
                pygame.K_RETURN,
                pygame.K_KP_ENTER,
            ) and (
                not self.game.running
                or self.game.won
            ):
                self.restart()

            # ------------------------------------------------
            # MANUAL
            # ------------------------------------------------

            elif self.game.mode == Game.MANUAL:

                directions = {
                    pygame.K_UP: (0, -1),
                    pygame.K_w: (0, -1),
                    pygame.K_RIGHT: (1, 0),
                    pygame.K_d: (1, 0),
                    pygame.K_DOWN: (0, 1),
                    pygame.K_s: (0, 1),
                    pygame.K_LEFT: (-1, 0),
                    pygame.K_a: (-1, 0),
                }

                direction = directions.get(event.key)

                if direction is not None:
                    self._set_manual_direction(direction)

        return True

    def _toggle_mode(self) -> None:
        if self.game.mode == Game.SMART:
            self.game.set_mode(Game.MANUAL)
            self._sync_manual_direction()
        else:
            self.game.set_mode(Game.SMART)

    def restart(self) -> None:
        self.game = Game(
            self.game.board.width,
            self.game.board.height,
            self.game.apple_count,
            self.game.mode,
        )

        self.previous_body = list(self.game.snake.body)
        self.animation_start = pygame.time.get_ticks()
        self._reset_trail()

        self._sync_manual_direction()

    # ========================================================
    # ОБНОВЛЕНИЕ ИГРЫ
    # ========================================================

    def update(self) -> None:
        self.previous_body = list(self.game.snake.body)
        self.animation_start = pygame.time.get_ticks()

        if self.game.mode == Game.MANUAL:

            if (
                not self.game.paused
                and self.game.running
                and not self.game.won
            ):

                new_position = self.direction_to_position(
                    self.manual_direction
                )

                self.game.move(new_position)

        else:

            self.game.update()

    # ========================================================
    # ОТРИСОВКА ДОСКИ
    # ========================================================

    def draw_board(self) -> None:
        layout = self.layout
        self._build_board()

        rect = pygame.Rect(
            layout.grid_x,
            layout.grid_y,
            layout.grid_width,
            layout.grid_height,
        )

        # Тень/рамка вокруг доски. На узких полях (5×5) вокруг сетки
        # остаётся свободное место, и рамка выглядит особенно выигрышно.
        side_space = max(0, (layout.window_width - layout.grid_width) // 2)
        frame = min(10, max(0, side_space - 4))

        if frame:
            pygame.draw.rect(
                self.screen,
                (3, 8, 5),
                rect.inflate(frame * 2, frame * 2),
                border_radius=20,
            )
            pygame.draw.rect(
                self.screen,
                (22, 46, 32),
                rect.inflate(frame * 2, frame * 2),
                1,
                border_radius=20,
            )

        self.screen.blit(self._board_cache, rect.topleft)

        pygame.draw.rect(
            self.screen,
            BOARD_BORDER_COLOR,
            rect,
            2,
            border_radius=14,
        )
        pygame.draw.rect(
            self.screen,
            (24, 35, 46),
            rect.inflate(-4, -4),
            1,
            border_radius=12,
        )

        # Аккуратные угловые акценты.
        accent = (54, 144, 96)
        corner = min(18, max(8, layout.cell_size // 2))
        x0, y0 = rect.topleft
        x1, y1 = rect.bottomright

        for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
            cx = x0 + 7 if sx > 0 else x1 - 7
            cy = y0 + 7 if sy > 0 else y1 - 7
            pygame.draw.line(
                self.screen,
                accent,
                (cx, cy),
                (cx + sx * corner, cy),
                2,
            )
            pygame.draw.line(
                self.screen,
                accent,
                (cx, cy),
                (cx, cy + sy * corner),
                2,
            )

    # ========================================================
    # ЯБЛОКИ
    # ========================================================

    def draw_apples(self) -> None:
        cell = self.cell_size
        size = max(5, int(cell * 0.92))

        for apple in self.game.apples:
            cx, cy = self.cell_center(*apple)
            self.screen.blit(
                self._scaled_asset("apple", size),
                (cx - size // 2, cy - size // 2),
            )

    # ========================================================
    # ПУТЬ ИИ
    # ========================================================

    def draw_path(self) -> None:
        if (
            not self.show_path
            or self.game.mode != Game.SMART
            or not self.game.running
            or self.game.won
        ):
            return

        path = getattr(self.game.ai, "planned_path", None)

        if not path:
            return

        path = list(path)

        # Путь строится до хода, поэтому первая клетка — уже голова.
        if path[0] == self.game.snake.head:
            path = path[1:]

        if not path:
            return

        points = [
            self.cell_center(*cell)
            for cell in [self.game.snake.head] + path
        ]

        # Полупрозрачный слой, чтобы путь не перекрывал змейку.
        overlay = pygame.Surface(
            (self.layout.window_width, self.layout.hud_y),
            pygame.SRCALPHA,
        )

        if len(points) > 1:
            pygame.draw.lines(
                overlay,
                (30, 120, 88, 50),
                False,
                points,
                max(3, self.cell_size // 3),
            )

        for index, point in enumerate(points[1:]):
            alpha = max(40, 150 - index * 3)
            pygame.draw.circle(
                overlay,
                (36, 150, 110, alpha),
                point,
                max(1, self.cell_size // 9),
            )

        self.screen.blit(overlay, (0, 0))

    # ========================================================
    # ЗМЕЙКА
    # ========================================================

    HEAD_ANGLES = {
        (1, 0): 0,
        (0, -1): 90,
        (-1, 0): 180,
        (0, 1): 270,
    }
    TAIL_ANGLES = {
        (-1, 0): 0,
        (0, 1): 90,
        (1, 0): 180,
        (0, -1): 270,
    }
    CORNER_ANGLES = {
        frozenset({(-1, 0), (0, -1)}): 0,
        frozenset({(-1, 0), (0, 1)}): 90,
        frozenset({(1, 0), (0, 1)}): 180,
        frozenset({(1, 0), (0, -1)}): 270,
    }

    def _reset_trail(self) -> None:
        self.trail = [
            self.cell_center(*cell)
            for cell in reversed(self.game.snake.body)
        ]

    @staticmethod
    def _distance(a, b) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])

    def _trail_length(self) -> float:
        return sum(
            self._distance(self.trail[i], self.trail[i - 1])
            for i in range(1, len(self.trail))
        )

    def _sample_trail(self, count: int, step: float):
        """Точки тела вдоль следа головы с шагом step."""
        if not self.trail:
            return []

        trail = self.trail
        index = len(trail) - 1
        distance = 0.0
        samples = []

        for i in range(count):
            target = i * step

            while index > 0:
                segment = self._distance(trail[index], trail[index - 1])
                if distance + segment >= target:
                    break
                distance += segment
                index -= 1

            if index <= 0:
                samples.append(trail[0])
                continue

            segment = self._distance(trail[index], trail[index - 1])
            t = 0.0 if segment <= 0 else (target - distance) / segment
            ax, ay = trail[index]
            bx, by = trail[index - 1]
            samples.append(
                (
                    int(ax + (bx - ax) * t),
                    int(ay + (by - ay) * t),
                )
            )

        return samples

    @staticmethod
    def _smooth_path(points, iterations=2):
        """Скругляет углы ломаной, не меняя клетки тела."""
        points = list(points)

        for _ in range(iterations):
            if len(points) < 3:
                break
            smoothed = [points[0]]

            for i in range(len(points) - 1):
                ax, ay = points[i]
                bx, by = points[i + 1]
                smoothed.append(
                    (ax * 0.75 + bx * 0.25, ay * 0.75 + by * 0.25)
                )
                smoothed.append(
                    (ax * 0.25 + bx * 0.75, ay * 0.25 + by * 0.75)
                )

            smoothed.append(points[-1])
            points = smoothed

        return points

    def draw_snake(self) -> None:
        body = list(self.game.snake.body)
        if not body:
            return

        cell = self.cell_size
        previous = self.previous_body or body
        alpha = (pygame.time.get_ticks() - self.animation_start)
        alpha = max(0.0, min(1.0, alpha / self.animation_duration))

        centers = []
        for index, cell_pos in enumerate(body):
            old = previous[min(index, len(previous) - 1)]
            old_x, old_y = self.cell_center(*old)
            new_x, new_y = self.cell_center(*cell_pos)
            centers.append(
                (
                    int(old_x + (new_x - old_x) * alpha),
                    int(old_y + (new_y - old_y) * alpha),
                )
            )

        points = [
            (int(x), int(y))
            for x, y in self._smooth_path(centers, 2)
        ]
        length = len(points)

        body_color = self.snake_body_color
        head_color = self.snake_head_color
        tail_color = self._mix(body_color, (0, 0, 0), 0.18)

        for i in range(length - 1, 0, -1):
            t = i / max(1, length - 1)
            color = self._mix(head_color, tail_color, t)
            width = max(2, int((cell + 2) * (0.76 - 0.18 * t)))

            pygame.draw.line(
                self.screen,
                color,
                points[i],
                points[i - 1],
                width,
            )
            pygame.draw.circle(
                self.screen,
                color,
                points[i],
                width // 2,
            )

        if len(points) > 1:
            dx = points[0][0] - points[1][0]
            dy = points[0][1] - points[1][1]
            if dx == 0 and dy == 0:
                dx, dy = 1, 0
            angle = int(
                round(math.degrees(math.atan2(-dy, dx)) / 3.0) * 3
            )
        else:
            angle = 0

        head_size = int(cell * 1.08) + 2
        head_name = f"snake_head_{self.asset_theme}"
        head = self._sprite(head_name, head_size, angle)
        self.screen.blit(
            head,
            (
                points[0][0] - head_size // 2,
                points[0][1] - head_size // 2,
            ),
        )

    # ========================================================
    # ИНФОРМАЦИОННАЯ ПАНЕЛЬ
    # ========================================================

    def draw_hud(self) -> None:
        layout = self.layout
        width = layout.window_width
        hud_y = layout.hud_y

        self._build_hud()
        self.screen.blit(self._hud_cache, (0, hud_y))

        left = 18
        right_panel = 128
        separator_x = width - right_panel - 10

        # ----------------------------------------------------
        # Режим и параметры поля
        # ----------------------------------------------------

        mode_text = self.mode_label or {
            Game.SMART: "SMART",
            Game.MANUAL: "MANUAL",
            Game.COMPETITION: "СОРЕВНОВАНИЕ",
        }.get(self.game.mode, self.game.mode)

        chip_font = self._font(11, bold=True)
        chip_text = chip_font.render(
            mode_text,
            True,
            (128, 236, 172),
        )
        chip_rect = pygame.Rect(
            left,
            hud_y + 8,
            chip_text.get_width() + 18,
            22,
        )

        pygame.draw.rect(
            self.screen,
            (22, 48, 37),
            chip_rect,
            border_radius=7,
        )
        pygame.draw.rect(
            self.screen,
            (48, 112, 82),
            chip_rect,
            1,
            border_radius=7,
        )
        self.screen.blit(
            chip_text,
            chip_text.get_rect(center=chip_rect.center),
        )

        meta = (
            f"ПОЛЕ {self.game.board.width}×"
            f"{self.game.board.height}  ·  "
            f"КЛЕТКА {self.cell_size} PX"
        )
        meta_surface = self._fit_surface(
            meta,
            11,
            max(80, separator_x - chip_rect.right - 22),
            MUTED_TEXT_COLOR,
        )
        self.screen.blit(
            meta_surface,
            (
                chip_rect.right + 10,
                chip_rect.centery - meta_surface.get_height() // 2,
            ),
        )

        apples_text = f"ЯБЛОК {len(self.game.apples)}"
        apples_surface = self._font(10, bold=True).render(
            apples_text,
            True,
            (196, 208, 224),
        )

        # ----------------------------------------------------
        # Статус
        # ----------------------------------------------------

        if self.extra_status is not None:
            status, status_color = self.extra_status()

        elif self.game.paused:
            status = "ПАУЗА"
            status_color = ACCENT_COLOR

        elif self.game.won:
            status = "ПОЛЕ ЗАПОЛНЕНО"
            status_color = SUCCESS_COLOR

        elif not self.game.running:
            status = "СТОЛКНОВЕНИЕ"
            status_color = DANGER_COLOR

        else:
            status = (
                f"Длина {self.game.snake.length}  ·  "
                f"ходы {self.game.moves}"
            )
            status_color = TEXT_COLOR

        status_surface = self._fit_surface(
            status,
            19,
            max(120, separator_x - left - 10),
            status_color,
            bold=True,
        )
        self.screen.blit(
            status_surface,
            (left, hud_y + 36),
        )

        controls = self.extra_controls or (
            "M — режим   ·   SPACE — пауза   ·   "
            "P — путь   ·   R — заново   ·   ESC — меню"
        )
        controls_surface = self._fit_surface(
            controls,
            11,
            max(120, separator_x - left - 10),
            MUTED_TEXT_COLOR,
        )
        self.screen.blit(
            controls_surface,
            (left, hud_y + 70),
        )

        # ----------------------------------------------------
        # Правая карточка со счётом
        # ----------------------------------------------------

        score_panel = pygame.Rect(
            separator_x + 4,
            hud_y + 8,
            width - separator_x - 16,
            HUD_HEIGHT - 16,
        )

        pygame.draw.rect(
            self.screen,
            (14, 34, 24),
            score_panel,
            border_radius=10,
        )
        pygame.draw.rect(
            self.screen,
            (46, 86, 62),
            score_panel,
            1,
            border_radius=10,
        )

        apples_x = score_panel.right - 10 - apples_surface.get_width()
        self.screen.blit(
            apples_surface,
            (apples_x, score_panel.y + 7),
        )

        icon = self._scaled_asset("apple", 14)
        self.screen.blit(
            icon,
            (apples_x - 18, score_panel.y + 3),
        )

        score = max(0, self.game.snake.length - 3)
        score_surface = self._font(30, bold=True).render(
            str(score),
            True,
            ACCENT_COLOR,
        )
        score_center = (
            score_panel.centerx,
            score_panel.y + 39,
        )
        self.screen.blit(
            score_surface,
            score_surface.get_rect(center=score_center),
        )

        label_surface = self._font(9, bold=True).render(
            "СЪЕДЕНО",
            True,
            MUTED_TEXT_COLOR,
        )
        self.screen.blit(
            label_surface,
            label_surface.get_rect(
                center=(
                    score_panel.centerx,
                    score_panel.bottom - 10,
                )
            ),
        )

        # ----------------------------------------------------
        # Полоса заполнения поля
        # ----------------------------------------------------

        track = pygame.Rect(
            0,
            hud_y + HUD_HEIGHT - 5,
            width,
            5,
        )
        pygame.draw.rect(
            self.screen,
            (28, 55, 40),
            track,
        )

        ratio = (
            min(1.0, self.game.snake.length / self.game.board.total_cells)
            if self.game.board.total_cells
            else 0.0
        )
        fill_width = int(width * ratio)

        if fill_width > 0:
            pygame.draw.rect(
                self.screen,
                ACCENT_COLOR,
                (0, track.y, fill_width, track.height),
            )

    # ========================================================
    # ФИНАЛЬНЫЙ ОВЕРЛЕЙ
    # ========================================================

    def draw_end_overlay(self) -> None:
        # В соревновании свой оверлей на весь экран.
        if self.extra_status is not None:
            return

        if not (
            self.game.paused
            or self.game.won
            or not self.game.running
        ):
            return

        width = self.layout.window_width
        board_height = self.layout.hud_y

        veil = pygame.Surface((width, board_height), pygame.SRCALPHA)
        veil.fill((4, 7, 11, 168))
        self.screen.blit(veil, (0, 0))

        if self.game.won:
            title = "ПОЛЕ ЗАПОЛНЕНО"
            subtitle = (
                f"Длина {self.game.snake.length}  ·  "
                f"ходы {self.game.moves}"
            )
            hint = "R — заново   ·   ESC — меню"
            color = SUCCESS_COLOR
        elif not self.game.running:
            title = "СТОЛКНОВЕНИЕ"
            subtitle = (
                f"Длина {self.game.snake.length}  ·  "
                f"ходы {self.game.moves}"
            )
            hint = "R — заново   ·   ESC — меню"
            color = DANGER_COLOR
        else:
            title = "ПАУЗА"
            subtitle = "Игра приостановлена"
            hint = "SPACE — продолжить"
            color = ACCENT_COLOR

        panel_width = min(width - 70, 430)
        panel_height = min(176, max(130, board_height - 40))
        panel = pygame.Rect(
            (width - panel_width) // 2,
            (board_height - panel_height) // 2,
            panel_width,
            panel_height,
        )

        pygame.draw.rect(
            self.screen,
            (2, 6, 3),
            panel.move(0, 7),
            border_radius=18,
        )
        pygame.draw.rect(
            self.screen,
            (15, 35, 24),
            panel,
            border_radius=18,
        )
        pygame.draw.rect(
            self.screen,
            (46, 86, 62),
            panel,
            1,
            border_radius=18,
        )
        pygame.draw.line(
            self.screen,
            color,
            (panel.x + 26, panel.y + 1),
            (panel.right - 26, panel.y + 1),
            2,
        )

        title_surface = self._fit_surface(
            title,
            28,
            panel_width - 40,
            color,
            bold=True,
        )
        self.screen.blit(
            title_surface,
            title_surface.get_rect(
                center=(panel.centerx, panel.y + 50)
            ),
        )

        subtitle_surface = self._fit_surface(
            subtitle,
            15,
            panel_width - 50,
            TEXT_COLOR,
        )
        self.screen.blit(
            subtitle_surface,
            subtitle_surface.get_rect(
                center=(panel.centerx, panel.y + 88)
            ),
        )

        hint_surface = self._fit_surface(
            hint,
            11,
            panel_width - 40,
            MUTED_TEXT_COLOR,
        )
        self.screen.blit(
            hint_surface,
            hint_surface.get_rect(
                center=(panel.centerx, panel.bottom - 26)
            ),
        )

    # ========================================================
    # ОБЩАЯ ОТРИСОВКА
    # ========================================================

    def draw(self) -> None:
        self._build_background()
        self.screen.blit(self._background_cache, (0, 0))

        self.draw_board()
        self.draw_path()
        self.draw_apples()
        self.draw_snake()
        self.draw_hud()
        self.draw_end_overlay()

    # ========================================================
    # ЗАПУСК
    # ========================================================

    def run(self):
        """Игровой цикл. Возвращает "menu" или "quit"."""
        self.exit_action = None
        running = True

        next_tick = pygame.time.get_ticks()
        frame_ms = 1000.0 / FPS

        while running:

            running = self.handle_events()

            if not running:
                break

            now = pygame.time.get_ticks()

            if now >= next_tick:
                self.update()
                next_tick += frame_ms

                if next_tick < now:
                    next_tick = now + frame_ms

            self.draw()
            pygame.display.flip()
            self.clock.tick(RENDER_FPS)

        return self.exit_action or "quit"

