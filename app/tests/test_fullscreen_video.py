"""Autoedgeware-only: which videos go fullscreen."""
import unittest
from pathlib import Path

from core.fullscreen_video import is_wide, play_seconds, should_fullscreen

ROOT = Path(__file__).resolve().parent.parent


class Rng:
    def __init__(self, value): self.value = value
    def random(self): return self.value


class Rules(unittest.TestCase):
    def test_wide_shapes(self):
        self.assertTrue(is_wide(1920, 1080))
        self.assertTrue(is_wide(1920, 1200))       # 16:10
        self.assertTrue(is_wide(2560, 1080))       # ultrawide
        self.assertFalse(is_wide(1080, 1920))      # portrait
        self.assertFalse(is_wide(1000, 1000))
        self.assertFalse(is_wide(1440, 1080))      # 4:3
        self.assertFalse(is_wide(0, 0))

    def test_chance(self):
        self.assertTrue(should_fullscreen(2560, 1440, 15, False, Rng(0.10)))
        self.assertFalse(should_fullscreen(2560, 1440, 15, False, Rng(0.20)))
        self.assertFalse(should_fullscreen(2560, 1440, 0, False, Rng(0.0)))
        self.assertTrue(should_fullscreen(2560, 1440, 100, False, Rng(0.999)))

    def test_only_one_at_a_time_and_only_wide(self):
        self.assertFalse(should_fullscreen(2560, 1440, 100, True, Rng(0.0)))
        self.assertFalse(should_fullscreen(1080, 1920, 100, False, Rng(0.0)))


class Length(unittest.TestCase):
    def test_plays_whole_video(self):
        self.assertEqual(play_seconds("60.5", 600), 62.5)
        self.assertEqual(play_seconds(30, 600), 32)

    def test_capped_and_unknown(self):
        self.assertEqual(play_seconds("5000", 600), 600)
        self.assertEqual(play_seconds(None, 600), 600)
        self.assertEqual(play_seconds("N/A", 600), 600)
        self.assertEqual(play_seconds("0", 600), 600)


class Wiring(unittest.TestCase):
    def test_normal_popup_timer_does_not_apply(self):
        text = (ROOT / "ae_video_popup.py").read_text(encoding="utf-8")
        self.assertRegex(text, r"def try_timeout\(self\)")
        self.assertIn("play_seconds(", text)

    def test_engine_uses_the_fullscreen_capable_popup(self):
        text = (ROOT / "run_engine.py").read_text(encoding="utf-8")
        self.assertIn("AEVideoPopup(root, settings, pack, state)", text)
        self.assertNotIn("lambda: VideoPopup(root", text)

    def test_popup_closes_through_the_normal_path_so_panic_and_stop_reach_it(self):
        text = (ROOT / "ae_video_popup.py").read_text(encoding="utf-8")
        self.assertIn("class AEVideoPopup(VideoPopup)", text)     # subclass => registered in state.popups
        self.assertIn("_fullscreen_open = False", text)           # flag cleared on close
        self.assertIn("super().close()", text)


    def test_low_quality_stays_a_popup(self):
        self.assertFalse(should_fullscreen(1920, 1080, 100, False, Rng(0.0)))
        self.assertFalse(should_fullscreen(1280, 720, 100, False, Rng(0.0)))
        self.assertTrue(should_fullscreen(2560, 1440, 100, False, Rng(0.0)))
        self.assertTrue(should_fullscreen(1920, 1080, 100, False, Rng(0.0), min_height=720))


if __name__ == "__main__":
    unittest.main()
