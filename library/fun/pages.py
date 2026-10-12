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

# Fun mode pages. Each page draws a 480x256 image that only changes once per second at most,
# so the image is cached by a key and redrawn only when the key changes.

import math
from datetime import datetime
from functools import lru_cache
from typing import Hashable, Optional

from PIL import Image, ImageDraw

from library.fun import ui
from library.fun.lunar import solar_to_lunar
from library.fun.pet import CpuPet
from library.fun.pomodoro import Phase, PomodoroState

PAGE_SIZE = (480, 256)
STRIP_HEIGHT = 64

WEEKDAYS = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]

PHASE_LABELS = {
    Phase.FOCUS: "Tập trung",
    Phase.SHORT_BREAK: "Nghỉ ngắn",
    Phase.LONG_BREAK: "Nghỉ dài",
}
PHASE_COLORS = {
    Phase.FOCUS: ui.TOMATO,
    Phase.SHORT_BREAK: ui.GREEN,
    Phase.LONG_BREAK: ui.BLUE,
}

DIAL_CENTER = (124, 128)
DIAL_RADIUS = 108
RIGHT_COLUMN_X = 256
RIGHT_COLUMN_WIDTH = 214


def _draw_tomato(draw: ImageDraw.ImageDraw, x: int, y: int, size: int, filled: bool = True):
    fill = ui.TOMATO if filled else None
    outline = ui.TOMATO if filled else ui.GROUND
    draw.ellipse((x, y + size // 6, x + size, y + size), fill=fill, outline=outline, width=2)
    leaf = (x + size // 2, y + size // 6)
    draw.polygon([(leaf[0] - size // 3, leaf[1]), (leaf[0], leaf[1] - size // 6), (leaf[0] + size // 3, leaf[1]),
                  (leaf[0], leaf[1] + size // 6)], fill=ui.GREEN if filled else ui.GROUND)


class CachedPage:
    def __init__(self):
        self._key: Optional[Hashable] = None
        self._image: Optional[Image.Image] = None

    def image(self, key: Hashable, *args) -> Image.Image:
        if key != self._key or self._image is None:
            self._image = Image.new("RGB", PAGE_SIZE, ui.BACKGROUND)
            self.draw(self._image, *args)
            self._key = key
        return self._image

    def draw(self, img: Image.Image, *args):
        raise NotImplementedError


@lru_cache(maxsize=1)
def _dial_face() -> Image.Image:
    """Clock face without hands, drawn SUPERSAMPLING times bigger"""
    s = ui.SUPERSAMPLING
    size = (DIAL_RADIUS * 2 + 2) * s
    face = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(face)
    c = size / 2
    r = DIAL_RADIUS * s
    draw.ellipse((c - r, c - r, c + r, c + r), fill=ui.PANEL)
    for tick in range(60):
        angle = math.radians(tick * 6)
        hour_tick = tick % 5 == 0
        outer = r - 6 * s
        inner = outer - (12 if hour_tick else 5) * s
        draw.line([(c + inner * math.sin(angle), c - inner * math.cos(angle)),
                   (c + outer * math.sin(angle), c - outer * math.cos(angle))],
                  fill=ui.TEXT if hour_tick else ui.MUTED, width=(4 if hour_tick else 2) * s // 2)
    number_font = ui.font(ui.FONT_MEDIUM, 20 * s)
    for number, angle in ((12, 0), (3, 90), (6, 180), (9, 270)):
        distance = r - 34 * s
        x = c + distance * math.sin(math.radians(angle))
        y = c - distance * math.cos(math.radians(angle))
        draw.text((x, y), str(number), font=number_font, fill=ui.TEXT, anchor="mm")
    return face


def _draw_hand(draw: ImageDraw.ImageDraw, c: float, angle_deg: float, length: float, tail: float, width: int,
               color: ui.Color):
    angle = math.radians(angle_deg)
    dx, dy = math.sin(angle), -math.cos(angle)
    draw.line([(c - tail * dx, c - tail * dy), (c + length * dx, c + length * dy)], fill=color, width=width)


def _draw_dial(img: Image.Image, now: datetime):
    s = ui.SUPERSAMPLING
    face = _dial_face().copy()
    draw = ImageDraw.Draw(face)
    c = face.width / 2
    r = DIAL_RADIUS * s
    _draw_hand(draw, c, (now.hour % 12 + now.minute / 60) * 30, r * 0.50, r * 0.08, 8 * s, ui.TEXT)
    _draw_hand(draw, c, (now.minute + now.second / 60) * 6, r * 0.74, r * 0.08, 5 * s, ui.TEXT)
    _draw_hand(draw, c, now.second * 6, r * 0.84, r * 0.18, 2 * s, ui.TOMATO)
    draw.ellipse((c - 7 * s, c - 7 * s, c + 7 * s, c + 7 * s), fill=ui.TOMATO)
    draw.ellipse((c - 3 * s, c - 3 * s, c + 3 * s, c + 3 * s), fill=ui.PANEL)
    dial = face.resize((DIAL_RADIUS * 2 + 2, DIAL_RADIUS * 2 + 2), Image.LANCZOS)
    img.paste(dial, (DIAL_CENTER[0] - DIAL_RADIUS - 1, DIAL_CENTER[1] - DIAL_RADIUS - 1), dial)


class ClockPage(CachedPage):
    def render(self, now: datetime, pomodoro: PomodoroState) -> Image.Image:
        return self.image((now.replace(microsecond=0), pomodoro.completed_today), now, pomodoro)

    def draw(self, img: Image.Image, now: datetime, pomodoro: PomodoroState):
        _draw_dial(img, now)
        draw = ImageDraw.Draw(img)
        x = RIGHT_COLUMN_X

        time_font = ui.font(ui.FONT_MONO_BOLD, 60)
        draw.text((x, 14), now.strftime("%H:%M"), font=time_font, fill=ui.TEXT)
        hours_minutes_width = ui.text_width(draw, now.strftime("%H:%M"), time_font)
        draw.text((x + hours_minutes_width + 6, 46), now.strftime("%S"), font=ui.font(ui.FONT_MONO_BOLD, 24),
                  fill=ui.ACCENT)

        draw.text((x, 92), WEEKDAYS[now.weekday()], font=ui.font(ui.FONT_MEDIUM, 26), fill=ui.TEXT)
        draw.text((x, 126), now.strftime("%d/%m/%Y"), font=ui.font(ui.FONT_REGULAR, 20), fill=ui.MUTED)
        if pomodoro.completed_today:
            count = str(pomodoro.completed_today)
            count_font = ui.font(ui.FONT_MEDIUM, 20)
            count_x = x + RIGHT_COLUMN_WIDTH - ui.text_width(draw, count, count_font)
            draw.text((count_x, 126), count, font=count_font, fill=ui.TEXT)
            _draw_tomato(draw, count_x - 26, 128, 20)

        draw.line([(x, 162), (x + RIGHT_COLUMN_WIDTH, 162)], fill=ui.GROUND, width=1)

        lunar = solar_to_lunar(now.date())
        draw.text((x, 172), "ÂM LỊCH", font=ui.font(ui.FONT_MEDIUM, 13), fill=ui.ACCENT)
        lunar_font = ui.font(ui.FONT_MEDIUM, 22)
        lunar_text = ui.fit_text(draw, f"{lunar.day_name()} tháng {lunar.month_name()}", lunar_font,
                                 RIGHT_COLUMN_WIDTH)
        draw.text((x, 192), lunar_text, font=lunar_font, fill=ui.TEXT)
        draw.text((x, 222), f"Năm {lunar.year_name()}", font=ui.font(ui.FONT_REGULAR, 18), fill=ui.MUTED)


class PomodoroPage(CachedPage):
    def render(self, now: datetime, pomodoro: PomodoroState) -> Image.Image:
        remaining = math.ceil(pomodoro.remaining)
        blink = pomodoro.paused and now.second % 2 == 0
        key = (pomodoro.phase, pomodoro.paused, remaining, pomodoro.round_in_cycle, pomodoro.completed_today,
               now.strftime("%H:%M"), blink)
        return self.image(key, now, pomodoro, remaining, blink)

    def draw(self, img: Image.Image, now: datetime, pomodoro: PomodoroState, remaining: int, blink: bool):
        color = PHASE_COLORS.get(pomodoro.phase, ui.MUTED)
        remaining_fraction = 0.0 if pomodoro.duration <= 0 else remaining / pomodoro.duration
        ui.draw_ring(img, DIAL_CENTER, DIAL_RADIUS - 4, 14, remaining_fraction, color, ui.PANEL)

        draw = ImageDraw.Draw(img)
        cx, cy = DIAL_CENTER
        minutes, seconds = divmod(max(0, remaining), 60)
        draw.text((cx, cy - 8), f"{minutes:02d}:{seconds:02d}", font=ui.font(ui.FONT_MONO_BOLD, 48),
                  fill=ui.MUTED if blink else ui.TEXT, anchor="mm")
        label = "Tạm dừng" if pomodoro.paused else PHASE_LABELS.get(pomodoro.phase, "")
        draw.text((cx, cy + 34), label, font=ui.font(ui.FONT_MEDIUM, 20), fill=color, anchor="mm")

        x = RIGHT_COLUMN_X
        draw.text((x, 20), "POMODORO", font=ui.font(ui.FONT_MEDIUM, 14), fill=ui.ACCENT)
        draw.text((x, 40), f"Lượt {pomodoro.round_in_cycle}/{pomodoro.rounds}", font=ui.font(ui.FONT_BOLD, 30),
                  fill=ui.TEXT)

        done_in_cycle = pomodoro.rounds if pomodoro.phase == Phase.LONG_BREAK else pomodoro.round_in_cycle - 1
        size = 28
        gap = min(12, (RIGHT_COLUMN_WIDTH - size * pomodoro.rounds) // max(1, pomodoro.rounds - 1))
        for i in range(pomodoro.rounds):
            _draw_tomato(draw, x + i * (size + gap), 88, size, filled=i < done_in_cycle)

        draw.line([(x, 136), (x + RIGHT_COLUMN_WIDTH, 136)], fill=ui.GROUND, width=1)
        draw.text((x, 150), "Hôm nay", font=ui.font(ui.FONT_REGULAR, 18), fill=ui.MUTED)
        _draw_tomato(draw, x, 178, 26)
        draw.text((x + 34, 174), str(pomodoro.completed_today), font=ui.font(ui.FONT_BOLD, 28), fill=ui.TEXT)

        clock_font = ui.font(ui.FONT_MONO_BOLD, 22)
        clock = now.strftime("%H:%M")
        draw.text((x + RIGHT_COLUMN_WIDTH - ui.text_width(draw, clock, clock_font), 222), clock, font=clock_font,
                  fill=ui.MUTED)


class StatusStrip:
    """Bottom strip: running cat on the left, CPU load and temperature on the right"""
    CAT_AREA_WIDTH = 330
    STATS_X = 344

    def draw(self, img: Image.Image, top: int, pet: CpuPet, cpu_percent: float, temperature: float):
        draw = ImageDraw.Draw(img)
        width = img.width
        draw.rectangle((0, top, width, top + STRIP_HEIGHT), fill=ui.STRIP)
        draw.line([(0, top), (width, top)], fill=ui.GROUND, width=1)
        draw.line([(0, top + STRIP_HEIGHT - 3), (self.CAT_AREA_WIDTH, top + STRIP_HEIGHT - 3)], fill=ui.GROUND,
                  width=1)

        pet.draw(img, (0, top + 4, self.CAT_AREA_WIDTH, top + STRIP_HEIGHT - 3))

        label_font = ui.font(ui.FONT_MEDIUM, 12)
        value_font = ui.font(ui.FONT_MONO_BOLD, 24)
        temperature_text = "--" if math.isnan(temperature) else f"{temperature:.0f}°C"
        temperature_color = ui.TOMATO if pet.hot else ui.TEXT
        for x, label, value, color in ((self.STATS_X, "CPU", f"{cpu_percent:.0f}%", ui.TEXT),
                                       (self.STATS_X + 70, "NHIỆT ĐỘ", temperature_text, temperature_color)):
            draw.text((x, top + 10), label, font=label_font, fill=ui.MUTED)
            draw.text((x, top + 26), value, font=value_font, fill=color)
