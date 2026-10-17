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

# A pixel-art cat that runs faster when the CPU is busy, sleeps when it is idle (or when told to) and sweats when it
# is hot. It startles when the load jumps, stretches and yawns when it wakes up and hops when a Pomodoro is done.
# It eats and purrs when cared for from the tray menu, slows down when hungry or sad, and dresses up on holidays.
# Sprites are drawn in code at low resolution then scaled up with NEAREST: no image file needed.
# The cat area is barely taller than the sprites: jumps are drawn as poses, effects next to the head, not above it.

import math
from enum import Enum
from functools import lru_cache
from typing import Optional, Tuple

from PIL import Image, ImageDraw

from library.fun import costume as outfit
from library.fun import ui
from library.fun.costume import Costume

SPRITE_SIZE = (30, 18)  # low-resolution canvas of the poses
# Poses are drawn one row lower on a taller canvas: the extra row on top leaves some room for hats
CANVAS_SIZE = (SPRITE_SIZE[0], SPRITE_SIZE[1] + 1)
SCALE = 3

BODY = (247, 160, 72)
OUTLINE = (92, 52, 28)
STRIPE = (204, 108, 40)
MUZZLE = (252, 241, 230)
PINK = (240, 140, 150)
EYE = (30, 24, 24)
SWEAT = (110, 190, 255)
FISH = (120, 170, 210)

SLEEP_CPU_PERCENT = 3.0  # below this (smoothed) load the cat takes a nap...
WAKE_CPU_PERCENT = 6.0  # ...and wakes up only above this one, so that it does not flicker around the threshold
CPU_SMOOTHING_S = 3.0  # time constant of the load smoothing: the CPU % measured each second jumps a lot
MIN_SPEED = 25.0  # px/s on screen, at SLEEP_CPU_PERCENT
MAX_SPEED = 300.0  # px/s on screen, at 100% CPU
STEP_PX = 12.0  # distance between two running frames
HUNGRY_SPEED_FACTOR = 0.6
SAD_SPEED_FACTOR = 0.8

# A load measure this far above the smoothed load startles the cat. The smoothed load needs a few seconds to catch up,
# so the jump stays visible for several frames: the cooldown keeps it to a single startle.
STARTLE_JUMP_PERCENT = 35.0
STARTLE_COOLDOWN_S = 10.0
HOP_PERIOD_S = 0.5  # crouch then jump
CHEW_PERIOD_S = 0.25

# Leg segments (top x, bottom x) for each running frame: stretched, passing, gathered, passing
RUN_LEGS = [
    [(19, 23), (17, 21), (8, 4), (6, 2)],
    [(19, 18), (17, 16), (8, 9), (6, 7)],
    [(19, 16), (17, 14), (8, 11), (6, 9)],
    [(19, 19), (17, 17), (8, 8), (6, 6)],
]
RUN_BOB = [0, -1, 0, -1]
RUN_TAIL_TIP = [(0, 3), (1, 2), (0, 5), (1, 2)]


class Action(Enum):
    """Short animation played over the running / sleeping state, the cat does not move meanwhile"""
    STARTLE = "startle"
    STRETCH = "stretch"
    CELEBRATE = "celebrate"
    EAT = "eat"
    PURR = "purr"


ACTION_DURATIONS = {
    Action.STARTLE: 1.0,
    Action.STRETCH: 1.5,
    Action.CELEBRATE: 3.0,
    Action.EAT: 3.0,
    Action.PURR: 2.5,
}
BIG_CELEBRATION_S = 5.0


def _finish(img: Image.Image, costume: Costume, head: Tuple[int, int], facing_left: bool = False) -> Image.Image:
    """Move the pose one row down on the taller canvas, put the hat on, scale up"""
    canvas = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
    canvas.paste(img, (0, 1), img)
    outfit.draw_hat(ImageDraw.Draw(canvas), costume, head[0], head[1] + 1, facing_left)
    return canvas.resize((CANVAS_SIZE[0] * SCALE, CANVAS_SIZE[1] * SCALE), Image.NEAREST)


def _new_pose() -> Tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGBA", SPRITE_SIZE, (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


@lru_cache(maxsize=None)
def run_sprite(frame: int, costume: Costume = Costume.NONE, eye: str = "open") -> Image.Image:
    img, draw = _new_pose()
    dy = RUN_BOB[frame]

    tail_x, tail_y = RUN_TAIL_TIP[frame]
    _draw_tail(draw, (5, 8 + dy), (tail_x, tail_y + dy))

    for top_x, bottom_x in RUN_LEGS[frame]:
        draw.line([(top_x, 12 + dy), (bottom_x, 16)], fill=OUTLINE, width=2)
        draw.point((bottom_x, 17), fill=OUTLINE)

    _draw_body(draw, dy)
    _draw_head(draw, dy, eye=eye)
    return _finish(img, costume, (18, dy))


def _draw_tail(draw: ImageDraw.ImageDraw, root: Tuple[int, int], tip: Tuple[int, int]):
    draw.line([root, tip], fill=OUTLINE, width=3)
    draw.line([root, tip], fill=BODY, width=1)


def _draw_body(draw: ImageDraw.ImageDraw, dy: int):
    draw.rounded_rectangle((4, 6 + dy, 21, 13 + dy), radius=3, fill=BODY, outline=OUTLINE)
    for x in (9, 12, 15):
        draw.line([(x, 7 + dy), (x, 9 + dy)], fill=STRIPE)


def _draw_head(draw: ImageDraw.ImageDraw, dy: int, eye: str = "open", mouth_open: bool = False):
    """eye: "open", "wide" (startled), "closed", "happy" (closed, curved up) or "sad" (worried brow)"""
    draw.polygon([(18, 4 + dy), (19, 0 + dy), (22, 2 + dy)], fill=BODY, outline=OUTLINE)
    draw.polygon([(23, 2 + dy), (26, 0 + dy), (27, 5 + dy)], fill=BODY, outline=OUTLINE)
    draw.ellipse((17, 1 + dy, 28, 11 + dy), fill=BODY, outline=OUTLINE)
    draw.point([(19, 2 + dy), (25, 2 + dy)], fill=PINK)
    draw.ellipse((23, 6 + dy, 28, 10 + dy), fill=MUZZLE)
    if eye == "wide":
        draw.rectangle((22, 3 + dy, 24, 5 + dy), fill=EYE)
        draw.point((22, 3 + dy), fill=MUZZLE)
    elif eye == "closed":
        draw.line([(22, 5 + dy), (24, 5 + dy)], fill=EYE)
    elif eye == "happy":
        draw.point([(22, 5 + dy), (23, 4 + dy), (24, 5 + dy)], fill=EYE)
    elif eye == "sad":
        draw.point([(23, 5 + dy), (22, 3 + dy), (23, 3 + dy), (24, 4 + dy)], fill=EYE)
        draw.line([(22, 6 + dy), (22, 7 + dy)], fill=SWEAT)
    else:
        draw.rectangle((23, 4 + dy, 23, 5 + dy), fill=EYE)
    if mouth_open:
        draw.ellipse((24, 7 + dy, 27, 11 + dy), fill=EYE)
        draw.line([(25, 10 + dy), (26, 10 + dy)], fill=PINK)
    draw.point((28, 7 + dy), fill=PINK)


@lru_cache(maxsize=None)
def sleep_sprite(costume: Costume = Costume.NONE) -> Image.Image:
    img, draw = _new_pose()
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
    return _finish(img, costume, (3, 6), facing_left=True)


@lru_cache(maxsize=None)
def startle_sprite(costume: Costume = Costume.NONE) -> Image.Image:
    """Arched back, bristling fur, stiff legs and bushy tail straight up"""
    img, draw = _new_pose()
    draw.line([(5, 9), (3, 1)], fill=OUTLINE, width=5)
    draw.line([(5, 9), (3, 1)], fill=BODY, width=3)
    for x in (6, 9, 16, 19):
        draw.line([(x, 10), (x, 16)], fill=OUTLINE, width=2)
        draw.point((x, 17), fill=OUTLINE)
    draw.chord((4, 2, 22, 20), 180, 360, fill=BODY, outline=OUTLINE)
    for root, tip in (((7, 5), (6, 3)), ((10, 3), (10, 1)), ((14, 3), (15, 1)), ((18, 5), (19, 3))):
        draw.line([root, tip], fill=OUTLINE)
    for x in (10, 13, 16):
        draw.line([(x, 5), (x, 7)], fill=STRIPE)
    _draw_head(draw, 4, eye="wide", mouth_open=True)
    return _finish(img, costume, (18, 4))


@lru_cache(maxsize=None)
def stretch_sprite(costume: Costume = Costume.NONE) -> Image.Image:
    """Play bow: rear up, chest down, front paws reaching forward, yawning"""
    img, draw = _new_pose()
    _draw_tail(draw, (5, 6), (2, 0))
    for x in (5, 8):
        draw.line([(x, 10), (x, 16)], fill=OUTLINE, width=2)
        draw.point((x, 17), fill=OUTLINE)
    draw.polygon([(4, 7), (7, 4), (19, 9), (19, 15), (5, 12)], fill=BODY, outline=OUTLINE)
    for x, y in ((10, 6), (13, 7), (16, 8)):
        draw.line([(x, y), (x, y + 2)], fill=STRIPE)
    _draw_head(draw, 4, eye="closed", mouth_open=True)
    draw.rounded_rectangle((15, 15, 29, 17), radius=1, fill=BODY, outline=OUTLINE)
    draw.point([(26, 16), (28, 16)], fill=OUTLINE)
    return _finish(img, costume, (18, 4))


@lru_cache(maxsize=None)
def hop_sprite(frame: int, costume: Costume = Costume.NONE) -> Image.Image:
    """0: crouched, ready to jump. 1: in the air, legs tucked, feet off the ground."""
    img, draw = _new_pose()
    if frame == 0:
        dy = 4
        _draw_tail(draw, (5, 8 + dy), (0, 10 + dy))
        for top_x, bottom_x in ((19, 21), (17, 19), (8, 6), (6, 4)):
            draw.line([(top_x, 12 + dy), (bottom_x, 17)], fill=OUTLINE, width=2)
    else:
        dy = 0
        _draw_tail(draw, (5, 8), (1, 1))
        for top_x, bottom_x in ((19, 22), (17, 20), (8, 5), (6, 3)):
            draw.line([(top_x, 12), (bottom_x, 14)], fill=OUTLINE, width=2)
    _draw_body(draw, dy)
    _draw_head(draw, dy, eye="happy")
    return _finish(img, costume, (18, dy))


@lru_cache(maxsize=None)
def sit_sprite(costume: Costume = Costume.NONE, eye: str = "open", mouth_open: bool = False) -> Image.Image:
    """Sitting up, tail curled on the ground: eating, being petted"""
    img, draw = _new_pose()
    _draw_tail(draw, (9, 16), (3, 16))
    _draw_tail(draw, (3, 16), (2, 13))
    draw.ellipse((7, 7, 22, 18), fill=BODY, outline=OUTLINE)
    for x, y in ((10, 9), (12, 8), (14, 8)):
        draw.line([(x, y), (x + 1, y + 2)], fill=STRIPE)
    for x in (18, 21):
        draw.line([(x, 11), (x, 16)], fill=OUTLINE, width=2)
        draw.point([(x, 17), (x + 1, 17)], fill=OUTLINE)
    _draw_head(draw, 1, eye=eye, mouth_open=mouth_open)
    return _finish(img, costume, (18, 1))


class CpuPet:
    def __init__(self, hot_temp: float = 70.0):
        self.hot_temp = hot_temp
        self.x = 0.0
        self.step_distance = 0.0
        self.frame = 0
        self.time = 0.0
        self.smoothed_cpu_percent: Optional[float] = None
        self.idle = False  # the CPU load is low enough for a nap
        self.force_sleep = False  # set from the tray menu: sleep whatever the load
        self.action: Optional[Action] = None
        self.action_left = 0.0
        self.action_duration = 0.0
        self.variant = False  # of the running action: big celebration, food refused
        self.next_startle_time = 0.0
        self.was_sleeping = False  # at the previous update: force_sleep may have changed in between
        # Set from the tray menu: automatic reactions that can be turned off, and an action asked for by hand
        self.startle_enabled = True
        self.stretch_enabled = True
        self.celebrate_enabled = True
        self.requested: Optional[Tuple[Action, bool]] = None
        # Set by the app: mood from the care stats, outfit of the day
        self.hungry = False
        self.sad = False
        self.costume = Costume.NONE
        self.temperature = math.nan

    @property
    def sleeping(self) -> bool:
        return self.action is None and (self.force_sleep or self.idle)

    @property
    def hot(self) -> bool:
        return not math.isnan(self.temperature) and self.temperature >= self.hot_temp

    @property
    def big_celebration(self) -> bool:
        return self.action is Action.CELEBRATE and self.variant

    @property
    def speed(self) -> float:
        """Running speed in px/s, from the smoothed CPU load, slower when hungry or sad"""
        load = (self.smoothed_cpu_percent or 0.0) - SLEEP_CPU_PERCENT
        load = min(1.0, max(0.0, load / (100 - SLEEP_CPU_PERCENT)))
        speed = MIN_SPEED + (MAX_SPEED - MIN_SPEED) * load
        if self.hungry:
            speed *= HUNGRY_SPEED_FACTOR
        if self.sad:
            speed *= SAD_SPEED_FACTOR
        return speed

    def celebrate(self, big: bool = False):
        """Hop for a few seconds, even if asleep: it falls asleep again afterwards if it should"""
        self._start(Action.CELEBRATE, big, BIG_CELEBRATION_S if big else None)

    def request(self, action: Action, variant: bool = False):
        """Play an action at the next update. Called from the tray thread: the render thread does the change.
        variant: big celebration, or food refused because the cat is not hungry."""
        self.requested = (action, variant)

    def _start(self, action: Action, variant: bool = False, duration: Optional[float] = None):
        self.action = action
        self.variant = variant
        self.action_duration = ACTION_DURATIONS[action] if duration is None else duration
        self.action_left = self.action_duration

    def update(self, dt: float, cpu_percent: float, temperature: float, area_width: int, fps: float):
        self.time += dt
        self.temperature = temperature
        previous_cpu_percent = self.smoothed_cpu_percent
        if previous_cpu_percent is None:
            self.smoothed_cpu_percent = cpu_percent
        else:
            weight = 1 - math.exp(-dt / CPU_SMOOTHING_S)
            self.smoothed_cpu_percent += (cpu_percent - self.smoothed_cpu_percent) * weight

        if self.action is not None:
            self.action_left -= dt
            if self.action_left <= 0:
                self.action = None

        if self.idle and self.smoothed_cpu_percent > WAKE_CPU_PERCENT:
            self.idle = False
        elif not self.idle and self.smoothed_cpu_percent < SLEEP_CPU_PERCENT:
            self.idle = True

        requested, self.requested = self.requested, None
        spike = (previous_cpu_percent is not None and cpu_percent - previous_cpu_percent >= STARTLE_JUMP_PERCENT
                 and self.time >= self.next_startle_time)
        if requested is not None:
            # Asked by hand: played even when asleep (it falls asleep again afterwards if it should)
            action, variant = requested
            if action is Action.CELEBRATE:
                self.celebrate(variant)
            else:
                self._start(action, variant)
        elif (spike and self.startle_enabled and not self.force_sleep
              and self.action not in (Action.CELEBRATE, Action.EAT, Action.PURR)):
            # Also wakes up from a nap at once, without waiting for the smoothed load to rise
            self.idle = False
            self._start(Action.STARTLE)
            self.next_startle_time = self.time + STARTLE_COOLDOWN_S
        elif self.was_sleeping and not self.sleeping and self.action is None and self.stretch_enabled:
            self._start(Action.STRETCH)
        self.was_sleeping = self.sleeping
        if self.action is not None or self.sleeping:
            return

        # Same step for every drawn frame, whatever the real frame duration: when a frame takes longer to send,
        # the cat slows down a little instead of jumping forward
        dx = self.speed / fps
        self.x += dx
        sprite_width = SPRITE_SIZE[0] * SCALE
        if self.x > area_width:
            self.x = -sprite_width

        # At most one leg frame per update, otherwise high speeds alias into a random-looking animation.
        # The remaining distance is kept (but capped) so that the leg cadence stays regular.
        self.step_distance += dx
        if self.step_distance >= STEP_PX:
            self.step_distance = min(self.step_distance - STEP_PX, STEP_PX)
            self.frame = (self.frame + 1) % len(RUN_LEGS)

    def sprite(self) -> Image.Image:
        costume = self.costume
        if self.sleeping:
            return sleep_sprite(costume)
        if self.action is Action.STARTLE:
            return startle_sprite(costume)
        if self.action is Action.STRETCH:
            return stretch_sprite(costume)
        if self.action is Action.CELEBRATE:
            return hop_sprite(int(self.time * 2 / HOP_PERIOD_S) % 2, costume)
        if self.action is Action.EAT:
            if self.variant:
                return sit_sprite(costume, eye="closed")
            return sit_sprite(costume, eye="happy", mouth_open=int(self.time / CHEW_PERIOD_S) % 2 == 0)
        if self.action is Action.PURR:
            return sit_sprite(costume, eye="happy")
        return run_sprite(self.frame, costume, "sad" if self.sad else "open")

    def draw(self, img: Image.Image, box: Tuple[int, int, int, int]):
        """Draw the cat inside box (left, top, right, bottom); it is clipped to the box"""
        left, top, right, bottom = box
        layer = Image.new("RGBA", (right - left, bottom - top), (0, 0, 0, 0))
        sprite = self.sprite()
        x = int(self.x)
        # Top of the pose: the canvas has an extra row above it for hats
        y = layer.height - SPRITE_SIZE[1] * SCALE
        layer.paste(sprite, (x, y - SCALE), sprite)

        draw = ImageDraw.Draw(layer)
        outfit.draw_falling(draw, self.costume, layer.width, layer.height, self.time)
        # Effects in front of the head, or behind the cat when it reaches the right edge
        ahead = x + 130 <= layer.width
        effect_x = x + 90 if ahead else x - 40
        if self.sleeping:
            self._draw_zzz(draw, x + 30, y)
            if self.costume is Costume.BIRTHDAY:
                outfit.draw_cake(draw, x + 84 if ahead else x - 24, layer.height - 1, self.time)
        elif self.action is Action.STARTLE:
            self._draw_alert(draw, effect_x, y)
        elif self.action is Action.CELEBRATE:
            self._draw_hearts(draw, effect_x, layer.height)
            if self.big_celebration:
                self._draw_stars(draw, effect_x, y)
        elif self.action is Action.EAT:
            if self.variant:
                draw.text((effect_x, y + 12), "...", font=ui.font(ui.FONT_BOLD, 18), fill=ui.MUTED)
            else:
                self._draw_fish(draw, x + 88 if ahead else x - 32, y + 27)
        elif self.action is Action.PURR:
            self._draw_hearts(draw, effect_x, layer.height)
            self._draw_purr(draw, x + 24, y + 12)
        if not self.sleeping and self.action not in (Action.STARTLE, Action.STRETCH, Action.EAT):
            mouth_y = y + (27 if self.action is not Action.PURR else 30)
            outfit.draw_held_item(draw, self.costume, x + 82, mouth_y, self.time)
        if self.hot:
            self._draw_sweat(draw, x + (10 if self.sleeping else 78), y + 4)

        img.paste(layer, (left, top), layer)

    def _draw_fish(self, draw: ImageDraw.ImageDraw, x: int, y: int):
        # Eaten from the head: shorter and shorter, only the bones at the end
        left = self.action_left / self.action_duration if self.action_duration else 0
        length = round(16 * left)
        if length < 4:
            draw.line([(x, y), (x + 12, y)], fill=MUZZLE)
            for bone_x in (x + 3, x + 6, x + 9):
                draw.line([(bone_x, y - 2), (bone_x, y + 2)], fill=MUZZLE)
            return
        tail_x = x + 16
        draw.polygon([(tail_x - 1, y), (tail_x + 5, y - 4), (tail_x + 5, y + 4)], fill=FISH)
        draw.ellipse((tail_x - length, y - 4, tail_x + 1, y + 4), fill=FISH)
        if length > 12:
            draw.point((tail_x - length + 3, y - 1), fill=EYE)

    def _draw_purr(self, draw: ImageDraw.ImageDraw, x: int, y: int):
        # "~" marks shaking above the back
        shake = 1 if int(self.time * 10) % 2 else 0
        font = ui.font(ui.FONT_BOLD, 16)
        draw.text((x + shake, y - 14), "~", font=font, fill=ui.MUTED)
        draw.text((x + 14 - shake, y - 18), "~", font=font, fill=ui.MUTED)

    def _draw_zzz(self, draw: ImageDraw.ImageDraw, x: int, y: int):
        # Three letters rising one after the other, every 3 seconds
        for i, size in enumerate((12, 15, 18)):
            t = (self.time / 3.0 + i / 3.0) % 1.0
            draw.text((x + 14 * i + 10, y + 10 - t * 26), "z", font=ui.font(ui.FONT_BOLD, size),
                      fill=ui.MUTED if t < 0.8 else ui.GROUND)

    def _draw_alert(self, draw: ImageDraw.ImageDraw, x: int, y: int):
        # Shaking exclamation mark
        shake = 1 if int(self.time * 12) % 2 else -1
        draw.text((x + 4 + shake, y + 2), "!", font=ui.font(ui.FONT_BOLD, 30), fill=ui.TOMATO)

    def _draw_hearts(self, draw: ImageDraw.ImageDraw, x: int, height: int):
        # Three hearts rising one after the other, every 1.5 seconds
        for i in range(3):
            t = (self.time / 1.5 + i / 3.0) % 1.0
            hx, hy = x + 13 * i, round(height - 12 - t * (height - 14))
            color = PINK if t < 0.8 else ui.GROUND
            draw.ellipse((hx, hy, hx + 5, hy + 5), fill=color)
            draw.ellipse((hx + 4, hy, hx + 9, hy + 5), fill=color)
            draw.polygon([(hx, hy + 3), (hx + 9, hy + 3), (hx + 4.5, hy + 9)], fill=color)

    def _draw_stars(self, draw: ImageDraw.ImageDraw, x: int, y: int):
        # Two stars twinkling in turn between the hearts
        for i, (sx, sy) in enumerate(((x + 8, y + 10), (x + 30, y + 28))):
            if (int(self.time * 4) + i) % 2:
                continue
            points = [(sx + (6 if k % 2 == 0 else 2.5) * math.sin(k * math.pi / 5),
                       sy - (6 if k % 2 == 0 else 2.5) * math.cos(k * math.pi / 5)) for k in range(10)]
            draw.polygon(points, fill=ui.ACCENT)

    def _draw_sweat(self, draw: ImageDraw.ImageDraw, x: int, y: int):
        # Two drops sliding down, blinking at 2 Hz
        if int(self.time * 2) % 2:
            return
        for dx, dy in ((0, 0), (9, 6)):
            draw.polygon([(x + dx + 3, y + dy), (x + dx, y + dy + 6), (x + dx + 6, y + dy + 6)], fill=SWEAT)
            draw.ellipse((x + dx, y + dy + 3, x + dx + 6, y + dy + 9), fill=SWEAT)
