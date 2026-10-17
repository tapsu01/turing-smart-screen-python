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

# Cat care: food and joy go down while the program runs, feeding and petting (tray menu) bring them back up.
# Gentle on purpose: nothing changes while the program is stopped, and an empty stat only makes the cat slow and sad.
# Fed from the tray menu thread and ticked from the render thread, so every public method takes the lock.

import json
import threading
from dataclasses import dataclass
from pathlib import Path

from library.log import logger

MAX_STAT = 100.0
DEFAULT_STAT = 80.0
FOOD_EMPTY_S = 6 * 3600  # from full to empty while the program runs
JOY_EMPTY_S = 4 * 3600
FEED_AMOUNT = 40.0
FULL_FOOD = 95.0  # from this level the cat refuses to eat
PET_AMOUNT = 25.0
REWARD_AMOUNT = 15.0  # completed Pomodoro round
LOW_STAT = 30.0


@dataclass(frozen=True)
class CareState:
    food: float
    joy: float

    @property
    def hungry(self) -> bool:
        return self.food < LOW_STAT

    @property
    def sad(self) -> bool:
        return self.joy < LOW_STAT


class PetCare:
    def __init__(self, food: float = DEFAULT_STAT, joy: float = DEFAULT_STAT):
        self.lock = threading.Lock()
        self.food = _clamp(food)
        self.joy = _clamp(joy)

    def tick(self, dt: float):
        with self.lock:
            self.food = _clamp(self.food - MAX_STAT * dt / FOOD_EMPTY_S)
            self.joy = _clamp(self.joy - MAX_STAT * dt / JOY_EMPTY_S)

    def feed(self) -> bool:
        """False when the cat is not hungry: it refuses the food"""
        with self.lock:
            if self.food >= FULL_FOOD:
                return False
            self.food = _clamp(self.food + FEED_AMOUNT)
            return True

    def pet(self):
        with self.lock:
            self.joy = _clamp(self.joy + PET_AMOUNT)

    def reward(self):
        with self.lock:
            self.joy = _clamp(self.joy + REWARD_AMOUNT)

    def state(self) -> CareState:
        with self.lock:
            return CareState(food=self.food, joy=self.joy)

    @classmethod
    def load(cls, path: Path) -> "PetCare":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls(food=float(data["food"]), joy=float(data["joy"]))
        except FileNotFoundError:
            return cls()
        except (OSError, ValueError, KeyError, TypeError) as e:
            logger.warning(f"Cannot read cat care state from {path}, starting again: {e}")
            return cls()

    def save(self, path: Path):
        with self.lock:
            data = {"food": round(self.food, 2), "joy": round(self.joy, 2)}
            try:
                path.write_text(json.dumps(data), encoding="utf-8")
            except OSError as e:
                logger.warning(f"Cannot save cat care state to {path}: {e}")


def _clamp(value: float) -> float:
    return min(MAX_STAT, max(0.0, value))
