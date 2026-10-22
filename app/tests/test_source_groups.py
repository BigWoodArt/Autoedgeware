"""Autoedgeware-only: the source picker is grouped, and every site is in exactly one group."""
import unittest
from pathlib import Path

from core.source_groups import GROUPS, grouped
from core.source_registry import SOURCE_REGISTRY, SOURCE_TYPES

ROOT = Path(__file__).resolve().parent.parent


class Groups(unittest.TestCase):
    def test_group_names_and_order(self):
        self.assertEqual([g for g, _ in grouped(SOURCE_TYPES)], ["Image Boards", "Audio", "Video", "Images"])

    def test_every_registered_site_appears_exactly_once(self):
        flat = [sid for _g, ids in grouped(SOURCE_TYPES) for sid in ids]
        self.assertEqual(sorted(flat), sorted(SOURCE_TYPES))
        self.assertEqual(len(flat), len(set(flat)))

    def test_sensible_membership(self):
        by_group = dict(grouped(SOURCE_TYPES))
        self.assertIn("gelbooru", by_group["Image Boards"])
        self.assertIn("e621", by_group["Image Boards"])
        self.assertIn("soundgasm", by_group["Audio"])
        self.assertIn("redgifs", by_group["Video"])
        self.assertIn("reddit", by_group["Images"])
        self.assertIn("wallhaven", by_group["Images"])

    def test_an_unknown_new_site_still_shows_up(self):
        by_group = dict(grouped(SOURCE_TYPES + ["brandnew"]))
        self.assertIn("brandnew", by_group["Images"])

    def test_missing_sites_are_skipped_not_invented(self):
        self.assertEqual(grouped(["reddit"]), [("Images", ["reddit"])])

    def test_table_only_names_real_sites_or_known_extras(self):
        extras = {"freesound"}      # a source file exists but is not in the registry yet
        for _g, ids in GROUPS:
            for sid in ids:
                self.assertTrue(sid in SOURCE_REGISTRY or sid in extras, sid)

    def test_editor_uses_the_grouped_menu(self):
        text = (ROOT / "gui/preset_editor.py").read_text(encoding="utf-8")
        self.assertIn("grouped(SOURCE_TYPES)", text)
        self.assertNotIn("tk.OptionMenu(row_frame, type_var", text)


if __name__ == "__main__":
    unittest.main()
