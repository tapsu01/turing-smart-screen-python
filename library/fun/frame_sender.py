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

# Sends full frames to the display, but only the parts that changed since the previous frame.
# A full 480x320 frame is 300 KB of RGB565 data: far too slow to send 10 times per second over USB full-speed,
# while a ticking second hand or a small walking sprite only changes a few KB.

from typing import List, Optional, Tuple

from PIL import Image, ImageChops

from library.lcd.lcd_comm import LcdComm

DEFAULT_BAND_HEIGHT = 32  # px: changes are searched band by band, so 2 far-apart changes are sent as 2 small areas


class FrameSender:
    def __init__(self, lcd: LcdComm, band_height: int = DEFAULT_BAND_HEIGHT):
        self.lcd = lcd
        self.band_height = band_height
        self.previous: Optional[Image.Image] = None

    def changed_areas(self, frame: Image.Image) -> List[Tuple[int, int, int, int]]:
        """(left, top, right, bottom) boxes that differ from the previous frame"""
        if self.previous is None or self.previous.size != frame.size:
            return [(0, 0, frame.width, frame.height)]

        areas = []
        for top in range(0, frame.height, self.band_height):
            bottom = min(top + self.band_height, frame.height)
            band_box = (0, top, frame.width, bottom)
            bbox = ImageChops.difference(frame.crop(band_box), self.previous.crop(band_box)).getbbox()
            if bbox:
                areas.append((bbox[0], top + bbox[1], bbox[2], top + bbox[3]))
        return areas

    def push(self, frame: Image.Image) -> int:
        """Send the changed parts of the frame, returns the number of pixels sent"""
        frame = frame.convert("RGB")
        pixels = 0
        for left, top, right, bottom in self.changed_areas(frame):
            self.lcd.DisplayPILImage(frame.crop((left, top, right, bottom)), left, top)
            pixels += (right - left) * (bottom - top)
        self.previous = frame
        return pixels

    def invalidate(self):
        """Force a full frame on next push (e.g. after the display was reset)"""
        self.previous = None
