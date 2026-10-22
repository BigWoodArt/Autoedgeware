"""Autoedgeware-specific (not shared): which sites are offered, and how the scheduler treats them."""
import os
import tempfile
import unittest

from ae_settings.preset import Preset
from core.display_queue import DisplayQueue
from core.scheduler import BOORU_SOURCE_TYPES, PresetWorker
from core.source_registry import SOURCE_REGISTRY, SOURCE_TYPES

NEW_BOORUS = ("rule34", "safebooru", "tbib", "xbooru")


class Registry(unittest.TestCase):
    def test_every_site_is_offered_and_matches_its_own_id(self):
        for site in NEW_BOORUS + ("reddit", "gelbooru", "realbooru", "hypnohub", "soundgasm", "erome", "redgifs"):
            with self.subTest(site=site):
                self.assertIn(site, SOURCE_TYPES)
                self.assertEqual(SOURCE_REGISTRY[site].id, site)

    def test_new_sites_get_no_made_up_sort_tag_but_old_ones_still_do(self):
        seen = {}

        class Capture:
            def __init__(self, **kw):
                pass

            def fetch(self, query, **kw):
                seen["query"] = query
                return []

        for site, expect_tag in (("rule34", False), ("safebooru", False), ("gelbooru", True)):
            with self.subTest(site=site), tempfile.TemporaryDirectory() as root:
                preset = Preset(name="p", sources=[{"source_type": site, "query": "cat_ears"}])
                w = PresetWorker(preset, {site: Capture}, root, DisplayQueue(), on_log=lambda m, l="info": None)
                w._fetch_one_source(preset.sources[0], preset.media_dir(root))
                self.assertEqual("sort:" in seen["query"], expect_tag, seen["query"])
        self.assertTrue(set(NEW_BOORUS).isdisjoint(BOORU_SOURCE_TYPES))


if __name__ == "__main__":
    unittest.main()


class NewSourcesRegistered(unittest.TestCase):
    def test_new_ids_present_and_have_fetch(self):
        from core.source_registry import SOURCE_REGISTRY
        for sid in ("e621", "danbooru", "yandere", "konachan", "derpibooru", "wallhaven",
                    "civitai", "lemmy", "coomer", "fapello", "kemono"):
            self.assertIn(sid, SOURCE_REGISTRY)
            self.assertEqual(SOURCE_REGISTRY[sid].id, sid)
