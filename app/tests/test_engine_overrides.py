"""Autoedgeware-specific (not shared): settings the engine always forces."""
import os
import unittest

from core.engine_overrides import apply_forced, click_close_blocked, clamp_popup_pos, POPUP_BEHAVIOR
from gui.theme import INTENSITY_PRESETS

BASE = os.path.join(os.path.dirname(__file__), "..")


def _read(*parts):
    with open(os.path.join(BASE, *parts), encoding="utf-8") as f:
        return f.read()


class Forced(unittest.TestCase):
    def test_every_preset_keeps_its_timed_popups(self):
        for name, bundle in INTENSITY_PRESETS:
            with self.subTest(preset=name):
                self.assertEqual(bundle["mitosisMode"], 0)           # the preset data itself is clean
                cfg = apply_forced(dict(bundle), {})
                self.assertEqual(cfg["mitosisMode"], 0)              # mitosis would switch the timer off
                self.assertGreater(cfg["popupMod"], 0)
                self.assertGreater(cfg["delay"], 0)

    def test_an_old_saved_bundle_with_mitosis_on_is_still_overridden(self):
        cfg = apply_forced({"mitosisMode": 1, "mitosisStrength": 3}, {})
        self.assertEqual((cfg["mitosisMode"], cfg["mitosisStrength"]), (0, 0))

    def test_fixed_values(self):
        cfg = apply_forced({}, {})
        self.assertEqual((cfg["buttonless"], cfg["maxAudio"], cfg["audioVolume"], cfg["videoVolume"],
                          cfg["booru_download"]), (True, 1, 50, 20, 0))

    def test_popup_timeout_follows_the_option(self):
        on = apply_forced({}, {"popup_timeout_enabled": True, "popup_timeout_seconds": 7})
        self.assertEqual((on["timeoutPopups"], on["popupTimeout"]), (1, 7))
        self.assertEqual(apply_forced({"timeoutPopups": 1}, {})["timeoutPopups"], 0)


if __name__ == "__main__":
    unittest.main()


class SoundFromSettings(unittest.TestCase):
    def test_user_values_are_used_and_clamped(self):
        cfg = apply_forced({}, {"max_audio": 3, "audio_volume": 80, "video_volume": 5})
        self.assertEqual((cfg["maxAudio"], cfg["audioVolume"], cfg["videoVolume"]), (3, 80, 5))
        cfg = apply_forced({}, {"max_audio": 99, "audio_volume": 500, "video_volume": -4})
        self.assertEqual((cfg["maxAudio"], cfg["audioVolume"], cfg["videoVolume"]), (10, 100, 0))
        cfg = apply_forced({}, {"max_audio": "x"})
        self.assertEqual(cfg["maxAudio"], 1)


class StaleMoving(unittest.TestCase):
    def test_old_saved_bundle_cannot_make_popups_move(self):
        from core.engine_overrides import effective_cfg
        stale = dict(INTENSITY_PRESETS[3][1], movingChance=5, movingSpeed=2)       # saved by an older version
        cfg = effective_cfg({"edgeware_cfg_name": INTENSITY_PRESETS[3][0], "edgeware_cfg": stale}, INTENSITY_PRESETS)
        self.assertEqual(cfg["movingChance"], 0)
        custom = effective_cfg({"edgeware_cfg_name": "Custom", "edgeware_cfg": {"delay": 2000}}, INTENSITY_PRESETS)
        self.assertEqual(custom["movingChance"], 0)
        self.assertEqual(effective_cfg({"edgeware_cfg_name": "Custom", "edgeware_cfg": {"movingChance": 30}},
                                       INTENSITY_PRESETS)["movingChance"], 30)       # a Custom value is kept


class PopupBehavior(unittest.TestCase):
    def test_timer_only_needs_timeout(self):
        apply_forced({}, {"popup_close_by_timer_only": True, "popup_drag_right_button": True})
        self.assertEqual((POPUP_BEHAVIOR["timer_only"], POPUP_BEHAVIOR["rmb_drag"]), (False, True))
        apply_forced({}, {"popup_timeout_enabled": True, "popup_timeout_seconds": 7,
                          "popup_close_by_timer_only": True, "popup_drag_right_button": False})
        self.assertEqual((POPUP_BEHAVIOR["timer_only"], POPUP_BEHAVIOR["rmb_drag"]), (True, False))

    def test_click_close_skips_fullscreen(self):
        apply_forced({}, {"popup_timeout_enabled": True, "popup_close_by_timer_only": True})
        self.assertTrue(click_close_blocked(type("P", (), {})()))
        self.assertFalse(click_close_blocked(type("P", (), {"_ae_full": True})()))

    def test_wiring(self):
        src = _read("core", "engine_overrides.py")
        self.assertIn("Popup.compute_geometry = compute_geometry", src)
        self.assertIn("clamp_popup_pos", src)
        self.assertIn("install_popup_behavior()", _read("run_engine.py"))
        gui = _read("gui", "app.py")
        self.assertIn("popup_close_by_timer_only", gui)
        self.assertIn("popup_drag_right_button", gui)
        settings = _read("ae_settings", "settings.py")
        self.assertIn('"popup_close_by_timer_only": False', settings)
        self.assertIn('"popup_drag_right_button": False', settings)

    def test_negative_tk_geometry_breaks_edgeware_split(self):
        # Tk reports a window at x=-10 as "800x600-10+20". Edgeware then does
        # map(int, geometry().replace("x", "+").split("+")) and the next popup dies.
        parts = "800x600-10+20".replace("x", "+").split("+")
        with self.assertRaises(ValueError):
            list(map(int, parts))

    def test_drag_stays_on_the_monitor(self):
        mon = type("M", (), {"x": 0, "y": 0, "width": 1920, "height": 1080})()
        self.assertEqual(clamp_popup_pos(-40, -10, 400, 300, mon), (0, 0))
        self.assertEqual(clamp_popup_pos(3000, 2000, 400, 300, mon), (1520, 780))
        left = type("M", (), {"x": -1920, "y": 0, "width": 1920, "height": 1080})()
        self.assertEqual(clamp_popup_pos(-4000, 10, 400, 300, left), (-1920, 10))
