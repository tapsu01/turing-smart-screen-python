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
# A full 480x320 frame is 300 KB of RGB565 data and rev. A displays accept ~160 KB/s: sending only the changes is
# what makes animation possible.
#
# Changed pixels are grouped by 8x8 tiles, and touching dirty tiles form one "object" (the cat, a digit, a hand...):
# - a dense object is sent as one rectangle, so that it is never torn in 2 updates
# - a sparse object (e.g. a diagonal clock hand) is sent row by row, instead of its mostly unchanged bounding box
# Two changes far apart never share a rectangle, so a small change cannot make a big area to resend.

from typing import List, Optional, Tuple

import numpy as np
from PIL import Image, ImageChops

from library.lcd.lcd_comm import LcdComm

Box = Tuple[int, int, int, int]  # left, top, right (excluded), bottom (excluded)

TILE = 8  # px
DENSE_RATIO = 0.5  # an object whose dirty tiles fill at least this part of its bounding box is sent in one piece

NEIGHBOURS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def _dirty_tiles(mask: np.ndarray) -> np.ndarray:
    """Tile grid where True means at least one pixel of the tile changed"""
    height, width = mask.shape
    rows, cols = -(-height // TILE), -(-width // TILE)
    padded = np.zeros((rows * TILE, cols * TILE), dtype=bool)
    padded[:height, :width] = mask
    return padded.reshape(rows, TILE, cols, TILE).any(axis=(1, 3))


def _objects(tiles: np.ndarray) -> List[List[Tuple[int, int]]]:
    """Groups of touching dirty tiles (8-connectivity), as lists of (row, col)"""
    seen = np.zeros_like(tiles)
    objects = []
    for row, col in zip(*np.nonzero(tiles)):
        if seen[row, col]:
            continue
        seen[row, col] = True
        stack, group = [(row, col)], []
        while stack:
            r, c = stack.pop()
            group.append((r, c))
            for dr, dc in NEIGHBOURS:
                nr, nc = r + dr, c + dc
                if 0 <= nr < tiles.shape[0] and 0 <= nc < tiles.shape[1] and tiles[nr, nc] and not seen[nr, nc]:
                    seen[nr, nc] = True
                    stack.append((nr, nc))
        objects.append(group)
    return objects


def _tile_boxes(group: List[Tuple[int, int]]) -> List[Tuple[int, int, int, int]]:
    """Tile rectangles (row0, col0, row1, col1, inclusive) to send for one object"""
    rows = [r for r, _ in group]
    cols = [c for _, c in group]
    row0, row1, col0, col1 = min(rows), max(rows), min(cols), max(cols)
    if len(group) >= DENSE_RATIO * (row1 - row0 + 1) * (col1 - col0 + 1):
        return [(row0, col0, row1, col1)]

    # Sparse object: one rectangle per run of consecutive dirty tiles on each tile row
    boxes = []
    by_row = {}
    for r, c in group:
        by_row.setdefault(r, []).append(c)
    for r, row_cols in sorted(by_row.items()):
        row_cols.sort()
        start = previous = row_cols[0]
        for c in row_cols[1:] + [None]:
            if c is not None and c == previous + 1:
                previous = c
                continue
            boxes.append((r, start, r, previous))
            if c is not None:
                start = previous = c
    return boxes


def _tight_box(mask: np.ndarray, tile_box: Tuple[int, int, int, int]) -> Optional[Box]:
    """Pixel box of the changed pixels inside a tile rectangle"""
    row0, col0, row1, col1 = tile_box
    top, left = row0 * TILE, col0 * TILE
    area = mask[top:(row1 + 1) * TILE, left:(col1 + 1) * TILE]
    changed_rows = np.flatnonzero(area.any(axis=1))
    changed_cols = np.flatnonzero(area.any(axis=0))
    if not len(changed_rows):
        return None
    return (left + int(changed_cols[0]), top + int(changed_rows[0]),
            left + int(changed_cols[-1]) + 1, top + int(changed_rows[-1]) + 1)


def _intersects(a: Box, b: Box) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


class FrameSender:
    def __init__(self, lcd: LcdComm, priority_box: Optional[Box] = None):
        self.lcd = lcd
        # Changes inside this box are sent first in each frame (e.g. the animated sprite, so its pace stays regular)
        self.priority_box = priority_box
        self.previous: Optional[Image.Image] = None

    def changed_areas(self, frame: Image.Image) -> List[Box]:
        """Boxes that differ from the previous frame"""
        if self.previous is None or self.previous.size != frame.size:
            return [(0, 0, frame.width, frame.height)]

        # Max over R, G, B: a tiny change in a single channel must not be lost
        mask = np.asarray(ImageChops.difference(frame, self.previous)).max(axis=2) > 0
        boxes = []
        for group in _objects(_dirty_tiles(mask)):
            for tile_box in _tile_boxes(group):
                box = _tight_box(mask, tile_box)
                if box:
                    boxes.append(box)

        if self.priority_box:
            boxes.sort(key=lambda b: (not _intersects(b, self.priority_box), b[1], b[0]))
        else:
            boxes.sort(key=lambda b: (b[1], b[0]))
        return boxes

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
