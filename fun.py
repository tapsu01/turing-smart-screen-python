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

# Fun mode: a pixel cat running with the CPU load, an analog clock with Vietnamese lunar calendar and a Pomodoro timer.
# Standalone program like simple-program.py: stop main.py first, only one program can use the display at a time.
# Controlled from its tray (menu bar) icon. Settings: "fun" section of config.yaml.

from library.pythoncheck import check_python_version

check_python_version()

import argparse
import dataclasses
import platform
import signal
import sys
import threading
from pathlib import Path

from PIL import Image

from library import config
from library.app_mode import launch_script, switch_to
from library.fun.app import FunApp, FunSettings, Mode
from library.fun.notify import notify_phase_change
from library.fun.costume import COSTUME_LABELS
from library.fun.pet import Action
from library.fun.pomodoro import Phase, Pomodoro
from library.lcd.lcd_comm import Orientation
from library.lcd.lcd_comm_rev_a_usb import create_lcd_rev_a
from library.log import logger
from library.paths import user_data_dir

try:
    import pystray
except Exception:
    # Without tray icon the program still runs, but the Pomodoro cannot be controlled
    pystray = None

MAIN_DIRECTORY = Path(__file__).resolve().parent

# Short durations to try the Pomodoro transitions without waiting 25 minutes
TEST_POMODORO = dict(pomodoro_focus_min=20 / 60, pomodoro_short_break_min=10 / 60, pomodoro_long_break_min=15 / 60,
                     pomodoro_rounds=2)


def build_tray_menu(app: FunApp, pomodoro: Pomodoro, on_monitor, on_configure, on_exit) -> "pystray.Menu":
    def phase_is(*phases):
        return lambda item: pomodoro.state().phase in phases

    def running(paused: bool):
        return lambda item: pomodoro.state().phase != Phase.IDLE and pomodoro.state().paused == paused

    def action(fn):
        def run(icon, item):
            fn()
            icon.update_menu()

        return run

    def set_mode(mode: Mode):
        def run(icon, item):
            app.mode = mode

        return run

    def mode_is(mode: Mode):
        return lambda item: app.mode == mode

    def pet_option(name: str, text: str, target=None) -> "pystray.MenuItem":
        def owner():
            return app.pet if target is None else target

        def run(icon, item):
            setattr(owner(), name, not getattr(owner(), name))

        return pystray.MenuItem(text, run, checked=lambda item: getattr(owner(), name))

    def pet_action(pet_action_: Action, variant: bool = False):
        def run(icon, item):
            app.pet.request(pet_action_, variant)

        return run

    def costume_item(text: str, costume) -> "pystray.MenuItem":
        def run(icon, item):
            app.costume_choice = costume

        return pystray.MenuItem(text, run, checked=lambda item: app.costume_choice == costume, radio=True)

    not_idle = phase_is(Phase.FOCUS, Phase.SHORT_BREAK, Phase.LONG_BREAK)
    return pystray.Menu(
        pystray.MenuItem("Bắt đầu Pomodoro", action(pomodoro.start), visible=phase_is(Phase.IDLE)),
        pystray.MenuItem("Tạm dừng", action(pomodoro.pause), visible=running(paused=False)),
        pystray.MenuItem("Tiếp tục", action(pomodoro.resume), visible=running(paused=True)),
        pystray.MenuItem("Bỏ qua lượt này", action(pomodoro.skip), visible=not_idle),
        pystray.MenuItem("Dừng Pomodoro", action(pomodoro.stop), visible=not_idle),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Trang", pystray.Menu(
            pystray.MenuItem("Tự động", set_mode(Mode.AUTO), checked=mode_is(Mode.AUTO), radio=True),
            pystray.MenuItem("Đồng hồ", set_mode(Mode.CLOCK), checked=mode_is(Mode.CLOCK), radio=True),
            pystray.MenuItem("Pomodoro", set_mode(Mode.POMODORO), checked=mode_is(Mode.POMODORO), radio=True),
        )),
        pystray.MenuItem("Mèo", pystray.Menu(
            pystray.MenuItem("Cho ăn", lambda icon, item: app.feed_pet(), enabled=lambda item: app.care_enabled),
            pystray.MenuItem("Vuốt ve", lambda icon, item: app.pet_cat(), enabled=lambda item: app.care_enabled),
            pet_option("force_sleep", "Cho mèo đi ngủ"),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Giật mình", pet_action(Action.STARTLE)),
            pystray.MenuItem("Ngáp, vươn vai", pet_action(Action.STRETCH)),
            pystray.MenuItem("Ăn mừng", pet_action(Action.CELEBRATE)),
            pystray.MenuItem("Ăn mừng to", pet_action(Action.CELEBRATE, variant=True)),
            pystray.MenuItem("Trang phục", pystray.Menu(
                costume_item("Theo ngày", None),
                *(costume_item(label, costume) for costume, label in COSTUME_LABELS.items()),
            )),
            pystray.Menu.SEPARATOR,
            pet_option("startle_enabled", "Tự giật mình khi CPU vọt lên"),
            pet_option("stretch_enabled", "Ngáp, vươn vai khi thức dậy"),
            pet_option("celebrate_enabled", "Ăn mừng khi xong Pomodoro"),
            pet_option("care_enabled", "Nuôi mèo (đói, buồn)", target=app),
        )),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Theo dõi hệ thống", on_monitor),
        pystray.MenuItem("Cấu hình…", on_configure),
        pystray.MenuItem("Thoát", on_exit),
    )


def main():
    parser = argparse.ArgumentParser(description="Turing smart screen - fun mode")
    parser.add_argument("--pomodoro-test", action="store_true",
                        help="Use very short Pomodoro durations (20s / 10s / 15s, 2 rounds) to try transitions")
    args = parser.parse_args()

    display_config = config.CONFIG_DATA["display"]
    if display_config["REVISION"] != "A":
        logger.error("fun.py currently supports only revision A displays (Turing Smart Screen 3.5\")")
        sys.exit(1)

    settings = FunSettings.from_config(config.CONFIG_DATA.get("fun") or {})
    if args.pomodoro_test:
        settings = dataclasses.replace(settings, **TEST_POMODORO)

    # Default actions: the process ends right away. Python-level handlers would never run while the macOS tray
    # event loop (native code) owns the main thread.
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    lcd = create_lcd_rev_a(com_port=config.CONFIG_DATA["config"]["COM_PORT"],
                           raw_usb=display_config.get("MACOS_RAW_USB", True))
    if display_config.get("RESET_ON_STARTUP", True):
        lcd.Reset()
    lcd.InitializeComm()
    lcd.ScreenOn()
    lcd.SetBrightness(display_config["BRIGHTNESS"])
    lcd.SetOrientation(Orientation.REVERSE_LANDSCAPE if display_config.get("DISPLAY_REVERSE", False)
                       else Orientation.LANDSCAPE)

    pomodoro = Pomodoro(focus_s=settings.pomodoro_focus_min * 60,
                        short_break_s=settings.pomodoro_short_break_min * 60,
                        long_break_s=settings.pomodoro_long_break_min * 60,
                        rounds=settings.pomodoro_rounds,
                        on_phase_change=notify_phase_change)
    app = FunApp(lcd, settings, pomodoro, care_path=user_data_dir() / "pet_state.json")
    render_thread = threading.Thread(target=app.run, name="fun-render", daemon=True)
    render_thread.start()
    logger.info("Fun mode started")

    def stop(icon=None, item=None):
        logger.info("Fun mode stopping")
        app.stop()
        render_thread.join(timeout=3)
        lcd.ScreenOff()
        lcd.closeSerial()
        if icon is not None:
            icon.stop()

    def switch_to_monitor(icon, item):
        # Start the system monitor first: it retries to open the display until this program has released it
        switch_to("monitor")
        stop(icon)

    def open_configure(icon, item):
        # Same as the system monitor: the configuration window needs the display to be free for "Save and run"
        launch_script("configure.py")
        stop(icon)

    if pystray is None:
        logger.warning("Tray icon not available: Pomodoro cannot be controlled, stop with Ctrl+C")
        render_thread.join()
        return

    tray_icon = pystray.Icon(name="Turing Fun Mode", title="Turing Fun Mode",
                             icon=Image.open(MAIN_DIRECTORY / "res/icons/monitor-icon-17865/64.png"))
    tray_icon.menu = build_tray_menu(app, pomodoro, on_monitor=switch_to_monitor, on_configure=open_configure,
                                     on_exit=stop)
    if platform.system() == "Darwin":
        from library.tray import hide_macos_dock_icon

        hide_macos_dock_icon()
    # Blocking: on macOS the tray event loop must own the main thread
    tray_icon.run()


if __name__ == "__main__":
    main()
