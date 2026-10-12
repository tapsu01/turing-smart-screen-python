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

# Pomodoro timer: focus -> short break -> focus ... -> long break every N focus rounds.
# Controlled from the tray menu thread and ticked from the render thread, so every public method takes the lock.

import threading
import time
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Callable, Optional


class Phase(Enum):
    IDLE = "idle"
    FOCUS = "focus"
    SHORT_BREAK = "short_break"
    LONG_BREAK = "long_break"


@dataclass(frozen=True)
class PomodoroState:
    phase: Phase
    paused: bool
    remaining: float  # seconds
    duration: float  # seconds of the current phase
    round_in_cycle: int  # 1..rounds, focus round currently running (or next one during a break)
    rounds: int
    completed_today: int

    @property
    def progress(self) -> float:
        """Elapsed part of the current phase, 0.0 -> 1.0"""
        return 0.0 if self.duration <= 0 else min(1.0, max(0.0, 1 - self.remaining / self.duration))


class Pomodoro:
    def __init__(self, focus_s: float = 25 * 60, short_break_s: float = 5 * 60, long_break_s: float = 15 * 60,
                 rounds: int = 4, on_phase_change: Optional[Callable[[Phase, Phase], None]] = None,
                 clock: Callable[[], float] = time.monotonic, today: Callable[[], date] = date.today):
        self.durations = {Phase.FOCUS: focus_s, Phase.SHORT_BREAK: short_break_s, Phase.LONG_BREAK: long_break_s}
        self.rounds = rounds
        self.on_phase_change = on_phase_change
        self.clock = clock
        self.today = today

        self.lock = threading.Lock()
        self.phase = Phase.IDLE
        self.paused = False
        self.phase_end = 0.0  # clock() value at which the running phase ends
        self.paused_remaining = 0.0
        self.focus_done_in_cycle = 0
        self.completed_day = today()
        self.completed_today = 0

    def _remaining(self) -> float:
        if self.phase == Phase.IDLE:
            return 0.0
        if self.paused:
            return self.paused_remaining
        return max(0.0, self.phase_end - self.clock())

    def _enter(self, phase: Phase):
        self.phase = phase
        self.paused = False
        self.phase_end = self.clock() + self.durations.get(phase, 0)

    def _finish_phase(self, count_focus: bool) -> Phase:
        """Leave the current phase and start the next one, returns the new phase"""
        if self.phase == Phase.FOCUS:
            if count_focus:
                self._roll_day()
                self.completed_today += 1
            self.focus_done_in_cycle += 1
            if self.focus_done_in_cycle >= self.rounds:
                self.focus_done_in_cycle = 0
                self._enter(Phase.LONG_BREAK)
            else:
                self._enter(Phase.SHORT_BREAK)
        else:
            self._enter(Phase.FOCUS)
        return self.phase

    def _roll_day(self):
        if self.today() != self.completed_day:
            self.completed_day = self.today()
            self.completed_today = 0

    def _notify(self, old: Phase, new: Phase):
        # Called without the lock held: the callback may be slow (notification, sound)
        if self.on_phase_change is not None:
            self.on_phase_change(old, new)

    def start(self):
        with self.lock:
            if self.phase != Phase.IDLE:
                return
            self.focus_done_in_cycle = 0
            self._enter(Phase.FOCUS)

    def pause(self):
        with self.lock:
            if self.phase != Phase.IDLE and not self.paused:
                self.paused_remaining = self._remaining()
                self.paused = True

    def resume(self):
        with self.lock:
            if self.phase != Phase.IDLE and self.paused:
                self.phase_end = self.clock() + self.paused_remaining
                self.paused = False

    def skip(self):
        """End the current phase now. A skipped focus round does not count as a completed pomodoro."""
        with self.lock:
            if self.phase == Phase.IDLE:
                return
            old = self.phase
            new = self._finish_phase(count_focus=False)
        self._notify(old, new)

    def stop(self):
        with self.lock:
            self.phase = Phase.IDLE
            self.paused = False
            self.focus_done_in_cycle = 0

    def tick(self):
        """Advance to the next phase when the running one is over. Call it regularly (e.g. every frame)."""
        with self.lock:
            if self.phase == Phase.IDLE or self.paused or self._remaining() > 0:
                return
            old = self.phase
            new = self._finish_phase(count_focus=True)
        self._notify(old, new)

    def state(self) -> PomodoroState:
        with self.lock:
            self._roll_day()
            return PomodoroState(
                phase=self.phase,
                paused=self.paused,
                remaining=self._remaining(),
                duration=self.durations.get(self.phase, 0),
                round_in_cycle=min(self.focus_done_in_cycle + 1, self.rounds),
                rounds=self.rounds,
                completed_today=self.completed_today,
            )
