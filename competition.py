# competition.py
"""
Режим соревнования: ИИ и человек играют одновременно в двух окнах.

Правила:
  * у обоих одинаковое стартовое поле и одинаковый набор яблок;
  * победитель — тот, кто первым достиг выбранной цели: съел заданное
    число яблок или заполнил всё поле;
  * если змейка разбилась, она сразу проигрывает;
  * фора по скорости не используется: оба игрока ходят с частотой FPS;
  * ИИ ходит первым и получает победу, если оба достигли цели в одном
    кадре.

Pygame умеет создавать несколько окон через pygame._sdl2: одно окно
рисуется для ИИ, второе — для игрока. После матча окна закрываются,
и приложение возвращается в обычное меню.
"""

import random

import pygame

from pygame._sdl2.video import Renderer, Texture, Window

from config import (
    ACCENT_COLOR,
    AI_BODY_COLOR,
    AI_HEAD_COLOR,
    COMPETITION_COUNTDOWN_MS,
    COMPETITION_TARGET,
    FPS,
    RENDER_FPS,
    MUTED_TEXT_COLOR,
    PLAYER_BODY_COLOR,
    PLAYER_HEAD_COLOR,
    SUCCESS_COLOR,
    TEXT_COLOR,
)

from game import Game
from layout import compute_competition_layouts
from ui import UI


DIRECTIONS = {
    pygame.K_UP: (0, -1),
    pygame.K_w: (0, -1),
    pygame.K_RIGHT: (1, 0),
    pygame.K_d: (1, 0),
    pygame.K_DOWN: (0, 1),
    pygame.K_s: (0, 1),
    pygame.K_LEFT: (-1, 0),
    pygame.K_a: (-1, 0),
}

AI_TITLE = "Snake AI — СОРЕВНОВАНИЕ · ИИ"
HUMAN_TITLE = "Snake AI — СОРЕВНОВАНИЕ · ИГРОК"


class Competition:

    def __init__(
        self,
        width: int,
        height: int,
        apple_count: int,
        target: int = COMPETITION_TARGET,
        full_board: bool = False,
    ):

        self.width = width
        self.height = height
        self.apple_count = apple_count

        self.full_board = bool(full_board)
        max_target = max(1, width * height - 3)

        if self.full_board:
            self.target = max_target
        else:
            self.target = max(
                1,
                min(int(target), max_target),
            )

        self.exit_action = None
        self.paused = False
        self.match_over = False
        self.winner = None

        self.countdown_end = 0

        self.ai_game = None
        self.human_game = None
        self.ai_ui = None
        self.human_ui = None

        self.ai_window = None
        self.human_window = None
        self.ai_renderer = None
        self.human_renderer = None
        self.ai_texture = None
        self.human_texture = None

        self._menu_window = None

        self._fonts = {}
        self._clock = pygame.time.Clock()
        self._last_title = None
        self._seed = 0

    # ========================================================
    # ОКНА
    # ========================================================

    def _create_windows(self) -> None:

        competition_layout = compute_competition_layouts(
            self.width,
            self.height,
        )

        self._layout = competition_layout.game
        self._size = (
            self._layout.window_width,
            self._layout.window_height,
        )

        self._ai_surface = pygame.Surface(self._size)
        self._human_surface = pygame.Surface(self._size)

        # Прячем окно меню, чтобы на экране остались ровно два окна.
        try:
            self._menu_window = Window.from_display_module()
            self._menu_window.hide()
        except Exception:
            self._menu_window = None

        self.ai_window = Window(
            AI_TITLE,
            size=self._size,
            position=competition_layout.left,
        )
        self.human_window = Window(
            HUMAN_TITLE,
            size=self._size,
            position=competition_layout.right,
        )

        self.ai_renderer = Renderer(self.ai_window)
        self.human_renderer = Renderer(self.human_window)

        self.ai_texture = Texture.from_surface(
            self.ai_renderer,
            self._ai_surface,
        )
        self.human_texture = Texture.from_surface(
            self.human_renderer,
            self._human_surface,
        )

        try:
            self.human_window.focus()
        except Exception:
            pass

    def _close_windows(self) -> None:

        for attribute in ("ai_window", "human_window"):
            window = getattr(self, attribute, None)

            if window is not None:
                try:
                    window.destroy()
                except Exception:
                    pass
                setattr(self, attribute, None)

        self.ai_renderer = None
        self.human_renderer = None
        self.ai_texture = None
        self.human_texture = None

        if self._menu_window is not None:
            try:
                if self.exit_action != "quit":
                    self._menu_window.show()
                    self._menu_window.focus()
            except Exception:
                pass

            self._menu_window = None

    # ========================================================
    # МАТЧ
    # ========================================================

    def _new_round(self) -> None:

        self._seed = random.randrange(1, 2 ** 31)

        # Одинаковый seed = одинаковые стартовые яблоки у обоих.
        # У каждой партии свой RNG: действия одного игрока не меняют
        # последовательность появления яблок у другого.
        ai_game = Game(
            self.width,
            self.height,
            self.apple_count,
            Game.SMART,
            rng=random.Random(self._seed),
        )

        human_game = Game(
            self.width,
            self.height,
            self.apple_count,
            Game.MANUAL,
            rng=random.Random(self._seed),
        )

        self.ai_game = ai_game
        self.human_game = human_game

        # Быстрый режим включается по коэффициенту опасности:
        # пока позиция просторная — сбор яблок, дальше кольцо.
        ai_game.ai.fast_enabled = False

        self.ai_ui = UI(
            ai_game,
            screen=self._ai_surface,
            layout=self._layout,
        )
        self.human_ui = UI(
            human_game,
            screen=self._human_surface,
            layout=self._layout,
        )

        self.human_ui.snake_head_color = PLAYER_HEAD_COLOR
        self.human_ui.snake_body_color = PLAYER_BODY_COLOR
        self.ai_ui.snake_head_color = AI_HEAD_COLOR
        self.ai_ui.snake_body_color = AI_BODY_COLOR

        self.ai_ui.asset_theme = "purple"
        self.human_ui.asset_theme = "blue"

        # В каждом окне свой бейдж, чтобы не путать SMART/MANUAL
        # с ролью окна в соревновании.
        self.ai_ui.mode_label = "ИИ"
        self.human_ui.mode_label = "ИГРОК"

        self.ai_ui.extra_status = self._ai_status
        self.human_ui.extra_status = self._human_status

        self.ai_ui.extra_controls = (
            "Окно ИИ · SPACE — пауза · P — путь · "
            "R — реванш · ESC — меню"
        )
        self.human_ui.extra_controls = (
            "ВАС: ←↑↓→ / WASD · SPACE — пауза · "
            "R — реванш · ESC — меню"
        )

        self.paused = False
        self.match_over = False
        self.winner = None
        self._last_title = None

        self.countdown_end = (
            pygame.time.get_ticks() + COMPETITION_COUNTDOWN_MS
        )

        try:
            self.human_window.focus()
        except Exception:
            pass

    def _scores(self) -> tuple[int, int]:
        """Сколько яблок съела каждая змейка."""
        ai_score = max(0, self.ai_game.snake.length - 3)
        human_score = max(0, self.human_game.snake.length - 3)
        return ai_score, human_score

    def _countdown_left(self) -> int:
        return max(
            0,
            self.countdown_end - pygame.time.get_ticks(),
        )

    def _status(self, human_view: bool):
        ai_score, human_score = self._scores()

        if self.match_over:
            if self.winner == "human":
                return (
                    f"ПОБЕДА ИГРОКА · {human_score} : {ai_score}",
                    SUCCESS_COLOR,
                )

            if self.winner == "ai":
                return (
                    f"ПОБЕДА ИИ · {ai_score} : {human_score}",
                    ACCENT_COLOR,
                )

            return (
                f"НИЧЬЯ · {human_score} : {ai_score}",
                TEXT_COLOR,
            )

        if self.paused:
            return (
                f"ПАУЗА · ИИ {ai_score} : {human_score} ВЫ",
                ACCENT_COLOR,
            )

        if human_view:
            return (
                f"ВЫ {human_score} : {ai_score} ИИ · "
                f"{self._target_label()}",
                TEXT_COLOR,
            )

        return (
            f"ИИ {ai_score} : {human_score} ВЫ · "
            f"{self._target_label()}",
            TEXT_COLOR,
        )

    def _target_label(self) -> str:
        if self.full_board:
            return "до заполнения поля"
        return f"до {self.target} яблок"

    def _ai_status(self):
        return self._status(False)

    def _human_status(self):
        return self._status(True)

    def _check_finish(self) -> None:
        ai_score, human_score = self._scores()

        ai_finished = ai_score >= self.target
        human_finished = human_score >= self.target

        if ai_finished or human_finished:
            if ai_finished and human_finished:
                self.winner = "tie"
            elif human_finished:
                self.winner = "human"
            else:
                self.winner = "ai"

            self.match_over = True
            self.paused = False
            return

        if not self.ai_game.running or not self.human_game.running:
            if not self.ai_game.running and not self.human_game.running:
                if human_score > ai_score:
                    self.winner = "human"
                elif ai_score > human_score:
                    self.winner = "ai"
                else:
                    self.winner = "tie"
            elif not self.human_game.running:
                self.winner = "ai"
            else:
                self.winner = "human"

            self.match_over = True
            self.paused = False

    def _update(self) -> None:
        if self.paused or self.match_over:
            return

        if self._countdown_left() > 0:
            return

        self.ai_ui.update()

        # ИИ ходит первым. Если он уже достиг цели, матч сразу
        # заканчивается его победой — человек не получает
        # «ответный» ход в том же кадре.
        ai_score, _ = self._scores()
        if ai_score >= self.target:
            self.winner = "ai"
            self.match_over = True
            self.paused = False
            return

        self.human_ui.update()

        self._check_finish()

    # ========================================================
    # СОБЫТИЯ
    # ========================================================

    def _handle_events(self) -> bool:
        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                self.exit_action = "quit"
                return False

            if event.type == pygame.WINDOWCLOSE:
                window = getattr(event, "window", None)
                window_id = getattr(window, "id", window)

                if window_id is None or window_id in (
                    self.ai_window.id,
                    self.human_window.id,
                ):
                    self.exit_action = "quit"
                    return False

                continue

            if event.type != pygame.KEYDOWN:
                continue

            if event.key == pygame.K_ESCAPE:
                self.exit_action = "menu"
                return False

            if event.key == pygame.K_r:
                self._new_round()
                continue

            if event.key in (
                pygame.K_RETURN,
                pygame.K_KP_ENTER,
            ) and self.match_over:
                self._new_round()
                continue

            if event.key == pygame.K_p:
                self.ai_ui.show_path = not self.ai_ui.show_path
                continue

            if event.key == pygame.K_SPACE:
                if (
                    not self.match_over
                    and self._countdown_left() == 0
                ):
                    self.paused = not self.paused
                continue

            if self.paused or self.match_over:
                continue

            direction = DIRECTIONS.get(event.key)

            if direction is not None:
                self.human_ui._set_manual_direction(direction)

        return True

    # ========================================================
    # ОТРИСОВКА
    # ========================================================

    def _font(self, size: int, bold: bool = False):
        key = (int(size), bool(bold))
        font = self._fonts.get(key)

        if font is None:
            font = pygame.font.SysFont(
                "Arial",
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
    ):
        current = int(size)

        while current > 9:
            surface = self._font(current, bold).render(
                text,
                True,
                color,
            )
            if surface.get_width() <= max_width:
                return surface
            current -= 1

        return self._font(9, bold).render(text, True, color)

    def _overlay_data(self):
        if self.match_over:
            ai_score, human_score = self._scores()
            score = f"ИИ {ai_score} : {human_score} ВЫ"

            if self.winner == "human":
                return (
                    "ПОБЕДА ИГРОКА!",
                    SUCCESS_COLOR,
                    score,
                    "Enter — реванш · Esc — меню",
                )

            if self.winner == "ai":
                return (
                    "ПОБЕДА ИИ",
                    ACCENT_COLOR,
                    score,
                    "Enter — реванш · Esc — меню",
                )

            return (
                "НИЧЬЯ",
                TEXT_COLOR,
                score,
                "Enter — реванш · Esc — меню",
            )

        if self.paused:
            return (
                "ПАУЗА",
                ACCENT_COLOR,
                "SPACE — продолжить",
                "R — реванш · Esc — меню",
            )

        remaining = self._countdown_left()

        if remaining > 0:
            number = max(1, (remaining + 999) // 1000)
            goal = (
                "заполнить всё поле"
                if self.full_board
                else f"съесть {self.target} яблок"
            )
            return (
                str(number),
                ACCENT_COLOR,
                "Приготовьтесь…",
                f"Цель — {goal} · ИИ слева, вы справа",
            )

        return None

    def _draw_overlay(self, surface: pygame.Surface) -> None:
        data = self._overlay_data()

        if data is None:
            return

        title, title_color, info, hint = data

        width, height = surface.get_size()

        veil = pygame.Surface((width, height), pygame.SRCALPHA)
        veil.fill((6, 8, 12, 170))
        surface.blit(veil, (0, 0))

        panel_width = min(width - 60, 470)
        panel_height = 190
        panel = pygame.Rect(
            (width - panel_width) // 2,
            (height - panel_height) // 2,
            panel_width,
            panel_height,
        )

        pygame.draw.rect(
            surface,
            (2, 6, 3),
            panel.move(0, 7),
            border_radius=18,
        )
        pygame.draw.rect(
            surface,
            (14, 30, 22),
            panel,
            border_radius=18,
        )
        pygame.draw.rect(
            surface,
            (46, 86, 62),
            panel,
            1,
            border_radius=18,
        )
        pygame.draw.line(
            surface,
            title_color,
            (panel.x + 30, panel.y + 1),
            (panel.right - 30, panel.y + 1),
            2,
        )

        title_surface = self._fit_surface(
            title,
            42,
            panel_width - 40,
            title_color,
            bold=True,
        )
        surface.blit(
            title_surface,
            title_surface.get_rect(
                center=(panel.centerx, panel.y + 62)
            ),
        )

        info_surface = self._fit_surface(
            info,
            18,
            panel_width - 40,
            TEXT_COLOR,
        )
        surface.blit(
            info_surface,
            info_surface.get_rect(
                center=(panel.centerx, panel.y + 118)
            ),
        )

        hint_surface = self._fit_surface(
            hint,
            14,
            panel_width - 40,
            MUTED_TEXT_COLOR,
        )
        surface.blit(
            hint_surface,
            hint_surface.get_rect(
                center=(panel.centerx, panel.y + 154)
            ),
        )

    def _update_titles(self) -> None:
        ai_score, human_score = self._scores()

        if self.match_over:
            if self.winner == "human":
                suffix = "ПОБЕДА ИГРОКА"
            elif self.winner == "ai":
                suffix = "ПОБЕДА ИИ"
            else:
                suffix = "НИЧЬЯ"
        else:
            suffix = f"ИИ {ai_score} : {human_score} ВЫ"

        if suffix == self._last_title:
            return

        self._last_title = suffix

        try:
            self.ai_window.title = (
                f"{AI_TITLE} · {suffix}"
            )
            self.human_window.title = (
                f"{HUMAN_TITLE} · {suffix}"
            )
        except Exception:
            pass

    def _render(self) -> None:
        self.ai_ui.draw()
        self.human_ui.draw()

        self._draw_overlay(self._ai_surface)
        self._draw_overlay(self._human_surface)

        width, height = self._size
        destination = pygame.Rect(0, 0, width, height)

        for renderer, texture, surface in (
            (self.ai_renderer, self.ai_texture, self._ai_surface),
            (
                self.human_renderer,
                self.human_texture,
                self._human_surface,
            ),
        ):
            texture.update(surface)
            renderer.clear()
            renderer.blit(texture, destination)
            renderer.present()

        self._update_titles()

    # ========================================================
    # ЗАПУСК
    # ========================================================

    def run(self):
        """Проводит матч. Возвращает "menu" или "quit"."""
        self.exit_action = None

        running = True

        try:
            self._create_windows()
            self._new_round()

            pygame.key.set_repeat(0)

            self._render()

            next_tick = pygame.time.get_ticks()
            frame_ms = 1000.0 / FPS

            while running:
                running = self._handle_events()

                if not running:
                    break

                now = pygame.time.get_ticks()

                if now >= next_tick:
                    self._update()
                    next_tick += frame_ms

                    if next_tick < now:
                        next_tick = now + frame_ms

                self._render()
                self._clock.tick(RENDER_FPS)

        finally:
            self._close_windows()

        return self.exit_action or "quit"
