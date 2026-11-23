# layout.py
"""
Геометрия окна игры.

Размер клетки больше не фиксирован: он подбирается под рабочую область
экрана (без панели задач), поэтому окно с большим полем целиком
помещается на экране.
"""

import sys

from dataclasses import dataclass

import pygame

from config import (
    CELL_SIZE_MAX,
    CELL_SIZE_MIN,
    COMPETITION_GAP,
    COMPETITION_MARGIN,
    HUD_HEIGHT,
    HUD_MIN_WIDTH,
    SCREEN_MARGIN_H,
    SCREEN_MARGIN_V,
)


@dataclass(frozen=True)
class GameLayout:
    cell_size: int
    window_width: int
    window_height: int
    grid_x: int
    grid_y: int
    grid_width: int
    grid_height: int
    hud_y: int

    def cell_center(self, x: int, y: int) -> tuple[int, int]:
        """Центр клетки (x, y) в координатах окна."""
        return (
            self.grid_x + x * self.cell_size + self.cell_size // 2,
            self.grid_y + y * self.cell_size + self.cell_size // 2,
        )

    def cell_rect(self, x: int, y: int) -> pygame.Rect:
        """Прямоугольник клетки (x, y) в координатах окна."""
        return pygame.Rect(
            self.grid_x + x * self.cell_size,
            self.grid_y + y * self.cell_size,
            self.cell_size,
            self.cell_size,
        )


def desktop_size() -> tuple[int, int]:
    """Полный размер экрана в пикселях."""
    try:
        sizes = pygame.display.get_desktop_sizes()
    except (pygame.error, AttributeError):
        sizes = []

    if sizes:
        width, height = sizes[0]
        if width > 0 and height > 0:
            return int(width), int(height)

    try:
        info = pygame.display.Info()
        if info.current_w > 0 and info.current_h > 0:
            return int(info.current_w), int(info.current_h)
    except pygame.error:
        pass

    return 1024, 768


def work_area() -> tuple[int, int]:
    """
    Рабочая область основного монитора: экран без панели задач.
    Именно она, а не полный экран, определяет максимальный размер окна.
    """
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            rect = wintypes.RECT()

            # SPI_GETWORKAREA = 0x0030
            if ctypes.windll.user32.SystemParametersInfoW(
                0x0030, 0, ctypes.byref(rect), 0
            ):
                width = rect.right - rect.left
                height = rect.bottom - rect.top
                if width > 0 and height > 0:
                    return int(width), int(height)
        except Exception:
            pass

    width, height = desktop_size()
    return width, max(1, height - 48)


def compute_game_layout(
    board_width: int,
    board_height: int,
    area: tuple[int, int] | None = None,
) -> GameLayout:
    """
    Подбирает размер клетки так, чтобы окно игры целиком помещалось
    в рабочей области экрана.

    Окно не уже HUD_MIN_WIDTH (чтобы читались строки информации),
    поэтому сетка маленького поля центрируется по горизонтали.
    """
    available_width, available_height = area or work_area()

    available_width = max(320, available_width - SCREEN_MARGIN_H)
    available_height = max(240, available_height - SCREEN_MARGIN_V)

    cell_by_width = available_width // board_width
    cell_by_height = (available_height - HUD_HEIGHT) // max(1, board_height)

    cell_size = max(
        CELL_SIZE_MIN,
        min(CELL_SIZE_MAX, cell_by_width, cell_by_height),
    )

    grid_width = board_width * cell_size
    grid_height = board_height * cell_size

    min_window_width = min(HUD_MIN_WIDTH, available_width)
    window_width = max(grid_width, min_window_width)
    window_height = grid_height + HUD_HEIGHT

    return GameLayout(
        cell_size=cell_size,
        window_width=window_width,
        window_height=window_height,
        grid_x=(window_width - grid_width) // 2,
        grid_y=0,
        grid_width=grid_width,
        grid_height=grid_height,
        hud_y=grid_height,
    )


@dataclass(frozen=True)
class CompetitionLayout:
    """Геометрия режима соревнования: одно окно ИИ и одно окно игрока."""

    game: GameLayout
    left: tuple[int, int]
    right: tuple[int, int]
    outer_width: int
    outer_height: int

    @property
    def total_width(self) -> int:
        return self.outer_width * 2 + COMPETITION_GAP

    @property
    def right_edge(self) -> int:
        return (
            self.right[0]
            + self.game.window_width
            + WINDOW_BORDER_X
        )

    @property
    def bottom_edge(self) -> int:
        return (
            self.left[1]
            + self.game.window_height
            + WINDOW_BOTTOM_BORDER
        )


# Оформление окна Windows: рамка слева/справа и заголовок сверху.
# Нужны, чтобы позиция клиентской области не заводила окно за экран.
WINDOW_BORDER_X = 8
WINDOW_TITLE_BAR = 31
WINDOW_BOTTOM_BORDER = 8


def compute_competition_layouts(
    board_width: int,
    board_height: int,
    area: tuple[int, int] | None = None,
) -> CompetitionLayout:
    """
    Два окна рядом. Каждое окно получает половину рабочей области,
    поэтому даже поле 30×30 целиком помещается на экране.

    left/right — позиции клиентской области (их принимает SDL2 Window).
    """
    available_width, available_height = area or work_area()

    half_width = max(
        240,
        (available_width - COMPETITION_GAP - 2 * COMPETITION_MARGIN)
        // 2,
    )

    game_layout = compute_game_layout(
        board_width,
        board_height,
        (half_width, available_height),
    )

    width = game_layout.window_width
    height = game_layout.window_height

    outer_width = width + 2 * WINDOW_BORDER_X
    outer_height = (
        height + WINDOW_TITLE_BAR + WINDOW_BOTTOM_BORDER
    )

    total_outer_width = outer_width * 2 + COMPETITION_GAP

    outer_left = max(
        COMPETITION_MARGIN,
        (available_width - total_outer_width) // 2,
    )
    outer_top = max(
        8,
        (available_height - outer_height) // 2,
    )

    left_x = outer_left + WINDOW_BORDER_X
    right_x = outer_left + outer_width + COMPETITION_GAP + WINDOW_BORDER_X
    client_top = outer_top + WINDOW_TITLE_BAR

    return CompetitionLayout(
        game=game_layout,
        left=(left_x, client_top),
        right=(right_x, client_top),
        outer_width=outer_width,
        outer_height=outer_height,
    )


def center_window() -> None:
    """
    Ставит уже созданное окно по центру рабочей области монитора.
    Нужно, чтобы заголовок окна и нижняя кромка не уходили под панель задач.
    На не-Windows ничего не делает.
    """
    if sys.platform != "win32":
        return

    try:
        import ctypes
        from ctypes import wintypes

        hwnd = pygame.display.get_wm_info().get("window")
        if not hwnd:
            return

        user32 = ctypes.windll.user32

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD),
            ]

        user32.MonitorFromWindow.restype = ctypes.c_void_p
        user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        user32.GetMonitorInfoW.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(MONITORINFO),
        ]
        user32.GetMonitorInfoW.restype = wintypes.BOOL
        user32.GetWindowRect.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(wintypes.RECT),
        ]
        user32.GetWindowRect.restype = wintypes.BOOL
        user32.SetWindowPos.argtypes = [
            wintypes.HWND,
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        user32.SetWindowPos.restype = wintypes.BOOL

        # MONITOR_DEFAULTTONEAREST = 2
        monitor = user32.MonitorFromWindow(wintypes.HWND(hwnd), 2)
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)

        if not monitor or not user32.GetMonitorInfoW(
            monitor, ctypes.byref(info)
        ):
            return

        window_rect = wintypes.RECT()
        if not user32.GetWindowRect(
            wintypes.HWND(hwnd), ctypes.byref(window_rect)
        ):
            return

        window_width = window_rect.right - window_rect.left
        window_height = window_rect.bottom - window_rect.top
        work = info.rcWork

        x = work.left + max(
            0, (work.right - work.left - window_width) // 2
        )
        y = work.top + max(
            0, (work.bottom - work.top - window_height) // 2
        )

        SWP_NOSIZE = 0x0001
        SWP_NOZORDER = 0x0004
        SWP_NOACTIVATE = 0x0010

        user32.SetWindowPos(
            wintypes.HWND(hwnd),
            wintypes.HWND(0),
            x,
            y,
            0,
            0,
            SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE,
        )
    except Exception:
        # Центрирование — необязательный штрих: игра работает и без него.
        pass
