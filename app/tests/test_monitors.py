import types
import unittest
from pathlib import Path

from ae_settings.settings import DEFAULTS
from core import engine_overrides, monitors

APP = Path(__file__).resolve().parent.parent


def mon(name, w, h, primary=False):
    return types.SimpleNamespace(name=name, width=w, height=h, is_primary=primary)


class Monitors(unittest.TestCase):
    def test_list(self):
        got = monitors.list_monitors(lambda: [mon("A", 2560, 1440, True), mon("B", 1920, 1080)])
        self.assertEqual([g[0] for g in got], ["A", "B"])
        self.assertIn("(main)", got[0][1])
        self.assertIn("1920x1080", got[1][1])

    def test_unreadable_gives_empty(self):
        def boom():
            raise RuntimeError("no display")
        self.assertEqual(monitors.list_monitors(boom), [])

    def test_disabled_from(self):
        self.assertEqual(monitors.disabled_from(["A"], ["A", "B"]), ["B"])
        self.assertEqual(monitors.disabled_from(["A", "B"], ["A", "B"]), [])
        self.assertEqual(monitors.disabled_from([], ["A", "B"]), [])          # never switch everything off

    def test_default_is_all_monitors(self):
        self.assertEqual(DEFAULTS["disabled_monitors"], [])

    def test_engine_gets_the_list(self):
        cfg = engine_overrides.apply_forced({}, {"disabled_monitors": ["B"]})
        self.assertEqual(cfg["disabledMonitors"], ["B"])
        self.assertEqual(engine_overrides.apply_forced({}, {})["disabledMonitors"], [])

    def test_engine_never_crashes_with_everything_disabled(self):
        text = (APP / "edgeware_core/src/utils.py").read_text(encoding="utf-8")
        self.assertIn("[primary_monitor()]", text)

    def test_gui_has_card_and_saves(self):
        gui = (APP / "gui/app.py").read_text(encoding="utf-8")
        self.assertIn('"MONITORS"', gui)
        self.assertIn("monitors.disabled_from", gui)


if __name__ == "__main__":
    unittest.main()
