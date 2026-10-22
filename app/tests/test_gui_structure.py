"""Autoedgeware-only: catches the v0.10.11 bug where a second method with the same name silently
replaced the first and every button that used it broke. No Tk needed."""
import ast
import unittest
from collections import Counter
from pathlib import Path

GUI = Path(__file__).resolve().parent.parent / "gui"


class NoDuplicateNames(unittest.TestCase):
    def test_no_class_defines_the_same_method_twice(self):
        problems = []
        for path in sorted(GUI.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
                names = Counter(n.name for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
                problems += [f"{path.name}:{cls.name}.{name} defined {n}x" for name, n in names.items() if n > 1]
        self.assertEqual(problems, [])

    def test_every_self_method_the_window_refers_to_exists(self):
        """Every self.<name>(...) call or self.<name> button command in app.py names a real method,
        attribute or variable of the window, so a rename can never leave a dead button behind."""
        tree = ast.parse((GUI / "app.py").read_text(encoding="utf-8"))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "AutoedgewareGUI")
        methods = {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}
        assigned = {n.attr for n in ast.walk(cls) if isinstance(n, ast.Attribute)
                    and isinstance(n.ctx, ast.Store) and isinstance(n.value, ast.Name) and n.value.id == "self"}
        tk_names = set(dir(__import__("tkinter").Tk)) if __import__("importlib").util.find_spec("tkinter") else set()
        refs = {n.attr for n in ast.walk(cls) if isinstance(n, ast.Attribute)
                and isinstance(n.value, ast.Name) and n.value.id == "self" and isinstance(n.ctx, ast.Load)}
        missing = sorted(r for r in refs if r not in methods | assigned | tk_names and r not in INHERITED_TK)
        self.assertEqual(missing, [])
        for command in ("save", "save_and_exit", "run_now", "pause_now", "stop_now", "save_exit_and_run", "_open_finder"):
            self.assertIn(command, methods)


# Tk window methods used by the app that may not show up without tkinter installed.
INHERITED_TK = {"after", "after_cancel", "destroy", "title", "configure", "geometry", "resizable",
                "protocol", "update", "mainloop", "winfo_children", "winfo_exists", "quit", "select", "update_idletasks", "winfo_height", "winfo_screenheight"}


if __name__ == "__main__":
    unittest.main()


class SettingsTabs(unittest.TestCase):
    SRC = (GUI / "app.py").read_text(encoding="utf-8")

    def test_tabs_and_builders(self):
        for tab in ("Popups", "Modes", "Downloads", "Advanced"):
            self.assertIn(f'"{tab}")', self.SRC)
        for name in ("popups", "modes", "downloads", "advanced"):
            self.assertIn(f"def _build_{name}_tab", self.SRC)
        self.assertNotIn("_build_general_tab", self.SRC)
        self.assertNotIn('"Session"', self.SRC)

    def test_every_setting_variable_is_still_on_a_settings_tab(self):
        import re
        names = set(re.findall(r"self\.(\w+_vars?)\s*=", self.SRC)) - {"hypno_var", "hero_var", "status_var", "selected_name"}
        body = self.SRC[self.SRC.index("def _build_popups_tab"):self.SRC.index("def _build_log_tab")]
        self.assertEqual(sorted(n for n in names if f"self.{n}" not in body), [])

    def test_hints_stay_short(self):
        import re
        body = self.SRC[self.SRC.index("def _build_popups_tab"):self.SRC.index("def _build_log_tab")]
        for text in re.findall(r'_hint\([^,]+,\s*((?:"[^"\\]*(?:\\.[^"\\]*)*"\s*)+)', body):
            words = len(" ".join(re.findall(r'"((?:[^"\\]|\\.)*)"', text)).split())
            self.assertLessEqual(words, 20, text)
