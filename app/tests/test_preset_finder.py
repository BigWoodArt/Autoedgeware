"""Autoedgeware-only: the Preset Finder's logic (no network, no Tk)."""
import time
import unittest

from core import preset_finder as pf
from sources.base import Source


class WithSuggest(Source):
    id, label = "with", "With"

    @classmethod
    def suggest(cls, query):
        return []


class NoSuggest(Source):
    id, label = "plain", "Plain"


REGISTRY = {"with": WithSuggest, "plain": NoSuggest}


def fake(results):
    return lambda cls, term: results


class Finder(unittest.TestCase):
    def test_detects_which_sites_can_suggest(self):
        self.assertTrue(pf.has_suggest(WithSuggest))
        self.assertFalse(pf.has_suggest(NoSuggest))

    def test_suggestions_and_typed_fallback(self):
        data = [{"value": f"tag{i}", "label": f"With tag{i}", "count": 100 - i} for i in range(9)]
        out = pf.find("cats", ["with", "plain"], REGISTRY, suggest_fn=fake(data))
        self.assertEqual(len(out["with"]), pf.PER_SITE)
        self.assertEqual([p.ticked for p in out["with"]], [True, False, False, False, False])   # top 1 ticked
        self.assertEqual(out["plain"][0].value, "cats")                                          # as typed
        self.assertTrue(out["plain"][0].ticked)

    def test_reddit_gets_top_three_ticked(self):
        class Reddit(WithSuggest):
            id, label = "reddit", "Reddit"
        data = [{"value": f"r{i}", "label": f"r/r{i}", "count": 5} for i in range(5)]
        out = pf.find("cats", ["reddit"], {"reddit": Reddit}, suggest_fn=fake(data))
        self.assertEqual(sum(p.ticked for p in out["reddit"]), 3)

    def test_blocked_terms_and_results_never_appear(self):
        with self.assertRaises(ValueError):
            pf.find("loli", ["with"], REGISTRY)
        with self.assertRaises(ValueError):
            pf.find("   ", ["with"], REGISTRY)
        data = [{"value": "toddler_stuff", "label": "x", "count": 1}, {"value": "fine", "label": "Fine", "count": 2}]
        out = pf.find("cats", ["with"], REGISTRY, suggest_fn=fake(data))
        self.assertEqual([p.value for p in out["with"]], ["fine"])

    def test_empty_or_failing_site_falls_back_to_typed_search(self):
        out = pf.find("cats", ["with"], REGISTRY, suggest_fn=fake([]))
        self.assertEqual(out["with"][0].value, "cats")
        self.assertIn("no matches", out["with"][0].note)

        def boom(cls, term):
            raise RuntimeError("site down")
        out = pf.find("cats", ["with"], REGISTRY, suggest_fn=lambda c, t: pf._safe_suggest(type("X", (), {"suggest": boom}), t))
        self.assertEqual(out["with"][0].value, "cats")

    def test_slow_site_does_not_hold_up_the_rest(self):
        def slow(cls, term):
            time.sleep(1.5)
            return [{"value": "late", "label": "late", "count": 1}]
        start = time.time()
        out = pf.find("cats", ["with", "plain"], REGISTRY, timeout=0.2, suggest_fn=slow)
        self.assertLess(time.time() - start, 1.0)
        self.assertIn("no answer", out["with"][0].note)
        self.assertEqual(out["plain"][0].value, "cats")

    def test_merge_keeps_ticks_and_skips_duplicates(self):
        first = pf.find("cats", ["plain"], REGISTRY)
        picks = pf.merge([], first)
        picks[0].ticked = False                               # the user unticked it
        again = pf.find("Cats", ["plain"], REGISTRY)          # same term, different case
        pf.merge(picks, again)
        self.assertEqual(len(picks), 1)
        self.assertFalse(picks[0].ticked)
        pf.merge(picks, pf.find("dogs", ["plain"], REGISTRY))
        self.assertEqual([p.value for p in picks], ["cats", "dogs"])

    def test_to_sources_only_ticked_and_unique(self):
        a = pf.Pick("with", "x", "x", ticked=True)
        b = pf.Pick("with", "y", "y", ticked=False)
        c = pf.Pick("with", "X", "x", ticked=True)            # duplicate of a
        self.assertEqual(pf.to_sources([a, b, c]), [{"source_type": "with", "query": "x"}])


if __name__ == "__main__":
    unittest.main()
