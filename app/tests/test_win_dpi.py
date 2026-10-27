"""Windows display scale: the window grows with the system DPI instead of being bitmap-stretched.

Offline checks need no window. The last one opens a hidden Tk window on Windows."""
import sys
import unittest
from pathlib import Path

from core.win_dpi import apply_tk, enable, read_dpi, scale_for_dpi, scale_px, tk_scaling_for_dpi

APP = Path(__file__).resolve().parent.parent


class DpiMath(unittest.TestCase):
    def test_100_percent_is_unchanged(self):
        self.assertEqual(scale_for_dpi(96), 1.0)
        self.assertEqual(scale_px(700, 1.0), 700)
        self.assertEqual(scale_px(860, 1), 860)

    def test_150_percent_is_the_2k_laptop_case(self):
        # 144 DPI is Windows at 150%, the usual scale on a 2K laptop.
        self.assertEqual(scale_for_dpi(144), 1.5)
        self.assertEqual(tk_scaling_for_dpi(144), 2.0)
        self.assertEqual(scale_px(700, 1.5), 1050)
        self.assertEqual(scale_px(860, 1.5), 1290)

    def test_125_and_200_percent(self):
        self.assertEqual(scale_for_dpi(120), 1.25)
        self.assertEqual(scale_px(700, 1.25), 875)
        self.assertEqual(scale_for_dpi(192), 2.0)
        self.assertEqual(scale_px(8, 2), 16)

    def test_junk_and_tiny_dpi_do_not_shrink_the_window(self):
        self.assertEqual(scale_for_dpi(None), 1.0)
        self.assertEqual(scale_for_dpi("nope"), 1.0)
        self.assertEqual(scale_for_dpi(0), 1.0)
        self.assertEqual(scale_for_dpi(72), 1.0)
        self.assertEqual(scale_px("x", 1.5), 1)


class Launchers(unittest.TestCase):
    def test_windows_are_not_forced_dpi_unaware(self):
        for name in ("gui_main.py", "run_engine.py"):
            text = (APP / name).read_text(encoding="utf-8")
            self.assertIn("from core.win_dpi import enable", text, name)
            self.assertIn("enable()", text, name)
            self.assertNotIn("SetProcessDpiAwareness(0)", text, name)

    def test_embedded_video_uses_the_same_pixels_as_the_window(self):
        player = (APP / "edgeware_core" / "src" / "features" / "video_player.py").read_text(encoding="utf-8")
        child = (APP / "edgeware_core" / "src" / "features" / "mpv_subprocess.py").read_text(encoding="utf-8")
        self.assertIn('"hidpi-window-scale": "no"', player)
        self.assertIn('"hidpi-window-scale": "no"', child)
        self.assertLess(child.index("SetProcessDpiAwarenessContext"), child.index("import mpv"))


@unittest.skipUnless(sys.platform == "win32", "Windows DPI")
class LiveDpi(unittest.TestCase):
    def test_tk_follows_the_system_dpi(self):
        enable()
        dpi = read_dpi()
        import tkinter as tk
        root = tk.Tk()
        try:
            root.withdraw()
            scale = apply_tk(root, dpi)
            scaling = float(root.tk.call("tk", "scaling"))
        finally:
            root.destroy()
        self.assertAlmostEqual(scale, scale_for_dpi(dpi), places=2)
        self.assertAlmostEqual(scaling, tk_scaling_for_dpi(dpi), places=2)


if __name__ == "__main__":
    unittest.main()
