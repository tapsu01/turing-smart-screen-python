import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from library import paths


class TestPaths(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.program_dir = Path(self.tmp.name) / "program"
        self.home = Path(self.tmp.name) / "home"
        self.program_dir.mkdir()
        self.home.mkdir()
        (self.program_dir / "config.yaml").write_text("display:\n  BRIGHTNESS: 20\n")
        patches = [
            mock.patch.object(paths, "MAIN_DIRECTORY", self.program_dir),
            mock.patch.object(paths.Path, "home", return_value=self.home),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_source_checkout_uses_program_directory(self):
        self.assertEqual(paths.config_file(), self.program_dir / "config.yaml")

    def test_macos_app_copies_default_config_to_user_directory_once(self):
        with mock.patch.object(sys, "frozen", True, create=True), \
                mock.patch.object(paths.platform, "system", return_value="Darwin"):
            config = paths.config_file()
            self.assertEqual(config, self.home / "Library/Application Support/Turing Screen/config.yaml")
            self.assertEqual(config.read_text(), "display:\n  BRIGHTNESS: 20\n")

            # User changes are kept: the bundled default never overwrites them
            config.write_text("display:\n  BRIGHTNESS: 50\n")
            self.assertEqual(paths.config_file().read_text(), "display:\n  BRIGHTNESS: 50\n")

    def test_frozen_on_other_platforms_keeps_program_directory(self):
        with mock.patch.object(sys, "frozen", True, create=True), \
                mock.patch.object(paths.platform, "system", return_value="Windows"):
            self.assertEqual(paths.config_file(), self.program_dir / "config.yaml")


if __name__ == '__main__':
    unittest.main()
