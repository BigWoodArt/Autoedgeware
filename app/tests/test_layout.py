"""Autoedgeware-only: the folder layout is 'run.bat, README and media at the top, everything else in app/'."""
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
TOP = APP.parent


class Layout(unittest.TestCase):
    def test_top_folder_is_only_run_bat_readme_and_app(self):
        shown = {p.name for p in TOP.iterdir() if not p.name.startswith(".")}
        shown -= {"old_version_backup", "media"}
        self.assertTrue({"run.bat", "README.md", "app"} <= shown)
        self.assertTrue(shown <= {"run.bat", "README.md", "CHANGELOG.md", "LICENSE", "app"})

    def test_run_bat_goes_into_app_and_migrates_old_layouts(self):
        text = (TOP / "run.bat").read_text(encoding="utf-8")
        self.assertIn('cd /D "%~dp0app"', text)
        self.assertIn("call setup.bat", text)
        self.assertIn('start "" pyw gui_main.py', text)
        # an old-layout folder keeps its downloads, logs, presets/settings and the video library
        # (robocopy /MOVE merges into an existing folder, so a half-done earlier move cannot strand files)
        for piece in ('call :mv "app\\media" "media"', 'call :mv "logs" "app\\logs"', 'ae_settings\\*.json',
                      'edgeware_core\\data\\*.dll', "robocopy", "/E /MOVE", 'if exist "app\\media\\"'):
            self.assertIn(piece, text)
        # moves only - it must never delete anything
        lowered = text.lower()
        for word in ("del ", "rmdir", "rd ", "erase"):
            self.assertNotIn(word, lowered)

    def test_app_has_the_program(self):
        for name in ("gui_main.py", "run_engine.py", "setup.bat", "VERSION", "requirements.txt", "core", "gui", "sources"):
            self.assertTrue((APP / name).exists(), name)


if __name__ == "__main__":
    unittest.main()
