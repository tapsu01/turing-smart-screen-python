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

# Tray icon helpers shared by the programs that show a pystray icon (main.py, fun.py)


def hide_macos_dock_icon():
    """Hide the Python Launcher icon from macOS dock: the program only lives in the menu bar"""
    from AppKit import NSBundle, NSApp, NSApplicationActivationPolicyProhibited

    info = NSBundle.mainBundle().infoDictionary()
    info["LSUIElement"] = "1"
    NSApp.setActivationPolicy_(NSApplicationActivationPolicyProhibited)
