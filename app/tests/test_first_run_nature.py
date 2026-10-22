import re
import unittest
from pathlib import Path

GUI = Path(__file__).resolve().parent.parent / "gui"
APP = (GUI / "app.py").read_text(encoding="utf-8")


class FirstRunNature(unittest.TestCase):
    def test_asks_once_when_only_nature(self):
        self.assertIn("elif self._only_default_preset() and not self.settings.get(\"first_run_done\")", APP)
        self.assertIn('self.settings["first_run_done"] = True', APP)

    def test_starter_replaced_by_choice(self):
        self.assertIn("self.presets.clear()", APP)

    def test_dialogs_centered(self):
        for name in ("first_run_dialog.py", "preset_editor.py", "preset_finder_dialog.py"):
            text = (GUI / name).read_text(encoding="utf-8")
            self.assertIn("center_on_screen(self,", text, name)
            self.assertIsNone(re.search(r'self\.geometry\("\d+x\d+"\)', text), name)


if __name__ == "__main__":
    unittest.main()
