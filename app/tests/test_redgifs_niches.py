"""Redgifs niches + tag picks, offline: python -m unittest tests.test_redgifs_niches"""
import json
import tempfile
import threading
import unittest
import urllib.parse
import urllib.request
from unittest import mock

from tests._net import reply
from core import netlog, preset_finder
from core.source_registry import SOURCE_REGISTRY

CLIP = b"x" * 50


def gif(n, tags=("a",), desc=""):
    return {"id": f"g{n}", "tags": list(tags), "description": desc, "type": 1, "hasAudio": True,
            "urls": {"hd": f"https://media.redgifs.com/v{n}.mp4"}}


def site(niches=(), niche_gifs=None, tag_gifs=(), text_gifs=()):
    urls = []

    def handler(req):
        url = req.full_url
        urls.append(url)
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
        path = urllib.parse.urlparse(url).path
        if path.endswith("/auth/temporary"):
            return reply(json.dumps({"token": "t"}))
        if path == "/v2/search/suggest":
            return reply("[]")
        if path == "/v2/niches":
            return reply(json.dumps({"niches": list(niches)}))
        if path.startswith("/v2/niches/") and path.endswith("/gifs"):
            nid = path.split("/")[3]
            return reply(json.dumps({"gifs": (niche_gifs or {}).get(nid, [])}))
        if path == "/v2/gifs/search":
            if "tags" in q:
                return reply(json.dumps({"gifs": list(tag_gifs)}))
            return reply(json.dumps({"gifs": list(text_gifs)}))
        return reply(CLIP + url.encode())
    return handler, urls


def run(handler, query, limit=10):
    log, got = [], []
    with mock.patch("time.sleep"), mock.patch.object(netlog, "_orig_urlopen", lambda req, timeout=15: handler(req)):
        urllib.request.urlopen = netlog._wrapped
        src = SOURCE_REGISTRY["redgifs"]()
        items = src.fetch(query, limit, "Score", None, tempfile.mkdtemp(), lambda m, l="info": log.append(m),
                          lambda *a: None, threading.Event(), item_cb=got.append)
    return items, log


class Niches(unittest.TestCase):
    N = [{"id": "hypno-play", "name": "Hypno Play", "gifs": 400}, {"id": "tiny", "name": "Tiny", "gifs": 3}]

    def test_registry_uses_wrapper(self):
        self.assertEqual(SOURCE_REGISTRY["redgifs"].__module__, "ae_sources.redgifs_niches")

    def test_plain_word_pulls_best_niche(self):
        h, urls = site(self.N, {"hypno-play": [gif(1), gif(2)]})
        items, _ = run(h, "hypnotic")
        self.assertEqual(len(items), 2)
        self.assertTrue(any("/v2/niches/hypno-play/gifs" in u for u in urls))
        self.assertFalse(any("/niches/tiny" in u for u in urls))

    def test_niche_token(self):
        h, urls = site(self.N, {"hypno-play": [gif(1)]})
        items, _ = run(h, "niche:hypno-play")
        self.assertEqual([i.post_id for i in items], ["rg_g1"])
        self.assertFalse(any(u.endswith("/v2/niches?query=hypno-play&count=20&page=1") for u in urls))

    def test_paging_ignored_does_not_loop(self):
        h, _ = site(self.N, {"hypno-play": [gif(n) for n in range(1, 81)]})
        items, _ = run(h, "niche:hypno-play", limit=200)
        self.assertEqual(len(items), 80)

    def test_falls_back_to_tag(self):
        h, urls = site([], tag_gifs=[gif(1, ("Spiral",))])
        items, _ = run(h, "spiral")
        self.assertEqual(len(items), 1)
        self.assertTrue(any("tags=" in u for u in urls))

    def test_falls_back_to_text_and_filters(self):
        h, urls = site([], tag_gifs=[], text_gifs=[gif(1, ("x",), "a spiral clip"), gif(2, ("y",), "madness")])
        items, _ = run(h, "spiral")
        self.assertEqual([i.post_id for i in items], ["rg_g1"])

    def test_tag_token(self):
        h, urls = site(self.N, tag_gifs=[gif(1, ("Spiral",))])
        items, _ = run(h, "tag:Spiral")
        self.assertEqual(len(items), 1)
        self.assertFalse(any("/v2/niches" in u for u in urls))


class Suggest(unittest.TestCase):
    def test_niches_then_tags(self):
        texts = [gif(i, ("Hypno", "Spiral"), "hypno spiral") for i in range(3)] + [gif(9, ("Zed",), "hypno")]
        h, _ = site(Niches.N, text_gifs=texts)
        with mock.patch.object(netlog, "_orig_urlopen", lambda req, timeout=15: h(req)):
            urllib.request.urlopen = netlog._wrapped
            out = SOURCE_REGISTRY["redgifs"].suggest("hypno")
        self.assertEqual(out[0]["value"], "niche:hypno-play")
        self.assertEqual(out[0]["count"], 400)
        self.assertEqual([o["value"] for o in out[1:]], ["tag:Hypno", "tag:Spiral"])

    def test_finder_shows_both_and_ticks_two(self):
        fake = lambda cls, term: [{"value": "niche:a", "label": "n", "count": 5}, {"value": "niche:b", "label": "n", "count": 4},
                                  {"value": "tag:c", "label": "t", "count": None}]
        out = preset_finder.find("hypno", ["redgifs"], SOURCE_REGISTRY, suggest_fn=fake)
        self.assertEqual([p.ticked for p in out["redgifs"]], [True, True, False])
        self.assertEqual(preset_finder.to_sources(out["redgifs"])[0]["query"], "niche:a")


if __name__ == "__main__":
    unittest.main()
