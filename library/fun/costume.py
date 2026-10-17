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

# Seasonal outfits of the cat: Tết and Mid-Autumn (lunar calendar), Christmas, New Year and the user's birthday.
# Hats are drawn on the low-resolution sprite in place of the ears: there is no room above the head.
# Held items and falling petals are drawn at screen resolution, like the other effects of the cat.

import math
from datetime import date
from enum import Enum
from typing import Optional, Tuple

from PIL import ImageDraw

from library.fun import ui
from library.fun.lunar import solar_to_lunar

RED = (220, 48, 48)
WHITE = (248, 248, 248)
PARTY = (90, 150, 240)
CAKE = (250, 214, 226)


class Costume(Enum):
    NONE = "none"
    TET = "tet"
    MID_AUTUMN = "mid_autumn"
    CHRISTMAS = "christmas"
    NEW_YEAR = "new_year"
    BIRTHDAY = "birthday"


COSTUME_LABELS = {
    Costume.NONE: "Không mặc",
    Costume.TET: "Tết",
    Costume.MID_AUTUMN: "Trung Thu",
    Costume.CHRISTMAS: "Noel",
    Costume.NEW_YEAR: "Năm mới",
    Costume.BIRTHDAY: "Sinh nhật",
}


def parse_birthday(text: str) -> Optional[Tuple[int, int]]:
    """'DD/MM' -> (day, month), None when empty or invalid"""
    try:
        day, month = (int(part) for part in str(text).strip().split("/"))
        date(2000, month, day)  # leap year: 29/02 is accepted
        return day, month
    except (ValueError, TypeError):
        return None


def costume_for(day: date, birthday: Optional[Tuple[int, int]] = None) -> Costume:
    """Outfit of the day. When two occasions fall on the same day: birthday > Tết > Mid-Autumn > Christmas > New Year"""
    if birthday == (day.day, day.month):
        return Costume.BIRTHDAY
    lunar = solar_to_lunar(day)
    if not lunar.leap and ((lunar.month == 12 and lunar.day >= 23) or (lunar.month == 1 and lunar.day <= 7)):
        return Costume.TET
    if not lunar.leap and lunar.month == 8 and 10 <= lunar.day <= 16:
        return Costume.MID_AUTUMN
    if day.month == 12 and 20 <= day.day <= 26:
        return Costume.CHRISTMAS
    if (day.month, day.day) in ((12, 31), (1, 1), (1, 2)):
        return Costume.NEW_YEAR
    return Costume.NONE


def draw_hat(draw: ImageDraw.ImageDraw, costume: Costume, head_x: int, head_y: int, facing_left: bool = False):
    """Hat over the ears, on the low-resolution sprite. The ears span head_x..head_x+9 from row head_y,
    'behind the head' is on the left of a cat facing right."""

    def at(points):
        return [(head_x + (9 - px if facing_left else px), head_y + py) for px, py in points]

    if costume is Costume.CHRISTMAS:
        draw.polygon(at([(0, 3), (9, 3), (8, 1), (5, 0), (1, 0), (-3, 1)]), fill=RED)
        draw.line(at([(0, 3), (9, 3)]), fill=WHITE)
        draw.rectangle(_box(at([(-5, 1), (-4, 2)])), fill=WHITE)
    elif costume in (Costume.NEW_YEAR, Costume.BIRTHDAY):
        draw.polygon(at([(1, 3), (7, 3), (3, -1)]), fill=PARTY)
        draw.line(at([(2, 2), (6, 2)]), fill=ui.ACCENT)
        draw.line(at([(3, 0), (4, 0)]), fill=ui.ACCENT)
        draw.point(at([(2, -1)]), fill=ui.ACCENT)
    elif costume is Costume.TET:
        draw.rectangle(_box(at([(0, 2), (9, 3)])), fill=RED)
        draw.polygon(at([(0, 2), (-3, 0), (-3, 4)]), fill=RED)
        draw.point(at([(-1, 2), (5, 2)]), fill=ui.ACCENT)


def _box(points):
    (x0, y0), (x1, y1) = points
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


def draw_held_item(draw: ImageDraw.ImageDraw, costume: Costume, mouth_x: int, mouth_y: int, time: float):
    """Item carried in the mouth (screen coordinates): star lantern for Mid-Autumn, red envelope for Tết"""
    if costume is Costume.MID_AUTUMN:
        star_x, star_y = mouth_x + 15, mouth_y - 13
        draw.line([(mouth_x, mouth_y), (star_x, star_y)], fill=ui.MUTED, width=2)
        color = ui.ACCENT if int(time * 2) % 2 else (255, 128, 64)
        points = [(star_x + (8 if k % 2 == 0 else 3.5) * math.sin(k * math.pi / 5),
                   star_y + 1 - (8 if k % 2 == 0 else 3.5) * math.cos(k * math.pi / 5)) for k in range(10)]
        draw.polygon(points, fill=color, outline=RED)
        draw.line([(star_x, star_y + 7), (star_x, star_y + 12)], fill=RED)
    elif costume is Costume.TET:
        draw.rectangle((mouth_x, mouth_y - 3, mouth_x + 9, mouth_y + 9), fill=RED)
        draw.line([(mouth_x + 1, mouth_y + 1), (mouth_x + 8, mouth_y + 1)], fill=ui.ACCENT)
        draw.rectangle((mouth_x + 3, mouth_y + 4, mouth_x + 6, mouth_y + 6), fill=ui.ACCENT)


def draw_falling(draw: ImageDraw.ImageDraw, costume: Costume, width: int, height: int, time: float):
    """Apricot blossom petals (Tết) or confetti (New Year) slowly falling across the cat area"""
    if costume is Costume.TET:
        colors = [ui.ACCENT] * 4
    elif costume is Costume.NEW_YEAR:
        colors = [ui.ACCENT, PARTY, ui.TOMATO, ui.GREEN]
    else:
        return
    for i, color in enumerate(colors):
        t = (time / 6.0 + i / len(colors)) % 1.0
        x = (i * 89 + 37) % (width - 40) + round(math.sin(time * 1.3 + i) * 6)
        y = round(t * (height + 6)) - 4
        draw.rectangle((x, y, x + 2, y + 2), fill=color)


def draw_cake(draw: ImageDraw.ImageDraw, x: int, bottom: int, time: float):
    """Small birthday cake with a flickering candle (screen coordinates)"""
    draw.rectangle((x, bottom - 12, x + 17, bottom - 1), fill=CAKE, outline=ui.TOMATO)
    draw.line([(x + 1, bottom - 8), (x + 16, bottom - 8)], fill=ui.TOMATO)
    draw.rectangle((x + 8, bottom - 18, x + 9, bottom - 13), fill=PARTY)
    flame = (255, 210, 80) if int(time * 6) % 2 else (255, 150, 60)
    draw.ellipse((x + 7, bottom - 23, x + 10, bottom - 19), fill=flame)
