import tempfile
import unittest
from pathlib import Path
from unittest import mock

from library import app_mode

CONFIG = """display:
  # Display Brightness
  BRIGHTNESS: 20

app:
  # Mode started by the macOS app
  MODE: monitor
"""


class TestAppMode(unittest.TestCase):
    def test_mode_from_config(self):
        self.assertEqual(app_mode.mode_from_config({"app": {"MODE": "fun"}}), "fun")
        self.assertEqual(app_mode.mode_from_config({}), "monitor")
        self.assertEqual(app_mode.mode_from_config({"app": None}), "monitor")
        self.assertEqual(app_mode.mode_from_config({"app": {"MODE": "unknown"}}), "monitor")

    def test_save_mode_keeps_comments_and_other_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            path.write_text(CONFIG)
            with mock.patch.object(app_mode, "config_file", return_value=path):
                app_mode.save_mode("fun")
            self.assertEqual(path.read_text(), CONFIG.replace("MODE: monitor", "MODE: fun"))

    def test_switch_to_saves_mode_then_starts_its_program(self):
        with mock.patch.object(app_mode, "save_mode") as save_mode, \
                mock.patch.object(app_mode.subprocess, "Popen") as popen:
            app_mode.switch_to("fun")
        save_mode.assert_called_once_with("fun")
        self.assertEqual(Path(popen.call_args.args[0][1]).name, "fun.py")


if __name__ == '__main__':
    unittest.main()
