"""Generate smooth PNG assets for the Snake game.

Run from the project root:
    python tools/generate_assets.py
"""

from pathlib import Path

import math

import pygame

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
ASSETS.mkdir(exist_ok=True)

S = 512
OUTLINE = int(S * 0.045)
BODY = int(S * 0.64)
MID = S // 2
RADIUS = BODY // 2


def canvas():
    return pygame.Surface((S, S), pygame.SRCALPHA)


def save(surface, name):
    surface = pygame.transform.smoothscale(surface, (256, 256))
    pygame.image.save(surface, str(ASSETS / name))


def shade(mask, top, bottom):
    surface = pygame.Surface((S, S), pygame.SRCALPHA)

    for y in range(S):
        t = y / (S - 1)
        color = tuple(
            int(a + (b - a) * t)
            for a, b in zip(top, bottom)
        )
        pygame.draw.line(surface, color, (0, y), (S, y))

    surface.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return surface


def add_scales(surface, mask, color, offset=0):
    scales = pygame.Surface((S, S), pygame.SRCALPHA)
    rows = 3

    for row in range(rows):
        y = MID - BODY // 2 + int(BODY * (row + 0.5) / rows)
        for x in range(-30 + offset, S + 30, 62):
            pygame.draw.arc(
                scales,
                color,
                (x, y - 18, 46, 36),
                math.radians(205),
                math.radians(335),
                3,
            )

    scales.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surface.blit(scales, (0, 0))


def outline_line(surface, points, closed=False):
    # Мягкий стиль без жёсткого контура.
    return


def snake_body(top, bottom, scale_color, name, variant=0):
    surface = canvas()
    mask = canvas()
    radius = BODY // 2

    pygame.draw.rect(
        mask,
        (255, 255, 255, 255),
        (-radius, MID - radius, S + 2 * radius, BODY),
        border_radius=radius,
    )

    shaded = shade(mask, top, bottom)
    surface.blit(shaded, (0, 0))
    add_scales(surface, mask, scale_color, variant * 19)

    outline_line(surface, [(0, MID - radius), (S, MID - radius)])
    outline_line(surface, [(0, MID + radius), (S, MID + radius)])

    save(surface, f"snake_body_{name}.png")


def snake_corner(top, bottom, scale_color, name):
    surface = canvas()
    mask = canvas()
    points = [(-RADIUS, MID), (MID, MID), (MID, -RADIUS)]

    pygame.draw.lines(mask, (255, 255, 255, 255), False, points, BODY)
    pygame.draw.circle(mask, (255, 255, 255, 255), (MID, MID), RADIUS)

    shaded = shade(mask, top, bottom)
    surface.blit(shaded, (0, 0))
    add_scales(surface, mask, scale_color, 9)


    save(surface, f"snake_corner_{name}.png")


def snake_tail(top, bottom, scale_color, name):
    surface = canvas()
    mask = canvas()
    cap = int(BODY * 0.32)
    tip_x = S - cap

    points = [
        (0, MID - RADIUS),
        (int(S * 0.42), MID - RADIUS),
        (tip_x, MID - cap),
        (tip_x, MID + cap),
        (int(S * 0.42), MID + RADIUS),
        (0, MID + RADIUS),
    ]

    pygame.draw.polygon(mask, (255, 255, 255, 255), points)
    pygame.draw.circle(mask, (255, 255, 255, 255), (tip_x, MID), cap)
    shaded = shade(mask, top, bottom)
    surface.blit(shaded, (0, 0))
    add_scales(surface, mask, scale_color, 21)


    save(surface, f"snake_tail_{name}.png")


def snake_head(color, name, blink=False):
    surface = canvas()
    mask = canvas()
    head_body = int(S * 0.76)
    radius = head_body // 2
    head_x = int(S * 0.58)

    # Голова — вытянутая капсула: скруглена и сзади, и спереди.
    # Она длиннее своей ширины, поэтому не выглядит просто кругом,
    # но у неё нет прямых углов, которые цеплялись бы на поворотах.
    pygame.draw.rect(
        mask,
        (255, 255, 255, 255),
        (0, MID - radius, head_x + radius, head_body),
        border_radius=radius,
    )

    surface.fill(color + (255,))
    surface.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

    # Большие выразительные глаза.
    eye_x = head_x + int(radius * 0.28)
    eye_y = int(radius * 0.42)
    eye_r = max(5, int(S * 0.125))

    for sign in (-1, 1):
        cy = MID + sign * eye_y

        if blink:
            # Закрытый глаз — дуга века, без белка.
            rect = pygame.Rect(
                eye_x - eye_r,
                cy - eye_r // 2,
                eye_r * 2,
                eye_r,
            )
            pygame.draw.arc(
                surface,
                (24, 48, 96),
                rect,
                math.radians(200),
                math.radians(340),
                max(6, S // 42),
            )
            continue

        pygame.draw.circle(
            surface,
            (250, 253, 255),
            (eye_x, cy),
            eye_r,
        )
        pygame.draw.circle(
            surface,
            (19, 26, 34),
            (eye_x + eye_r // 3, cy),
            max(3, int(eye_r * 0.50)),
        )
        pygame.draw.circle(
            surface,
            (255, 255, 255),
            (eye_x + eye_r // 3 - 1, cy - eye_r // 3),
            max(2, eye_r // 4),
        )

    # Пара ноздрей у кончика морды.
    nostril_x = head_x + int(radius * 0.80)
    for sign in (-1, 1):
        pygame.draw.circle(
            surface,
            (24, 48, 96),
            (nostril_x, MID + sign * int(radius * 0.16)),
            max(4, S // 60),
        )

    # Рот. Язык рисуется отдельно в UI и появляется только при «вспышке».
    pygame.draw.line(
        surface,
        (24, 48, 96),
        (head_x + int(radius * 0.55), MID + int(radius * 0.58)),
        (head_x + int(radius * 0.95), MID + int(radius * 0.40)),
        max(2, OUTLINE // 2),
    )

    suffix = "_blink" if blink else ""
    save(surface, f"snake_head_{name}{suffix}.png")


def apple():
    surface = canvas()
    cx = S // 2
    cy = int(S * 0.54)
    radius = int(S * 0.29)

    pygame.draw.ellipse(
        surface,
        (45, 12, 17, 120),
        (cx - radius, cy + radius // 2, radius * 2, radius),
    )
    pygame.draw.circle(
        surface,
        (125, 28, 38),
        (cx, cy),
        radius + int(S * 0.018),
    )
    pygame.draw.circle(surface, (238, 74, 86), (cx, cy), radius)
    pygame.draw.circle(
        surface,
        (190, 48, 62),
        (cx, cy + radius // 3),
        max(2, radius - radius // 5),
    )
    pygame.draw.circle(
        surface,
        (238, 74, 86),
        (cx, cy),
        max(2, radius - radius // 14),
    )
    pygame.draw.line(
        surface,
        (102, 68, 35),
        (cx, cy - radius + 2),
        (cx + radius // 5, cy - radius - int(S * 0.11)),
        max(2, S // 90),
    )
    pygame.draw.ellipse(
        surface,
        (46, 190, 112),
        (
            cx + radius // 4,
            cy - radius - int(S * 0.12),
            int(S * 0.16),
            int(S * 0.08),
        ),
    )
    pygame.draw.circle(
        surface,
        (255, 198, 190),
        (cx - radius // 3, cy - radius // 3),
        max(2, radius // 3),
    )
    pygame.draw.circle(
        surface,
        (255, 238, 230),
        (cx - radius // 3, cy - radius // 3),
        max(1, radius // 6),
    )
    save(surface, "apple.png")


def board_tile(light):
    size = 256
    surface = pygame.Surface((size, size), pygame.SRCALPHA)
    top = (124, 182, 82) if light else (112, 170, 72)
    bottom = (112, 170, 72) if light else (102, 160, 64)

    for y in range(size):
        t = y / (size - 1)
        color = tuple(int(a + (b - a) * t) for a, b in zip(top, bottom))
        pygame.draw.line(surface, color, (0, y), (size, y))

    pygame.image.save(surface, str(ASSETS / (
        "board_light.png" if light else "board_dark.png"
    )))


pygame.init()

for palette, top, bottom, scale_color, head_color in (
    ("blue", (100, 176, 255), (37, 94, 208), (155, 210, 255), (74, 150, 250)),
    ("green", (116, 236, 164), (40, 156, 92), (188, 255, 211), (116, 236, 164)),
    ("purple", (196, 148, 255), (116, 62, 214), (232, 204, 255), (190, 138, 255)),
):
    snake_body(top, bottom, scale_color, palette, 0)
    snake_corner(top, bottom, scale_color, palette)
    snake_tail(top, bottom, scale_color, palette)
    snake_head(head_color, palette)
    snake_head(head_color, palette, blink=True)

apple()
board_tile(True)
board_tile(False)

print("assets written to", ASSETS)
