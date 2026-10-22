"""Settings tabs: Popups / Modes / Downloads / Advanced, and the sound fields are saved. No Tk needed."""
import unittest
from pathlib import Path

from ae_settings.settings import DEFAULTS

SRC = (Path(__file__).resolve().parent.parent / "gui" / "app.py").read_text(encoding="utf-8")


class Tabs(unittest.TestCase):
    def test_tabs_exist_in_order(self):
        order = [SRC.index(f', "{t}")') for t in ("Main", "Popups", "Modes", "Downloads", "Advanced", "Log")]
        self.assertEqual(order, sorted(order))

    def test_delete_preset_button_exists(self):
        self.assertIn('"Delete", self._delete_preset', SRC)
        self.assertIn("def _delete_preset", SRC)
        self.assertIn("Keep at least one preset", SRC)      # the last preset can't be deleted
        self.assertIn("Press Stop first", SRC)              # nor while it is running

    def test_sound_fields_are_saved(self):
        for key in ("audio_volume", "video_volume", "max_audio", "hypno_beat_volume", "fullscreen_video_volume_pct"):
            self.assertIn(f'"{key}"', SRC)
            self.assertIn(key, DEFAULTS)

    def test_no_stale_references(self):
        self.assertNotIn("settings_scroll", SRC)
        self.assertNotIn("Collapsible", SRC)


if __name__ == "__main__":
    unittest.main()
