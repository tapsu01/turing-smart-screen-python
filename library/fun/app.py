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

# Fun mode render loop: the only thread that writes to the display.

import math
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

import psutil
from PIL import Image

from library.fun import ui
from library.fun.frame_sender import FrameSender
from library.fun.pages import PAGE_SIZE, STRIP_HEIGHT, ClockPage, PomodoroPage, StatusStrip
from library.fun.pet import CpuPet
from library.fun.pomodoro import Phase, Pomodoro
from library.lcd.lcd_comm import LcdComm
from library.log import logger
from library.sensors.sensors_python import Cpu

CPU_REFRESH_S = 1.0
TEMPERATURE_REFRESH_S = 2.0
STATS_LOG_PERIOD_S = 10.0


class Mode(Enum):
    AUTO = "auto"  # Pomodoro page while a Pomodoro is running, clock otherwise
    CLOCK = "clock"
    POMODORO = "pomodoro"


@dataclass(frozen=True)
class FunSettings:
    fps: float = 10.0
    pomodoro_focus_min: float = 25
    pomodoro_short_break_min: float = 5
    pomodoro_long_break_min: float = 15
    pomodoro_rounds: int = 4
    pet_hot_temp: float = 70.0

    @classmethod
    def from_config(cls, data: dict) -> "FunSettings":
        defaults = cls()
        return cls(
            fps=float(data.get("FPS", defaults.fps)),
            pomodoro_focus_min=float(data.get("POMODORO_FOCUS_MIN", defaults.pomodoro_focus_min)),
            pomodoro_short_break_min=float(data.get("POMODORO_SHORT_BREAK_MIN", defaults.pomodoro_short_break_min)),
            pomodoro_long_break_min=float(data.get("POMODORO_LONG_BREAK_MIN", defaults.pomodoro_long_break_min)),
            pomodoro_rounds=int(data.get("POMODORO_ROUNDS", defaults.pomodoro_rounds)),
            pet_hot_temp=float(data.get("PET_HOT_TEMP", defaults.pet_hot_temp)),
        )


class FunApp:
    def __init__(self, lcd: LcdComm, settings: FunSettings, pomodoro: Pomodoro):
        self.settings = settings
        self.pomodoro = pomodoro
        # The cat area is sent first in each frame, so that its pace stays regular
        self.sender = FrameSender(lcd, priority_box=(0, PAGE_SIZE[1], StatusStrip.CAT_AREA_WIDTH,
                                                     PAGE_SIZE[1] + STRIP_HEIGHT))
        self.pet = CpuPet(hot_temp=settings.pet_hot_temp)
        self.clock_page = ClockPage()
        self.pomodoro_page = PomodoroPage()
        self.strip = StatusStrip()
        self.mode = Mode.AUTO
        self.stop_event = threading.Event()
        self.cpu_percent = 0.0
        self.temperature = math.nan

    def stop(self):
        self.stop_event.set()

    def render(self, now: datetime, dt: float) -> Image.Image:
        state = self.pomodoro.state()
        show_pomodoro = self.mode == Mode.POMODORO or (self.mode == Mode.AUTO and state.phase != Phase.IDLE)
        page = self.pomodoro_page if show_pomodoro else self.clock_page

        frame = Image.new("RGB", (PAGE_SIZE[0], PAGE_SIZE[1] + STRIP_HEIGHT), ui.BACKGROUND)
        frame.paste(page.render(now, state), (0, 0))
        self.pet.update(dt, self.cpu_percent, self.temperature, StatusStrip.CAT_AREA_WIDTH, self.settings.fps)
        self.strip.draw(frame, PAGE_SIZE[1], self.pet, self.cpu_percent, self.temperature)
        return frame

    def run(self):
        """Render and send frames until stop() is called"""
        frame_duration = 1.0 / self.settings.fps
        psutil.cpu_percent(interval=None)  # First call only initializes the measure
        last = time.monotonic()
        next_cpu = next_temperature = last
        stats_start, stats_frames, stats_pixels, stats_longest = last, 0, 0, 0.0

        while not self.stop_event.is_set():
            start = time.monotonic()
            dt = start - last
            last = start

            # Rev. A displays accept ~160 KB/s whatever the USB transfer size: log what the loop really achieves.
            # The longest frame shows hiccups that an average hides.
            if start - stats_start >= STATS_LOG_PERIOD_S:
                elapsed = start - stats_start
                logger.debug(f"Fun mode: {stats_frames / elapsed:.1f} fps, "
                             f"{stats_pixels * 2 / 1024 / elapsed:.0f} KB/s sent to display, "
                             f"longest frame {stats_longest * 1000:.0f} ms")
                stats_start, stats_frames, stats_pixels, stats_longest = start, 0, 0, 0.0
            stats_longest = max(stats_longest, dt)

            if start >= next_cpu:
                self.cpu_percent = psutil.cpu_percent(interval=None)
                next_cpu = start + CPU_REFRESH_S
            if start >= next_temperature:
                self.temperature = Cpu.temperature()
                next_temperature = start + TEMPERATURE_REFRESH_S

            self.pomodoro.tick()
            try:
                stats_pixels += self.sender.push(self.render(datetime.now(), dt))
                stats_frames += 1
            except Exception as e:
                # A failed frame must not kill the loop: the next one is complete again
                logger.error(f"Cannot send frame to display: {e}")
                self.sender.invalidate()

            self.stop_event.wait(max(0.0, frame_duration - (time.monotonic() - start)))
