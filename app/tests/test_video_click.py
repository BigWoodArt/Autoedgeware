"""'Clicking a fullscreen video closes it' setting, offline: python -m unittest tests.test_video_click
(The popup classes need Tk and mpv, so the wiring is checked in the source.)"""
import os
import unittest

from ae_settings.settings import DEFAULTS

BASE = os.path.join(os.path.dirname(__file__), "..")


def read(*parts):
    with open(os.path.join(BASE, *parts), encoding="utf-8") as f:
        return f.read()


class FullscreenClick(unittest.TestCase):
    def test_default_is_the_old_behaviour(self):
        self.assertIs(DEFAULTS["fullscreen_video_click_close"], True)
        self.assertNotIn("video_click_close", DEFAULTS)

    def test_only_fullscreen_videos_lose_the_click(self):
        src = read("ae_video_popup.py")
        self.assertIn("not CONFIG[\"click_close\"]:\n            return", src)
        self.assertIn("super().try_button()", src)                     # everything else keeps its click / Close button
        self.assertIn("click_close=bool(click_close)", src)
        # the normal popup timeout is untouched for small popups
        self.assertIn("if not self._ae_full:", src)
        self.assertNotIn("margin=0.7", src)

    def test_engine_and_settings_screen_pass_it_on(self):
        self.assertIn('click_close=ae_settings.get("fullscreen_video_click_close", True)', read("run_engine.py"))
        gui = read("gui", "app.py")
        self.assertIn('self.settings["fullscreen_video_click_close"] = bool(self.video_click_var.get())', gui)
        self.assertIn("Clicking a fullscreen video closes it", gui)


if __name__ == "__main__":
    unittest.main()
