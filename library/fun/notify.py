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

# Pomodoro phase change alerts. macOS: system notification + sound with built-in tools (osascript, afplay).
# Other platforms: log only.

import platform
import subprocess

from library.fun.pomodoro import Phase
from library.log import logger

MACOS_SOUND = "/System/Library/Sounds/Glass.aiff"

PHASE_MESSAGES = {
    Phase.FOCUS: "Hết giờ nghỉ, bắt đầu tập trung nào!",
    Phase.SHORT_BREAK: "Xong một lượt 🍅 Nghỉ ngắn chút nhé.",
    Phase.LONG_BREAK: "Xong cả chu kỳ 🎉 Nghỉ dài thôi!",
}

# Text is passed as arguments, not inside the script, so quotes in messages cannot break the AppleScript
_NOTIFICATION_SCRIPT = ["-e", "on run argv", "-e", "display notification (item 2 of argv) with title (item 1 of argv)",
                        "-e", "end run"]


def notify(title: str, message: str):
    logger.info(f"{title}: {message}")
    if platform.system() != "Darwin":
        return
    try:
        # Popen: do not block the caller while the sound plays
        subprocess.Popen(["osascript", *_NOTIFICATION_SCRIPT, title, message],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.Popen(["afplay", MACOS_SOUND], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as e:
        logger.warning(f"Cannot send notification: {e}")


def notify_phase_change(old: Phase, new: Phase):
    message = PHASE_MESSAGES.get(new)
    if message:
        notify("Pomodoro", message)
