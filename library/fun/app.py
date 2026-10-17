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
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple

import psutil
from PIL import Image

from library.fun import ui
from library.fun.care import CareState, PetCare
from library.fun.costume import Costume, costume_for, parse_birthday
from library.fun.frame_sender import FrameSender
from library.fun.notify import notify
from library.fun.pages import PAGE_SIZE, STRIP_HEIGHT, ClockPage, PomodoroPage, StatusStrip
from library.fun.pet import Action, CpuPet
from library.fun.pomodoro import Phase, Pomodoro
from library.lcd.lcd_comm import LcdComm
from library.log import logger
from library.sensors.sensors_python import Cpu

CPU_REFRESH_S = 1.0
TEMPERATURE_REFRESH_S = 2.0
STATS_LOG_PERIOD_S = 10.0
CARE_SAVE_PERIOD_S = 300.0
CARE_MAX_TICK_S = 5.0  # a long hiccup (laptop asleep...) does not starve the cat
HUNGER_ALERT_FOOD = 20.0


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
    pet_care: bool = True
    pet_birthday: Optional[Tuple[int, int]] = None  # (day, month)

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
            pet_care=bool(data.get("PET_CARE", defaults.pet_care)),
            pet_birthday=parse_birthday(data.get("PET_BIRTHDAY") or ""),
        )


class FunApp:
    def __init__(self, lcd: LcdComm, settings: FunSettings, pomodoro: Pomodoro, care_path: Optional[Path] = None):
        self.settings = settings
        self.pomodoro = pomodoro
        # The cat area is sent first in each frame, so that its pace stays regular
        self.sender = FrameSender(lcd, priority_box=(0, PAGE_SIZE[1], StatusStrip.CAT_AREA_WIDTH,
                                                     PAGE_SIZE[1] + STRIP_HEIGHT))
        self.pet = CpuPet(hot_temp=settings.pet_hot_temp)
        # Only grows when a focus round runs to its end: a skipped round is not celebrated
        self.last_completed = pomodoro.state().completed_today
        # Food and joy of the cat, saved to care_path (no saving without it)
        self.care_path = care_path
        self.care = PetCare.load(care_path) if care_path else PetCare()
        self.care_enabled = settings.pet_care  # changed from the tray menu
        self.hunger_alerted = False
        # Outfit: None follows the calendar, a costume chosen in the tray menu is kept
        self.costume_choice: Optional[Costume] = None
        self.costume_of_day: Optional[Tuple[date, Costume]] = None
        self.clock_page = ClockPage()
        self.pomodoro_page = PomodoroPage()
        self.strip = StatusStrip()
        self.mode = Mode.AUTO
        self.stop_event = threading.Event()
        self.cpu_percent = 0.0
        self.temperature = math.nan

    def stop(self):
        self.stop_event.set()

    def feed_pet(self):
        """From the tray menu: the cat eats, or refuses when it is not hungry"""
        eaten = self.care.feed()
        self.pet.request(Action.EAT, variant=not eaten)
        self.save_care()

    def pet_cat(self):
        """From the tray menu: the cat purrs"""
        self.care.pet()
        self.pet.request(Action.PURR)
        self.save_care()

    def save_care(self):
        if self.care_path:
            self.care.save(self.care_path)

    def costume(self, today: date) -> Costume:
        if self.costume_choice is not None:
            return self.costume_choice
        if self.costume_of_day is None or self.costume_of_day[0] != today:
            self.costume_of_day = (today, costume_for(today, self.settings.pet_birthday))
        return self.costume_of_day[1]

    def update_care(self, dt: float, focus_done: bool) -> Optional[CareState]:
        if not self.care_enabled:
            self.pet.hungry = self.pet.sad = False
            return None
        self.care.tick(min(dt, CARE_MAX_TICK_S))
        if focus_done:
            self.care.reward()
        care = self.care.state()
        self.pet.hungry, self.pet.sad = care.hungry, care.sad
        # Once per hungry period: the alert comes back only after the cat has eaten
        if care.food < HUNGER_ALERT_FOOD and not self.hunger_alerted:
            self.hunger_alerted = True
            notify("Mèo đói rồi", "Cho mèo ăn chút cá nhé 🐟")
        elif not care.hungry:
            self.hunger_alerted = False
        return care

    def render(self, now: datetime, dt: float) -> Image.Image:
        state = self.pomodoro.state()
        show_pomodoro = self.mode == Mode.POMODORO or (self.mode == Mode.AUTO and state.phase != Phase.IDLE)
        page = self.pomodoro_page if show_pomodoro else self.clock_page
        focus_done = state.completed_today > self.last_completed
        if focus_done and self.pet.celebrate_enabled:
            self.pet.celebrate(big=state.phase == Phase.LONG_BREAK)
        self.last_completed = state.completed_today
        care = self.update_care(dt, focus_done)
        self.pet.costume = self.costume(now.date())

        frame = Image.new("RGB", (PAGE_SIZE[0], PAGE_SIZE[1] + STRIP_HEIGHT), ui.BACKGROUND)
        frame.paste(page.render(now, state), (0, 0))
        self.pet.update(dt, self.cpu_percent, self.temperature, StatusStrip.CAT_AREA_WIDTH, self.settings.fps)
        self.strip.draw(frame, PAGE_SIZE[1], self.pet, self.cpu_percent, self.temperature, care)
        return frame

    def run(self):
        """Render and send frames until stop() is called"""
        frame_duration = 1.0 / self.settings.fps
        psutil.cpu_percent(interval=None)  # First call only initializes the measure
        last = time.monotonic()
        next_cpu = next_temperature = last
        next_care_save = last + CARE_SAVE_PERIOD_S
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

            if start >= next_care_save:
                self.save_care()
                next_care_save = start + CARE_SAVE_PERIOD_S

            self.pomodoro.tick()
            try:
                stats_pixels += self.sender.push(self.render(datetime.now(), dt))
                stats_frames += 1
            except Exception as e:
                # A failed frame must not kill the loop: the next one is complete again
                logger.error(f"Cannot send frame to display: {e}")
                self.sender.invalidate()

            self.stop_event.wait(max(0.0, frame_duration - (time.monotonic() - start)))
        self.save_care()
