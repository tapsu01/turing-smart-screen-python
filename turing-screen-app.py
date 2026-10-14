#!/usr/bin/env python
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

# Entry point of the macOS app bundle (Turing Screen.app, built with turing-screen-macos.spec).
# - Without argument: starts the mode saved in config.yaml (app: MODE), system monitor or fun mode
# - With a "<script>.py" argument: runs that script. The programs start each other with
#   [sys.executable, "<script>.py"] (Configure, Save and run, Edit theme, mode switch): in the app sys.executable is
#   this launcher, so all those buttons keep working without change.
# It also works from source code: python turing-screen-app.py

import os
import runpy
import sys
from pathlib import Path

from library.paths import MAIN_DIRECTORY, user_data_dir


def main():
    # Before anything imports library.log: it writes log.log in the current directory,
    # and an app started from Finder has "/" as current directory
    os.chdir(user_data_dir())

    if len(sys.argv) > 1 and sys.argv[1].endswith(".py"):
        script = Path(sys.argv[1])
        args = sys.argv[2:]
    else:
        from library.app_mode import MODE_SCRIPTS, mode_from_config
        from library.config import CONFIG_DATA

        script = MAIN_DIRECTORY / MODE_SCRIPTS[mode_from_config(CONFIG_DATA)]
        args = sys.argv[1:]

    # The script sees itself as the running program, with its own arguments
    sys.argv = [str(script), *args]
    runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()
