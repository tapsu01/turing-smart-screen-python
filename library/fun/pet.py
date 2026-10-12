# SPDX-License-Identifier: GPL-3.0-or-later
#
# turing-smart-screen-python - a Python system monitor and library for USB-C displays like Turing Smart Screen or XuanFang
# https://github.com/mathoudebine/turing-smart-screen-python/
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# A pixel-art cat that runs faster when the CPU is busy, sleeps when it is idle and sweats when it is hot.
# Sprites are drawn in code at low resolution then scaled up with NEAREST: no image file needed.

import math
from functools import lru_cache
from typing import Tuple

from PIL import Image, ImageDraw

from library.fun import ui

SPRITE_SIZE = (30, 18)  # low-resolution canvas
SCALE = 3

BODY = (247, 160, 72)
OUTLINE = (92, 52, 28)
STRIPE = (204, 108, 40)
MUZZLE = (252, 241, 230)
PINK = (240, 140, 150)
EYE = (30, 24, 24)
SWEAT = (110, 190, 255)

SLEEP_CPU_PERCENT = 3.0  # below this the cat takes a nap
MIN_SPEED = 25.0  # px/s on screen, at SLEEP_CPU_PERCENT
MAX_SPEED = 300.0  # px/s on screen, at 100% CPU
STEP_PX = 12.0  # distance between two running frames

# Leg segments (top x, bottom x) for each running frame: stretched, passing, gathered, passing
RUN_LEGS = [
    [(19, 23), (17, 21), (8, 4), (6, 2)],
    [(19, 18), (17, 16), (8, 9), (6, 7)],
    [(19, 16), (17, 14), (8, 11), (6, 9)],
    [(19, 19), (17, 17), (8, 8), (6, 6)],
]
RUN_BOB = [0, -1, 0, -1]
RUN_TAIL_TIP = [(0, 3), (1, 2), (0, 5), (1, 2)]


@lru_cache(maxsize=None)
def run_sprite(frame: int) -> Image.Image:
    img = Image.new("RGBA", SPRITE_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    dy = RUN_BOB[frame]

    tail_x, tail_y = RUN_TAIL_TIP[frame]
    draw.line([(5, 8 + dy), (tail_x, tail_y + dy)], fill=OUTLINE, width=3)
    draw.line([(5, 8 + dy), (tail_x, tail_y + dy)], fill=BODY, width=1)

    for top_x, bottom_x in RUN_LEGS[frame]:
        draw.line([(top_x, 12 + dy), (bottom_x, 16)], fill=OUTLINE, width=2)
        draw.point((bottom_x, 17), fill=OUTLINE)

    draw.rounded_rectangle((4, 6 + dy, 21, 13 + dy), radius=3, fill=BODY, outline=OUTLINE)
    for x in (9, 12, 15):
        draw.line([(x, 7 + dy), (x, 9 + dy)], fill=STRIPE)

    _draw_head(draw, dy)
    return img.resize((SPRITE_SIZE[0] * SCALE, SPRITE_SIZE[1] * SCALE), Image.NEAREST)


def _draw_head(draw: ImageDraw.ImageDraw, dy: int):
    draw.polygon([(18, 4 + dy), (19, 0 + dy), (22, 2 + dy)], fill=BODY, outline=OUTLINE)
    draw.polygon([(23, 2 + dy), (26, 0 + dy), (27, 5 + dy)], fill=BODY, outline=OUTLINE)
    draw.ellipse((17, 1 + dy, 28, 11 + dy), fill=BODY, outline=OUTLINE)
    draw.point([(19, 2 + dy), (25, 2 + dy)], fill=PINK)
    draw.ellipse((23, 6 + dy, 28, 10 + dy), fill=MUZZLE)
    draw.rectangle((23, 4 + dy, 23, 5 + dy), fill=EYE)
    draw.point((28, 7 + dy), fill=PINK)


@lru_cache(maxsize=None)
def sleep_sprite() -> Image.Image:
    img = Image.new("RGBA", SPRITE_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.line([(8, 16), (26, 16)], fill=OUTLINE, width=3)
    draw.line([(8, 16), (26, 16)], fill=BODY, width=1)
    draw.ellipse((6, 7, 27, 17), fill=BODY, outline=OUTLINE)
    for x in (14, 17, 20):
        draw.line([(x, 8), (x + 1, 11)], fill=STRIPE)
    draw.polygon([(3, 11), (3, 6), (7, 9)], fill=BODY, outline=OUTLINE)
    draw.polygon([(9, 9), (11, 6), (12, 10)], fill=BODY, outline=OUTLINE)
    draw.ellipse((2, 8, 13, 17), fill=BODY, outline=OUTLINE)
    draw.point([(4, 8), (11, 8)], fill=PINK)
    draw.ellipse((2, 12, 7, 16), fill=MUZZLE)
    draw.line([(6, 11), (8, 11)], fill=EYE)
    draw.point((2, 13), fill=PINK)
    return img.resize((SPRITE_SIZE[0] * SCALE, SPRITE_SIZE[1] * SCALE), Image.NEAREST)


class CpuPet:
    def __init__(self, hot_temp: float = 70.0):
        self.hot_temp = hot_temp
        self.x = 0.0
        self.step_distance = 0.0
        self.frame = 0
        self.time = 0.0
        self.cpu_percent = 0.0
        self.temperature = math.nan

    @property
    def sleeping(self) -> bool:
        return self.cpu_percent < SLEEP_CPU_PERCENT

    @property
    def hot(self) -> bool:
        return not math.isnan(self.temperature) and self.temperature >= self.hot_temp

    def update(self, dt: float, cpu_percent: float, temperature: float, area_width: int):
        self.time += dt
        self.cpu_percent = cpu_percent
        self.temperature = temperature
        if self.sleeping:
            return

        load = min(1.0, max(0.0, (cpu_percent - SLEEP_CPU_PERCENT) / (100 - SLEEP_CPU_PERCENT)))
        dx = (MIN_SPEED + (MAX_SPEED - MIN_SPEED) * load) * dt
        self.x += dx
        sprite_width = SPRITE_SIZE[0] * SCALE
        if self.x > area_width:
            self.x = -sprite_width

        # At most one leg frame per update, otherwise high speeds alias into a random-looking animation
        self.step_distance += dx
        if self.step_distance >= STEP_PX:
            self.step_distance = 0
            self.frame = (self.frame + 1) % len(RUN_LEGS)

    def draw(self, img: Image.Image, box: Tuple[int, int, int, int]):
        """Draw the cat inside box (left, top, right, bottom); it is clipped to the box"""
        left, top, right, bottom = box
        layer = Image.new("RGBA", (right - left, bottom - top), (0, 0, 0, 0))
        sprite = sleep_sprite() if self.sleeping else run_sprite(self.frame)
        x = int(self.x)
        y = layer.height - sprite.height
        layer.paste(sprite, (x, y), sprite)

        draw = ImageDraw.Draw(layer)
        if self.sleeping:
            self._draw_zzz(draw, x + 30, y)
        if self.hot:
            self._draw_sweat(draw, x + (10 if self.sleeping else 78), y + 4)

        img.paste(layer, (left, top), layer)

    def _draw_zzz(self, draw: ImageDraw.ImageDraw, x: int, y: int):
        # Three letters rising one after the other, every 3 seconds
        for i, size in enumerate((12, 15, 18)):
            t = (self.time / 3.0 + i / 3.0) % 1.0
            draw.text((x + 14 * i + 10, y + 10 - t * 26), "z", font=ui.font(ui.FONT_BOLD, size),
                      fill=ui.MUTED if t < 0.8 else ui.GROUND)

    def _draw_sweat(self, draw: ImageDraw.ImageDraw, x: int, y: int):
        # Two drops sliding down, blinking at 2 Hz
        if int(self.time * 2) % 2:
            return
        for dx, dy in ((0, 0), (9, 6)):
            draw.polygon([(x + dx + 3, y + dy), (x + dx, y + dy + 6), (x + dx + 6, y + dy + 6)], fill=SWEAT)
            draw.ellipse((x + dx, y + dy + 3, x + dx + 6, y + dy + 9), fill=SWEAT)
