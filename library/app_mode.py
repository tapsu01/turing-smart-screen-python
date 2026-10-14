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

# Switching between the programs that drive the display (system monitor, fun mode) from their tray menus.
# The chosen mode is remembered in config.yaml (app: MODE) and started by the macOS app on next launch.

import subprocess
import sys

import ruamel.yaml

from library.log import logger
from library.paths import MAIN_DIRECTORY, config_file

MODE_SCRIPTS = {
    "monitor": "main.py",
    "fun": "fun.py",
}
DEFAULT_MODE = "monitor"


def mode_from_config(config_data: dict) -> str:
    mode = (config_data.get("app") or {}).get("MODE", DEFAULT_MODE)
    return mode if mode in MODE_SCRIPTS else DEFAULT_MODE


def save_mode(mode: str):
    # Round-trip load/dump like configure.py, so that comments and other settings are kept
    path = config_file()
    with open(path, "rt", encoding="utf8") as stream:
        data, _, _ = ruamel.yaml.util.load_yaml_guess_indent(stream)
    data.setdefault("app", {})["MODE"] = mode
    with open(path, "w", encoding="utf-8") as stream:
        ruamel.yaml.YAML().dump(data, stream)


def launch_script(script: str):
    """Start another program of this project in a new process.
    From source code sys.executable is Python; in the macOS app it is the app launcher, which runs the script."""
    logger.info(f"Starting {script}")
    subprocess.Popen([sys.executable, str(MAIN_DIRECTORY / script)])


def switch_to(mode: str):
    """Remember the mode and start its program. The caller must then stop itself to free the display:
    the new program retries to open the display for a few seconds."""
    save_mode(mode)
    launch_script(MODE_SCRIPTS[mode])
