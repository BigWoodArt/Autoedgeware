"""Autoedgeware-only: API keys reach their sources."""
import unittest
from pathlib import Path

from core.api_keys import API_KEYS, build_source_kwargs
from ae_settings.settings import DEFAULTS

ROOT = Path(__file__).resolve().parent.parent


class Keys(unittest.TestCase):
    def test_wallhaven_key_goes_to_wallhaven(self):
        kw = build_source_kwargs({"wallhaven_api_key": "  abc123 "})
        self.assertEqual(kw, {"wallhaven": {"api_key": "abc123"}})

    def test_empty_keys_are_left_out(self):
        self.assertEqual(build_source_kwargs({"wallhaven_api_key": ""}), {})
        self.assertEqual(build_source_kwargs({}), {})

    def test_gelbooru_needs_key_and_id(self):
        self.assertEqual(build_source_kwargs({"gelbooru_api_key": "k"}), {})
        self.assertEqual(build_source_kwargs({"gelbooru_api_key": "k", "gelbooru_user_id": "u"}),
                         {"gelbooru": {"api_key": "k", "user_id": "u"}})

    def test_every_entry_has_a_default_setting_and_a_real_source(self):
        from core.source_registry import SOURCE_REGISTRY
        for source_id, setting_key, label, hint in API_KEYS:
            self.assertIn(setting_key, DEFAULTS)
            self.assertIn(source_id, SOURCE_REGISTRY)

    def test_all_three_launchers_use_the_shared_builder(self):
        for name in ("main.py", "run_engine.py", "gui/app.py"):
            self.assertIn("build_source_kwargs", (ROOT / name).read_text(encoding="utf-8"), name)

    def test_gui_saves_every_key(self):
        text = (ROOT / "gui/app.py").read_text(encoding="utf-8")
        self.assertIn("self.api_key_vars.items()", text)


if __name__ == "__main__":
    unittest.main()
