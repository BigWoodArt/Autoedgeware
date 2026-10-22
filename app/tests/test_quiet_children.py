"""Autoedgeware-specific (not shared): child programs default to no console window on Windows."""
import subprocess
import unittest
from unittest import mock

from core import quiet_children


class QuietChildren(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.recorder = lambda s, *a, **k: self.calls.append((a, k))
        quiet_children._installed = False

    def run_installed(self, platform, *args, **kwargs):
        with mock.patch.object(subprocess.Popen, "__init__", self.recorder):
            quiet_children.install(platform)
            subprocess.Popen(*args, **kwargs)

    def test_flag_added_and_nothing_else_touched(self):
        self.run_installed("win32", ["ffprobe", "-version"], stdout=-1)
        (a, k), = self.calls
        self.assertEqual(k, {"stdout": -1, "creationflags": 0x08000000})   # no startupinfo / hide-window part

    def test_existing_flags_are_kept(self):
        self.run_installed("win32", ["x"], creationflags=0x200)
        self.assertEqual(self.calls[0][1]["creationflags"], 0x200 | 0x08000000)

    def test_positional_creationflags_call_is_left_alone(self):
        self.run_installed("win32", *(["x"] + [None] * 12 + [0x200]))
        self.assertNotIn("creationflags", self.calls[0][1])

    def test_not_windows_changes_nothing(self):
        before = subprocess.Popen.__init__
        quiet_children.install("linux")
        self.assertIs(subprocess.Popen.__init__, before)

    def test_installing_twice_wraps_once(self):
        with mock.patch.object(subprocess.Popen, "__init__", self.recorder):
            quiet_children.install("win32")
            quiet_children.install("win32")
            subprocess.Popen(["x"])
        self.assertEqual(len(self.calls), 1)


if __name__ == "__main__":
    unittest.main()
