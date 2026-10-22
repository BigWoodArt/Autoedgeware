"""Look-and-feel helpers that need no window: colour mixing and that every dialog uses the styled widgets."""
import re
import unittest
from pathlib import Path

try:
    from gui.style import ColumnList, mix
except ImportError:      # no Tk on this machine: the window-free checks below still run
    mix = ColumnList = None

GUI = Path(__file__).resolve().parent.parent / "gui"


class Style(unittest.TestCase):
    @unittest.skipIf(mix is None, "Tk not installed")
    def test_mix(self):
        self.assertEqual(mix("#000000", "#ffffff", 0.5), "#808080")
        self.assertEqual(mix("#102030", "#ffffff", 0), "#102030")
        self.assertEqual(mix("nonsense", "#ffffff", 0.5), "nonsense")     # never raises

    @unittest.skipIf(mix is None, "Tk not installed")
    def test_columns_and_trimming(self):
        self.assertEqual(ColumnList.columns_that_fit(ColumnList, 600), 2)
        self.assertEqual(ColumnList.columns_that_fit(ColumnList, 100), 1)
        long = "x" * 200
        shown = ColumnList.fit(long, 290)
        self.assertTrue(shown.endswith("\u2026") and len(shown) < 50)
        self.assertEqual(ColumnList.fit("short", 290), "short")

    def test_no_plain_buttons_checkbuttons_or_entries_left(self):
        for name in ("app.py", "first_run_dialog.py", "preset_editor.py", "preset_finder_dialog.py"):
            text = (GUI / name).read_text(encoding="utf-8")
            for plain in ("Button", "Checkbutton", "Entry", "Scrollbar"):
                self.assertIsNone(re.search(r"\btk\." + plain + r"\(", text), f"{name} still uses tk.{plain}")


if __name__ == "__main__":
    unittest.main()
