"""Autoedgeware-specific (not shared): the per-row Any / Good / Best choice."""
import tempfile
import unittest

from ae_settings.preset import Preset, source_entry
from core.display_queue import DisplayQueue
from core.scheduler import PresetWorker
from core.source_registry import SOURCE_REGISTRY


def fetch_settings(site, query="cat", quality=None):
    """What the scheduler would hand the real <site> class for a row (the network part is replaced)."""
    got = {}

    class Capture(SOURCE_REGISTRY[site]):            # keeps the real class's quality rules
        def __init__(self, **kw):
            pass

        def fetch(self, query, limit, sort, time_range, *a, **kw):
            got.update(query=query, sort=sort, time_range=time_range)
            return []

    row = {"source_type": site, "query": query}
    if quality:
        row["quality"] = quality
    with tempfile.TemporaryDirectory() as root:
        preset = Preset(name="p", sources=[row])
        w = PresetWorker(preset, {site: Capture}, root, DisplayQueue(), on_log=lambda m, l="info": None)
        w._fetch_one_source(row, preset.media_dir(root))
    return got


class Quality(unittest.TestCase):
    def test_reddit_and_redgifs(self):
        self.assertEqual(fetch_settings("reddit", "aww", "Good")["sort"], "Top")
        self.assertEqual(fetch_settings("reddit", "aww", "Good")["time_range"], "month")
        self.assertEqual(fetch_settings("reddit", "aww", "Best")["time_range"], "year")
        self.assertEqual(fetch_settings("redgifs", "cats", "Good")["sort"], "Top 28 days")
        self.assertEqual(fetch_settings("redgifs", "cats", "Best")["sort"], "Top")

    def test_boorus_get_a_minimum_score_and_no_made_up_sort_tag(self):
        # Good / Best now also sort by score (the shared sites list "Highest score" as their order)
        for site, quality, tag in (("gelbooru", "Good", "score:>=10"), ("gelbooru", "Best", "score:>=50"),
                                   ("rule34", "Best", "score:>=100"), ("safebooru", "Good", "score:>=5"),
                                   ("realbooru", "Best", "score:>=25")):       # 20 is not offered: nearest step
            with self.subTest(site=site, quality=quality):
                q = fetch_settings(site, "cat_ears", quality)["query"]
                self.assertEqual(q, f"cat_ears sort:score {tag}")

    def test_any_keeps_the_old_random_mix(self):
        self.assertIn(fetch_settings("reddit", "aww")["sort"], ("Top", "Hot", "New"))
        self.assertNotIn("score:", fetch_settings("gelbooru", "cat_ears")["query"])
        self.assertIn("sort:", fetch_settings("gelbooru", "cat_ears", "Any")["query"])

    def test_sites_without_quality_ignore_it(self):
        self.assertEqual(fetch_settings("soundgasm", "someone", "Best")["query"], "someone")
        self.assertEqual(fetch_settings("erome", "tag", "Best")["query"], "tag")

    def test_a_score_you_typed_is_not_doubled(self):
        q = fetch_settings("gelbooru", "cat_ears score:>=3", "Best")["query"]
        self.assertEqual(q.count("score:>="), 1)
        self.assertIn("score:>=3", q)


class SavedRow(unittest.TestCase):
    def test_only_used_options_are_saved(self):
        self.assertEqual(source_entry("reddit", "aww"), {"source_type": "reddit", "query": "aww"})
        self.assertEqual(source_entry("reddit", "aww", " 12 ", "Best"),
                         {"source_type": "reddit", "query": "aww", "limit": 12, "quality": "Best"})
        self.assertNotIn("quality", source_entry("reddit", "aww", "", "Any"))
        self.assertNotIn("limit", source_entry("reddit", "aww", "lots", "Good"))

    def test_description_shows_the_choice(self):
        p = Preset(name="p", sources=[source_entry("reddit", "aww", "5", "Good"), source_entry("tbib", "x")])
        self.assertIn("aww (limit 5, Good)", p.description())
        self.assertTrue(p.description().endswith("x"))


if __name__ == "__main__":
    unittest.main()


class QualityMap(unittest.TestCase):
    """The table that says what Good / Best mean per site (core/quality_map.py)."""

    def test_every_listed_site_exists_and_gives_something_for_good_and_best(self):
        from core import quality_map
        for site in (x for x in quality_map.TABLE if x in SOURCE_REGISTRY):
            for q in ("Good", "Best"):
                with self.subTest(site=site, quality=q):
                    cls = SOURCE_REGISTRY[site]
                    out = quality_map.resolve(cls, q)
                    self.assertTrue(out, out)
                    self.assertTrue(set(out) <= {"sort", "time_range", "query_suffix"})

    def test_same_meaning_as_before_for_the_sites_that_had_a_sort_rule(self):
        from core import quality_map
        from sources import SOURCE_BY_ID
        r = lambda site, q: quality_map.resolve(SOURCE_REGISTRY.get(site) or SOURCE_BY_ID[site], q)
        self.assertEqual(r("reddit", "Good"), {"sort": "Top", "time_range": "month"})
        self.assertEqual(r("reddit", "Best"), {"sort": "Top", "time_range": "year"})
        self.assertEqual(r("redgifs", "Good"), {"sort": "Top 28 days"})
        self.assertEqual(r("redgifs", "Best"), {"sort": "Top"})
        self.assertEqual(r("freesound", "Good"), {"sort": "Downloads"})
        self.assertEqual(r("freesound", "Best"), {"sort": "Rating"})
        self.assertEqual(r("lemmy", "Best"), {"sort": "TopYear"})

    def test_any_and_unlisted_sites_change_nothing(self):
        from core import quality_map
        self.assertEqual(quality_map.resolve(SOURCE_REGISTRY["reddit"], "Any"), {})
        self.assertEqual(quality_map.resolve(SOURCE_REGISTRY["soundgasm"], "Best"), {})
        self.assertFalse(quality_map.supported("erome"))

    def test_nearest_score_step_is_used_when_the_exact_one_is_not_offered(self):
        from core import quality_map
        self.assertEqual(quality_map._nearest([("5", "5+", {}), ("10", "10+", {}), ("25", "25+", {})], 20), "25")
        self.assertEqual(quality_map._nearest([("", "Any", {})], 20), "")
