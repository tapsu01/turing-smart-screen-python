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

# Shared look of the fun mode pages: colors, fonts and small drawing helpers

from functools import lru_cache
from typing import Tuple

from PIL import Image, ImageDraw, ImageFont

from library.config import FONTS_DIR

Color = Tuple[int, int, int]

BACKGROUND: Color = (14, 17, 24)
PANEL: Color = (28, 33, 46)
TEXT: Color = (236, 239, 244)
MUTED: Color = (138, 148, 168)
ACCENT: Color = (255, 183, 77)
TOMATO: Color = (239, 83, 80)
GREEN: Color = (102, 187, 106)
BLUE: Color = (79, 168, 245)
STRIP: Color = (20, 24, 34)
GROUND: Color = (52, 60, 78)

SUPERSAMPLING = 3  # Shapes are drawn bigger then scaled down: PIL does not anti-alias lines and arcs

# Roboto and JetBrains Mono both include Vietnamese diacritics
FONT_REGULAR = "roboto/Roboto-Regular.ttf"
FONT_MEDIUM = "roboto/Roboto-Medium.ttf"
FONT_BOLD = "roboto/Roboto-Bold.ttf"
FONT_MONO_BOLD = "jetbrains-mono/JetBrainsMono-Bold.ttf"


@lru_cache(maxsize=None)
def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONTS_DIR + name, size)


def text_width(draw: ImageDraw.ImageDraw, text: str, text_font: ImageFont.FreeTypeFont) -> int:
    left, _, right, _ = draw.textbbox((0, 0), text, font=text_font)
    return right - left


def fit_text(draw: ImageDraw.ImageDraw, text: str, text_font: ImageFont.FreeTypeFont, max_width: int) -> str:
    """Shorten the text with an ellipsis so that it fits in max_width pixels"""
    if text_width(draw, text, text_font) <= max_width:
        return text
    while text and text_width(draw, text + "…", text_font) > max_width:
        text = text[:-1]
    return text.rstrip() + "…"


def draw_ring(img: Image.Image, center: Tuple[int, int], radius: int, width: int, progress: float,
              color: Color, track_color: Color):
    """Anti-aliased circular progress ring, filled clockwise from 12 o'clock"""
    size = (radius * 2 + 2) * SUPERSAMPLING
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    box = (SUPERSAMPLING, SUPERSAMPLING, size - SUPERSAMPLING, size - SUPERSAMPLING)
    draw.ellipse(box, outline=track_color, width=width * SUPERSAMPLING)
    progress = min(1.0, max(0.0, progress))
    if progress > 0:
        draw.arc(box, start=-90, end=-90 + 360 * progress, fill=color, width=width * SUPERSAMPLING)
    layer = layer.resize((radius * 2 + 2, radius * 2 + 2), Image.LANCZOS)
    img.paste(layer, (center[0] - radius - 1, center[1] - radius - 1), layer)


def draw_bar(draw: ImageDraw.ImageDraw, box: Tuple[int, int, int, int], progress: float, color: Color,
             track_color: Color):
    left, top, right, bottom = box
    radius = (bottom - top) // 2
    draw.rounded_rectangle(box, radius=radius, fill=track_color)
    filled = left + round((right - left) * min(1.0, max(0.0, progress)))
    if filled - left >= bottom - top:
        draw.rounded_rectangle((left, top, filled, bottom), radius=radius, fill=color)
