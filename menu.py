# menu.py
"""
Графическое стартовое меню: размер поля, число яблок и режим игры.

Меню управляется и мышью, и клавиатурой:
    ↑ / ↓       — выбор строки
    ← / →       — изменение значения
    1 / 2 / 3   — SMART / MANUAL / СОРЕВНОВАНИЕ
    Enter       — начать игру
    Esc         — выход

В режиме соревнования появляется строка «Цель соревнования»:
число яблок до победы или режим «До конца» (до заполнения поля).
"""

import pygame

from config import (
    ACCENT_COLOR,
    ACCENT_DARK_COLOR,
    ACCENT_HOVER_COLOR,
    BUTTON_COLOR,
    BUTTON_DISABLED_COLOR,
    BUTTON_HOVER_COLOR,
    COMPETITION_TARGET,
    COMPETITION_TARGET_MAX,
    COMPETITION_TARGET_MIN,
    DANGER_COLOR,
    MAX_APPLES,
    MAX_BOARD_SIZE,
    MENU_BACKGROUND_BOTTOM,
    MENU_BACKGROUND_TOP,
    MENU_FPS,
    MENU_HEIGHT,
    MENU_WIDTH,
    MIN_BOARD_SIZE,
    MUTED_TEXT_COLOR,
    PANEL_BORDER_COLOR,
    PANEL_COLOR,
    SUCCESS_COLOR,
    TEXT_COLOR,
    TEXT_ON_ACCENT,
)

from game import Game
from layout import (
    center_window,
    compute_competition_layouts,
    compute_game_layout,
    work_area,
)


FOCUS_WIDTH = 0
FOCUS_HEIGHT = 1
FOCUS_APPLES = 2
FOCUS_MODE = 3
FOCUS_TARGET = 4
FOCUS_START = 5

FOCUS_COUNT = 6

GAME_MODES = (
    Game.SMART,
    Game.MANUAL,
    Game.COMPETITION,
)

MODE_LABELS = {
    Game.SMART: "SMART",
    Game.MANUAL: "MANUAL",
    Game.COMPETITION: "СОРЕВНОВАНИЕ",
}


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


class Menu:

    def __init__(self):

        self.width = 20
        self.height = 20
        self.apples = 5
        self.mode = Game.SMART

        self.competition_target = COMPETITION_TARGET
        self.competition_full_board = False

        self.focus = FOCUS_WIDTH

        self.result = None
        self.running = False

        self.screen = None
        self.clock = pygame.time.Clock()

        self._fonts = {}
        self._background = None
        self._background_size = (0, 0)

        self._desktop = (1024, 768)
        self._rects = {}
        self._mouse = (0, 0)

    # ========================================================
    # НАСТРОЙКИ
    # ========================================================

    @property
    def max_apples(self) -> int:
        return max(
            1,
            min(
                MAX_APPLES,
                self.width * self.height - 3,
            ),
        )

    @property
    def max_target(self) -> int:
        return max(
            1,
            min(
                COMPETITION_TARGET_MAX,
                self.width * self.height - 3,
            ),
        )

    def set_defaults(
        self,
        width: int,
        height: int,
        apple_count: int,
        mode: str,
        competition_target: int | None = None,
        competition_full_board: bool | None = None,
    ) -> None:
        """Запоминает параметры последней партии."""
        self.width = _clamp(width, MIN_BOARD_SIZE, MAX_BOARD_SIZE)
        self.height = _clamp(height, MIN_BOARD_SIZE, MAX_BOARD_SIZE)
        self.apples = _clamp(apple_count, 1, self.max_apples)
        self.mode = mode

        if competition_target is not None:
            self.competition_target = _clamp(
                competition_target,
                COMPETITION_TARGET_MIN,
                self.max_target,
            )

        if competition_full_board is not None:
            self.competition_full_board = bool(competition_full_board)

        self.focus = FOCUS_WIDTH

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
        """Рендер текста с уменьшением шрифта, пока он не влезет по ширине."""
        current = int(size)

        while current > 9:
            surface = self._font(current, bold).render(text, True, color)
            if surface.get_width() <= max_width:
                return surface
            current -= 1

        return self._font(9, bold).render(text, True, color)

    # ========================================================
    # ЗАПУСК МЕНЮ
    # ========================================================

    def run(self):
        """Показывает меню. Возвращает параметры игры или None."""
        self._create_window()

        self.result = None
        self.running = True

        pygame.key.set_repeat(300, 60)

        try:
            while self.running:
                self._handle_events()

                if not self.running:
                    break

                self._draw()
                pygame.display.flip()
                self.clock.tick(MENU_FPS)
        finally:
            pygame.key.set_repeat(0)

        return self.result

    def _create_window(self) -> None:
        self._desktop = work_area()

        available_width, available_height = self._desktop

        menu_width = min(
            MENU_WIDTH,
            max(480, available_width - 48),
        )
        menu_height = min(
            MENU_HEIGHT,
            max(520, available_height - 48),
        )

        self.screen = pygame.display.set_mode(
            (menu_width, menu_height)
        )

        pygame.display.set_caption(
            "Snake AI — настройка игры"
        )

        center_window()

        self._background = None
        self._background_size = (0, 0)

    # ========================================================
    # СОБЫТИЯ
    # ========================================================

    def _handle_events(self) -> None:
        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                self.running = False
                return

            if event.type == pygame.KEYDOWN:
                self._handle_key(event.key, event.mod)

            elif (
                event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1
            ):
                self._handle_click(event.pos)

            if not self.running:
                return

    def _focus_order(self) -> list[int]:
        order = [
            FOCUS_WIDTH,
            FOCUS_HEIGHT,
            FOCUS_APPLES,
            FOCUS_MODE,
        ]

        if self.mode == Game.COMPETITION:
            order.append(FOCUS_TARGET)

        order.append(FOCUS_START)
        return order

    def _move_focus(self, step: int) -> None:
        order = self._focus_order()

        if self.focus not in order:
            self.focus = order[0]
            return

        index = order.index(self.focus)
        self.focus = order[(index + step) % len(order)]

    def _handle_key(self, key: int, mod: int) -> None:
        if key == pygame.K_ESCAPE:
            self.running = False
            return

        if key == pygame.K_TAB:
            self._move_focus(
                -1 if mod & pygame.KMOD_SHIFT else 1
            )

        elif key in (pygame.K_UP, pygame.K_w):
            self._move_focus(-1)

        elif key in (pygame.K_DOWN, pygame.K_s):
            self._move_focus(1)

        elif key in (pygame.K_LEFT, pygame.K_a):
            self._adjust_focused(-1)

        elif key in (pygame.K_RIGHT, pygame.K_d):
            self._adjust_focused(1)

        elif key in (
            pygame.K_PLUS,
            pygame.K_EQUALS,
            pygame.K_KP_PLUS,
        ):
            self._adjust_focused(1)

        elif key in (
            pygame.K_MINUS,
            pygame.K_KP_MINUS,
        ):
            self._adjust_focused(-1)

        elif key == pygame.K_1:
            self.mode = Game.SMART
            self.focus = FOCUS_MODE

        elif key == pygame.K_2:
            self.mode = Game.MANUAL
            self.focus = FOCUS_MODE

        elif key == pygame.K_3:
            self.mode = Game.COMPETITION
            self.focus = FOCUS_MODE

        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._start()

        elif key == pygame.K_SPACE:
            if self.focus == FOCUS_MODE:
                self._toggle_mode()
            elif self.focus == FOCUS_TARGET:
                self._toggle_full_board()
            else:
                self._start()

    def _handle_click(self, position) -> None:
        rects = self._rects

        if rects.get("start") and rects["start"].collidepoint(position):
            self._start()
            return

        steppers = (
            ("width_minus", FOCUS_WIDTH, -1),
            ("width_plus", FOCUS_WIDTH, 1),
            ("height_minus", FOCUS_HEIGHT, -1),
            ("height_plus", FOCUS_HEIGHT, 1),
            ("apples_minus", FOCUS_APPLES, -1),
            ("apples_plus", FOCUS_APPLES, 1),
            ("target_minus", FOCUS_TARGET, -1),
            ("target_plus", FOCUS_TARGET, 1),
        )

        for name, focus, delta in steppers:
            rect = rects.get(name)
            if rect and rect.collidepoint(position):
                self._adjust(focus, delta)
                return

        full_rect = rects.get("full_board")
        if full_rect and full_rect.collidepoint(position):
            self._toggle_full_board()
            return

        for rect, preset_width, preset_height in rects.get(
            "presets", []
        ):
            if rect.collidepoint(position):
                self.width = preset_width
                self.height = preset_height
                self.apples = min(self.apples, self.max_apples)
                self.focus = FOCUS_WIDTH
                return

        for mode, rect in rects.get("modes", []):
            if rect.collidepoint(position):
                self.mode = mode
                self.focus = FOCUS_MODE
                return

        for focus in (
            FOCUS_WIDTH,
            FOCUS_HEIGHT,
            FOCUS_APPLES,
            FOCUS_TARGET,
        ):
            rect = rects.get(f"row_{focus}")
            if rect and rect.collidepoint(position):
                self.focus = focus
                return

        if rects.get("mode_row") and rects["mode_row"].collidepoint(
            position
        ):
            self.focus = FOCUS_MODE

    def _adjust_focused(self, delta: int) -> None:
        if self.focus in (
            FOCUS_WIDTH,
            FOCUS_HEIGHT,
            FOCUS_APPLES,
            FOCUS_MODE,
            FOCUS_TARGET,
        ):
            self._adjust(self.focus, delta)

    def _adjust(self, focus: int, delta: int) -> None:
        if focus == FOCUS_WIDTH:
            self.width = _clamp(
                self.width + delta,
                MIN_BOARD_SIZE,
                MAX_BOARD_SIZE,
            )

        elif focus == FOCUS_HEIGHT:
            self.height = _clamp(
                self.height + delta,
                MIN_BOARD_SIZE,
                MAX_BOARD_SIZE,
            )

        elif focus == FOCUS_APPLES:
            self.apples = _clamp(
                self.apples + delta,
                1,
                self.max_apples,
            )

        elif focus == FOCUS_MODE:
            self._cycle_mode(delta)
            return

        elif focus == FOCUS_TARGET:
            if not self.competition_full_board:
                self.competition_target = _clamp(
                    self.competition_target + delta,
                    COMPETITION_TARGET_MIN,
                    self.max_target,
                )
            self.focus = focus
            return

        self.apples = min(self.apples, self.max_apples)
        self.competition_target = min(
            self.competition_target,
            self.max_target,
        )
        self.focus = focus

    def _toggle_full_board(self) -> None:
        if self.mode != Game.COMPETITION:
            return

        self.competition_full_board = (
            not self.competition_full_board
        )
        self.focus = FOCUS_TARGET

    def _cycle_mode(self, delta: int) -> None:
        index = GAME_MODES.index(self.mode)
        self.mode = GAME_MODES[(index + delta) % len(GAME_MODES)]
        self.focus = FOCUS_MODE

    def _toggle_mode(self) -> None:
        self._cycle_mode(1)

    def _start(self) -> None:
        self.result = {
            "width": self.width,
            "height": self.height,
            "apple_count": self.apples,
            "mode": self.mode,
            "competition_target": self.competition_target,
            "competition_full_board": (
                self.competition_full_board
                if self.mode == Game.COMPETITION
                else False
            ),
        }
        self.running = False

    # ========================================================
    # ОТРИСОВКА
    # ========================================================

    def _make_background(
        self,
        width: int,
        height: int,
    ) -> pygame.Surface:
        background = pygame.Surface((width, height)).convert()

        for y in range(height):
            t = y / max(1, height - 1)
            color = tuple(
                int(
                    top + (bottom - top) * t
                )
                for top, bottom in zip(
                    MENU_BACKGROUND_TOP,
                    MENU_BACKGROUND_BOTTOM,
                )
            )
            pygame.draw.line(
                background,
                color,
                (0, y),
                (width, y),
            )

        glow = pygame.Surface(
            (width, height),
            pygame.SRCALPHA,
        )

        pygame.draw.circle(
            glow,
            (*ACCENT_COLOR, 16),
            (width - 40, 10),
            230,
        )
        pygame.draw.circle(
            glow,
            (70, 120, 220, 12),
            (10, height),
            260,
        )

        for y in range(18, height, 40):
            for x in range(18, width, 40):
                pygame.draw.circle(
                    glow,
                    (255, 255, 255, 8),
                    (x, y),
                    1,
                )

        background.blit(glow, (0, 0))

        return background

    def _draw(self) -> None:
        self._mouse = pygame.mouse.get_pos()

        screen = self.screen
        width, height = screen.get_size()

        if (
            self._background is None
            or self._background_size != (width, height)
        ):
            self._background = self._make_background(width, height)
            self._background_size = (width, height)

        screen.blit(self._background, (0, 0))

        self._rects = {
            "presets": [],
            "modes": [],
        }

        panel_width = min(width - 48, 760)
        panel_x = (width - panel_width) // 2
        panel_y = 112

        inner_x = panel_x + 22
        inner_right = panel_x + panel_width - 22
        inner_width = inner_right - inner_x

        row_1 = panel_y + 18
        row_2 = row_1 + 56
        row_3 = row_2 + 56
        presets_y = row_3 + 60

        competition_y = presets_y + 50

        if self.mode == Game.COMPETITION:
            mode_y = competition_y + 48
        else:
            mode_y = presets_y + 54

        caption_y = mode_y + 58
        panel_bottom = caption_y + 22
        panel_height = panel_bottom - panel_y

        preview_y = max(panel_bottom + 14, height - 142)
        start_y = height - 108
        footer_y = height - 32

        self._draw_header(panel_x, panel_width)

        # ----------------------------------------------------
        # Панель с настройками
        # ----------------------------------------------------

        panel_rect = pygame.Rect(
            panel_x,
            panel_y,
            panel_width,
            panel_height,
        )
        shadow_rect = panel_rect.move(0, 4)

        pygame.draw.rect(
            screen,
            (12, 14, 19),
            shadow_rect,
            border_radius=16,
        )
        pygame.draw.rect(
            screen,
            PANEL_COLOR,
            panel_rect,
            border_radius=16,
        )
        pygame.draw.rect(
            screen,
            PANEL_BORDER_COLOR,
            panel_rect,
            1,
            border_radius=16,
        )

        # ----------------------------------------------------
        # Размер поля и яблоки
        # ----------------------------------------------------

        self._draw_numeric_row(
            "Ширина поля",
            row_1,
            FOCUS_WIDTH,
            self.width,
            MIN_BOARD_SIZE,
            MAX_BOARD_SIZE,
            "width",
            inner_x,
            inner_right,
        )

        self._draw_numeric_row(
            "Высота поля",
            row_2,
            FOCUS_HEIGHT,
            self.height,
            MIN_BOARD_SIZE,
            MAX_BOARD_SIZE,
            "height",
            inner_x,
            inner_right,
        )

        self._draw_numeric_row(
            "Количество яблок",
            row_3,
            FOCUS_APPLES,
            self.apples,
            1,
            self.max_apples,
            "apples",
            inner_x,
            inner_right,
        )

        # ----------------------------------------------------
        # Быстрый выбор размера
        # ----------------------------------------------------

        label = self._font(14).render(
            "Быстрый выбор:",
            True,
            MUTED_TEXT_COLOR,
        )
        screen.blit(
            label,
            (
                inner_x,
                presets_y + 16 - label.get_height() // 2,
            ),
        )

        self._draw_presets(
            inner_right,
            presets_y,
        )

        # ----------------------------------------------------
        # Настройки соревнования
        # ----------------------------------------------------

        if self.mode == Game.COMPETITION:
            self._draw_target_row(
                competition_y,
                inner_x,
                inner_right,
            )

        # ----------------------------------------------------
        # Режим игры
        # ----------------------------------------------------

        self._draw_modes(inner_x, inner_right, mode_y)

        if self.mode == Game.COMPETITION:
            if self.competition_full_board:
                competition_caption = (
                    "СОРЕВНОВАНИЕ — два окна · игра до заполнения поля"
                )
            else:
                competition_caption = (
                    "СОРЕВНОВАНИЕ — два окна · до "
                    f"{self.competition_target} яблок"
                )
        else:
            competition_caption = ""

        captions = {
            Game.SMART: "SMART — автопилот играет сам",
            Game.MANUAL: "MANUAL — стрелки / WASD",
            Game.COMPETITION: competition_caption,
        }

        caption = self._fit_surface(
            captions[self.mode],
            13,
            inner_width,
            MUTED_TEXT_COLOR,
        )
        screen.blit(
            caption,
            (
                panel_x + panel_width // 2
                - caption.get_width() // 2,
                caption_y,
            ),
        )

        # ----------------------------------------------------
        # Предпросмотр размера окна
        # ----------------------------------------------------

        if self.mode == Game.COMPETITION:
            competition_layout = compute_competition_layouts(
                self.width,
                self.height,
                self._desktop,
            )
            game_layout = competition_layout.game

            right_edge = competition_layout.right_edge
            bottom_edge = competition_layout.bottom_edge

            fits = (
                right_edge <= self._desktop[0]
                and bottom_edge <= self._desktop[1]
            )

            preview_text = (
                f"Соревнование: 2 окна "
                f"{game_layout.window_width} × "
                f"{game_layout.window_height} px · "
                f"клетка {game_layout.cell_size} px · "
                + (
                    "до заполнения поля"
                    if self.competition_full_board
                    else f"до {self.competition_target} яблок"
                )
                + " · "
                + (
                    "полностью помещаются на экране"
                    if fits
                    else "окна будут уменьшены"
                )
            )
        else:
            game_layout = compute_game_layout(
                self.width,
                self.height,
                self._desktop,
            )

            fits = (
                game_layout.window_width <= self._desktop[0]
                and game_layout.window_height
                <= self._desktop[1]
            )

            preview_text = (
                f"Окно игры: {game_layout.window_width} × "
                f"{game_layout.window_height} px · "
                f"клетка {game_layout.cell_size} px · "
                + (
                    "полностью помещается на экране"
                    if fits
                    else "окно будет уменьшено"
                )
            )

        preview = self._fit_surface(
            preview_text,
            14,
            inner_width,
            SUCCESS_COLOR if fits else DANGER_COLOR,
        )
        screen.blit(
            preview,
            (
                width // 2 - preview.get_width() // 2,
                preview_y,
            ),
        )

        # ----------------------------------------------------
        # Кнопка старта
        # ----------------------------------------------------

        start_rect = pygame.Rect(
            panel_x,
            start_y,
            panel_width,
            56,
        )

        self._draw_start_button(start_rect)
        self._rects["start"] = start_rect

        # ----------------------------------------------------
        # Подсказка
        # ----------------------------------------------------

        footer_text = (
            "Мышь или клавиатура · "
            "↑↓ — выбор · ←→ — изменение · "
            "1 / 2 / 3 — режим · Enter — старт · Esc — выход"
        )

        footer = self._fit_surface(
            footer_text,
            13,
            width - 40,
            MUTED_TEXT_COLOR,
        )
        screen.blit(
            footer,
            (
                width // 2 - footer.get_width() // 2,
                footer_y,
            ),
        )

    def _draw_header(self, panel_x: int, panel_width: int) -> None:
        screen = self.screen
        width = screen.get_width()

        pygame.draw.rect(
            screen,
            ACCENT_COLOR,
            (panel_x, 30, 6, 50),
            border_radius=3,
        )

        title = self._font(46, bold=True).render(
            "SNAKE AI",
            True,
            ACCENT_COLOR,
        )
        screen.blit(title, (panel_x + 20, 22))

        subtitle = self._font(15).render(
            "Змейка с автопилотом — настройка игры",
            True,
            MUTED_TEXT_COLOR,
        )
        screen.blit(subtitle, (panel_x + 22, 84))

        # Маленькое яблоко в правом верхнем углу.
        if panel_width >= 600:
            apple_x = width - panel_x - 30
            apple_y = 62

            pygame.draw.circle(
                screen,
                (180, 30, 30),
                (apple_x, apple_y + 2),
                15,
            )
            pygame.draw.circle(
                screen,
                (220, 60, 60),
                (apple_x, apple_y),
                15,
            )
            pygame.draw.circle(
                screen,
                (255, 160, 150),
                (apple_x - 5, apple_y - 5),
                4,
            )
            pygame.draw.line(
                screen,
                (101, 67, 33),
                (apple_x, apple_y - 15),
                (apple_x + 2, apple_y - 22),
                3,
            )
            pygame.draw.ellipse(
                screen,
                (34, 197, 94),
                (apple_x + 3, apple_y - 24, 12, 7),
            )

    def _draw_target_row(
        self,
        y: int,
        inner_x: int,
        inner_right: int,
    ) -> None:
        screen = self.screen

        row_rect = pygame.Rect(
            inner_x - 8,
            y - 8,
            inner_right - inner_x + 16,
            56,
        )
        self._rects["row_target"] = row_rect

        if self.focus == FOCUS_TARGET:
            pygame.draw.rect(
                screen,
                ACCENT_DARK_COLOR,
                row_rect,
                1,
                border_radius=10,
            )

        label = self._font(
            17,
            bold=self.focus == FOCUS_TARGET,
        ).render(
            "Цель соревнования",
            True,
            TEXT_COLOR if self.focus == FOCUS_TARGET
            else (205, 210, 222),
        )
        screen.blit(
            label,
            (
                inner_x,
                y + 20 - label.get_height() // 2,
            ),
        )

        disabled = self.competition_full_board

        minus_rect = pygame.Rect(inner_right - 158, y, 38, 40)
        value_rect = pygame.Rect(inner_right - 114, y, 70, 40)
        plus_rect = pygame.Rect(inner_right - 38, y, 38, 40)

        self._rects["target_minus"] = minus_rect
        self._rects["target_plus"] = plus_rect

        self._draw_button(
            minus_rect,
            "−",
            enabled=not disabled
            and self.competition_target > COMPETITION_TARGET_MIN,
            size=22,
        )
        self._draw_button(
            plus_rect,
            "+",
            enabled=not disabled
            and self.competition_target < self.max_target,
            size=22,
        )

        pygame.draw.rect(
            screen,
            (20, 23, 30),
            value_rect,
            border_radius=9,
        )
        pygame.draw.rect(
            screen,
            ACCENT_COLOR if self.focus == FOCUS_TARGET and not disabled
            else PANEL_BORDER_COLOR,
            value_rect,
            1,
            border_radius=9,
        )

        value_text = (
            "ВСЁ"
            if disabled
            else str(self.competition_target)
        )
        value_surface = self._font(20, bold=True).render(
            value_text,
            True,
            MUTED_TEXT_COLOR if disabled else TEXT_COLOR,
        )
        screen.blit(
            value_surface,
            value_surface.get_rect(center=value_rect.center),
        )

        toggle_width = 170
        toggle_rect = pygame.Rect(
            inner_right - 158 - 10 - toggle_width,
            y,
            toggle_width,
            40,
        )
        self._rects["full_board"] = toggle_rect

        self._draw_button(
            toggle_rect,
            "ДО КОНЦА",
            selected=self.competition_full_board,
            size=13,
        )

    def _draw_numeric_row(
        self,
        label: str,
        y: int,
        focus: int,
        value: int,
        minimum: int,
        maximum: int,
        prefix: str,
        inner_x: int,
        inner_right: int,
    ) -> None:
        screen = self.screen

        row_rect = pygame.Rect(
            inner_x - 8,
            y - 8,
            inner_right - inner_x + 16,
            56,
        )

        if self.focus == focus:
            pygame.draw.rect(
                screen,
                ACCENT_DARK_COLOR,
                row_rect,
                1,
                border_radius=10,
            )

        self._rects[f"row_{focus}"] = row_rect

        label_surface = self._font(
            17,
            bold=self.focus == focus,
        ).render(
            label,
            True,
            TEXT_COLOR if self.focus == focus
            else (205, 210, 222),
        )

        screen.blit(
            label_surface,
            (
                inner_x,
                y + 20 - label_surface.get_height() // 2,
            ),
        )

        minus_rect = pygame.Rect(inner_right - 158, y, 38, 40)
        value_rect = pygame.Rect(inner_right - 114, y, 70, 40)
        plus_rect = pygame.Rect(inner_right - 38, y, 38, 40)

        self._rects[f"{prefix}_minus"] = minus_rect
        self._rects[f"{prefix}_plus"] = plus_rect

        self._draw_button(
            minus_rect,
            "−",
            enabled=value > minimum,
            size=22,
        )
        self._draw_button(
            plus_rect,
            "+",
            enabled=value < maximum,
            size=22,
        )

        pygame.draw.rect(
            screen,
            (20, 23, 30),
            value_rect,
            border_radius=9,
        )
        pygame.draw.rect(
            screen,
            ACCENT_COLOR if self.focus == focus
            else PANEL_BORDER_COLOR,
            value_rect,
            1,
            border_radius=9,
        )

        value_surface = self._font(22, bold=True).render(
            str(value),
            True,
            TEXT_COLOR,
        )
        screen.blit(
            value_surface,
            value_surface.get_rect(center=value_rect.center),
        )

    def _draw_presets(
        self,
        inner_right: int,
        y: int,
    ) -> None:
        presets = (
            (10, 10),
            (15, 15),
            (20, 20),
            (30, 30),
        )

        chip_width = 72
        chip_height = 32
        gap = 8

        total_width = (
            len(presets) * chip_width
            + (len(presets) - 1) * gap
        )
        x = inner_right - total_width

        for preset_width, preset_height in presets:
            rect = pygame.Rect(
                x,
                y,
                chip_width,
                chip_height,
            )

            selected = (
                self.width == preset_width
                and self.height == preset_height
            )

            self._draw_button(
                rect,
                f"{preset_width}×{preset_height}",
                selected=selected,
                size=14,
            )

            self._rects["presets"].append(
                (rect, preset_width, preset_height)
            )

            x += chip_width + gap

    def _draw_modes(
        self,
        inner_x: int,
        inner_right: int,
        y: int,
    ) -> None:
        screen = self.screen

        mode_label = self._font(17).render(
            "Режим игры",
            True,
            TEXT_COLOR,
        )
        screen.blit(
            mode_label,
            (
                inner_x,
                y + 25 - mode_label.get_height() // 2,
            ),
        )

        label_width = mode_label.get_width()
        gap = 10

        available = (
            inner_right - inner_x - label_width - 16
        )
        button_width = max(
            90,
            (available - 2 * gap) // 3,
        )
        button_height = 50

        total_width = button_width * 3 + 2 * gap
        x = inner_right - total_width

        row_rect = pygame.Rect(
            x - 8,
            y - 8,
            total_width + 16,
            button_height + 16,
        )
        self._rects["mode_row"] = row_rect

        if self.focus == FOCUS_MODE:
            pygame.draw.rect(
                screen,
                ACCENT_DARK_COLOR,
                row_rect,
                1,
                border_radius=12,
            )

        for mode in GAME_MODES:
            rect = pygame.Rect(
                x,
                y,
                button_width,
                button_height,
            )

            self._draw_button(
                rect,
                MODE_LABELS[mode],
                selected=self.mode == mode,
                size=14 if mode == Game.COMPETITION else 16,
            )

            self._rects["modes"].append((mode, rect))

            x += button_width + gap

    def _draw_start_button(self, rect: pygame.Rect) -> None:
        hovered = rect.collidepoint(self._mouse)

        fill = ACCENT_HOVER_COLOR if hovered else ACCENT_COLOR

        pygame.draw.rect(
            self.screen,
            fill,
            rect,
            border_radius=14,
        )

        if self.focus == FOCUS_START:
            pygame.draw.rect(
                self.screen,
                (190, 255, 205),
                rect.inflate(4, 4),
                2,
                border_radius=16,
            )

        text = (
            "НАЧАТЬ СОРЕВНОВАНИЕ"
            if self.mode == Game.COMPETITION
            else "НАЧАТЬ ИГРУ"
        )
        text += "   ·   Enter"

        surface = self._fit_surface(
            text,
            20,
            rect.width - 24,
            TEXT_ON_ACCENT,
            bold=True,
        )
        self.screen.blit(
            surface,
            surface.get_rect(center=rect.center),
        )

    def _draw_button(
        self,
        rect: pygame.Rect,
        text: str,
        enabled: bool = True,
        selected: bool = False,
        size: int = 16,
    ) -> None:
        hovered = enabled and rect.collidepoint(self._mouse)

        if not enabled:
            fill = BUTTON_DISABLED_COLOR
            border = PANEL_BORDER_COLOR
            text_color = (88, 93, 108)

        elif selected:
            fill = ACCENT_DARK_COLOR
            border = ACCENT_COLOR
            text_color = TEXT_COLOR

        else:
            fill = BUTTON_HOVER_COLOR if hovered else BUTTON_COLOR
            border = PANEL_BORDER_COLOR
            text_color = TEXT_COLOR

        pygame.draw.rect(
            self.screen,
            fill,
            rect,
            border_radius=9,
        )
        pygame.draw.rect(
            self.screen,
            border,
            rect,
            1,
            border_radius=9,
        )

        surface = self._fit_surface(
            text,
            size,
            max(10, rect.width - 12),
            text_color,
            bold=True,
        )
        self.screen.blit(
            surface,
            surface.get_rect(center=rect.center),
        )
