"""Autoedgeware-specific (not shared): the engine launch keeps the window-safe half of quiet()."""
import unittest
from unittest import mock

from core import engine_launch


class EngineLaunch(unittest.TestCase):
    def test_hide_window_part_is_dropped_but_no_console_is_kept(self):
        fake = {"creationflags": 0x08000000, "startupinfo": object()}
        with mock.patch.object(engine_launch, "quiet", return_value=fake):
            kw = engine_launch.engine_launch_kwargs()
        self.assertEqual(kw, {"creationflags": 0x08000000})
        self.assertIn("startupinfo", fake)             # the shared function's result isn't modified

    def test_start_engine_passes_script_cwd_and_flags(self):
        with mock.patch.object(engine_launch.subprocess, "Popen") as popen, \
                mock.patch.object(engine_launch, "quiet", return_value={"creationflags": 1, "startupinfo": 2}):
            engine_launch.start_engine("run_engine.py", "C:/app")
        args, kwargs = popen.call_args
        self.assertEqual(args[0][1], "run_engine.py")
        self.assertEqual(kwargs, {"cwd": "C:/app", "creationflags": 1})


if __name__ == "__main__":
    unittest.main()
