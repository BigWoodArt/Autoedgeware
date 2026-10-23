import unittest
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
ENGINE = (APP / "run_engine.py").read_text(encoding="utf-8")
GUI = (APP / "gui" / "app.py").read_text(encoding="utf-8")


class LiveReload(unittest.TestCase):
    def test_engine_exposes_reload(self):
        self.assertIn("state.ae_reload = reload_settings", ENGINE)
        self.assertIn("settings.config = load_engine_config()", ENGINE)
        self.assertIn("settings.load_settings()", ENGINE)

    def test_reload_keeps_hibernate_quiet(self):
        self.assertIn('if progression["hibernating"]', ENGINE.split("def reload_settings")[1].split("state.ae_reload")[0])

    def test_save_calls_reload(self):
        save = GUI.split("    def save(self):")[1].split("    def save_and_exit")[0]
        self.assertIn("ae_reload", save)
        self.assertIn("reload_live()", save)


if __name__ == "__main__":
    unittest.main()
