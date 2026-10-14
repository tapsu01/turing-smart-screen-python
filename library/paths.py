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

# Where the program finds its resources and where it writes user data.
# - From source code, and in Windows/Linux builds: everything stays in the program directory (unchanged behavior)
# - In the macOS app bundle: the bundle is read-only, so config.yaml and logs live in ~/Library/Application Support

import platform
import shutil
import sys
from pathlib import Path

APP_NAME = "Turing Screen"

# Program directory: source checkout, or bundled resources of a frozen build (res/, config.yaml defaults...)
MAIN_DIRECTORY = Path(__file__).parent.parent.resolve()


def is_macos_app() -> bool:
    return bool(getattr(sys, "frozen", False)) and platform.system() == "Darwin"


def user_data_dir() -> Path:
    if not is_macos_app():
        return MAIN_DIRECTORY
    path = Path.home() / "Library" / "Application Support" / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_file() -> Path:
    """config.yaml to read and write. In the macOS app it starts as a copy of the bundled default."""
    path = user_data_dir() / "config.yaml"
    if not path.exists():
        shutil.copyfile(MAIN_DIRECTORY / "config.yaml", path)
    return path
