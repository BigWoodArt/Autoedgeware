"""Hero mode is hooked in everywhere it must be (source checks; no Tk). Also the click sound file."""
import os
import re
import tempfile
import unittest
import wave
from pathlib import Path

from ae_settings.settings import DEFAULTS
from core import engine_control, hero_assets

APP = Path(__file__).resolve().parent.parent


def read(rel):
    return (APP / rel).read_text(encoding="utf-8")


class Hold(unittest.TestCase):
    def tearDown(self):
        engine_control.set_hold(False)

    def test_hold_blocks_new_popups_only(self):
        chance = engine_control.gated(lambda: 60)
        self.assertEqual(chance(), 60)
        engine_control.set_hold(True)
        self.assertEqual(chance(), 0)
        engine_control.set_hold(False)
        self.assertEqual(chance(), 60)

    def test_stop_takes_the_bar_down(self):
        calls = []

        class Hero:
            def teardown(self):
                calls.append("teardown")

            def shutdown(self):
                calls.append("shutdown")

        class Pop:
            audio_players, popups = [], []

        state = Pop()
        state.ae_hero = Hero()
        engine_control.stop_popups(state)
        engine_control.resume_popups(state)
        engine_control.stop_hero(state, final=True)
        self.assertEqual(calls, ["teardown", "shutdown"])


class Wiring(unittest.TestCase):
    def test_engine_hooks(self):
        src = read("run_engine.py")
        self.assertIn("HeroController(", src)
        self.assertIn("state.ae_hero = hero", src)
        self.assertIn('_safe("hero mode", hero.start)', src)
        self.assertIn("hero.next_popup_delay_ms(settings.delay)", src)
        # no speed-up and no hibernating while Hero mode sets the pace
        self.assertRegex(src, r"def escalate_corruption\(\):\s+if hero\.active:")
        self.assertRegex(src, r"def enter_hibernate\(\):\s+if hero\.active:")
        # every way the program can end takes the bar down
        self.assertGreaterEqual(src.count("stop_hero(state, final=True)"), 3)

    def test_window_close_and_toggle(self):
        src = read("gui/app.py")
        self.assertIn("engine_control.stop_hero(self._live_state, final=True)", src)
        self.assertIn("_on_hero_toggle", src)
        self.assertIn('self.settings["hero_mode"]', src)

    def test_hypno_can_be_steered(self):
        src = read("hypno.py")
        self.assertIn("level_source", src)
        self.assertIn("def apply_level", src)

    def test_defaults_exist(self):
        for key in ("hero_mode", "hero_text", "hero_click_volume", "hero_round_seconds", "hero_rounds_to_full", "hero_frenzy_percent",
                    "hero_hold_seconds", "hero_bpm_min", "hero_bpm_max"):
            self.assertIn(key, DEFAULTS)
        self.assertFalse(DEFAULTS["hero_mode"])

    def test_no_input_is_recorded(self):
        src = read("hero.py")
        for word in ("bind(", "<Key", "<Button", "pynput", "keyboard"):
            self.assertNotIn(word, src)


class Click(unittest.TestCase):
    def test_click_file_and_volume(self):
        with tempfile.TemporaryDirectory() as d:
            quiet = hero_assets.make_click(os.path.join(d, "q.wav"), 10)
            loud = hero_assets.make_click(os.path.join(d, "l.wav"), 100)
            silent = hero_assets.make_click(os.path.join(d, "s.wav"), 0)
            peaks = []
            for path in (quiet, loud, silent):
                with wave.open(path) as w:
                    self.assertEqual((w.getnchannels(), w.getsampwidth()), (1, 2))
                    self.assertLess(w.getnframes() / w.getframerate(), 0.1)
                    raw = w.readframes(w.getnframes())
                peaks.append(max(abs(int.from_bytes(raw[i:i + 2], "little", signed=True)) for i in range(0, len(raw), 2)))
            self.assertLess(peaks[0], peaks[1])
            self.assertEqual(peaks[2], 0)


if __name__ == "__main__":
    unittest.main()
