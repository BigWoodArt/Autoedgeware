"""Hypnotube and PMV Haven in Autoedgeware, offline: python -m unittest tests.test_video_sites"""
import json
import os
import tempfile
import threading
import types
import unittest
import urllib.request
from unittest import mock

from tests._net import reply, err
from core import netlog
from core.source_registry import SOURCE_REGISTRY
from ae_sources import pmvhaven_pages as pages

CARD = ('<a href="https://hypnotube.com/video/{slug}-{id}.html" class="x" title="{title}"><span class="quality-icon">{hd}</span>'
        '<span class="s-e-rate"> {rate}%</span></a>')
HT_PAGE = (CARD.format(slug="deep-spiral", id=222, title="Deep Spiral", hd="HD", rate=90) +
           CARD.format(slug="low-one", id=111, title="Low One", hd="SD", rate=50) + "page2.html")
HT_VIDEO = ('<meta name="keywords" content="spiral, trance"><video id="plyr_player"><source src="https://media.hypnotube.com/v/a.mp4?t=1&amp;e=2" sizes="480" />'
            '<source src="https://media.hypnotube.com/v/b.mp4?t=1" sizes="720" /></video>')
PMV_PAGE = ('<title>Rapid 12 - PMVHaven</title><a href="/video/rapid-12_6aca7db93cc0c5c8dff617ae?from=search">x</a>'
            '<script>"https:\\u002F\\u002Fcdn.pmvhaven.com\\u002Fabc\\u002Fmaster.m3u8"</script>')


def run(site, handler, query="spiral", limit=5, **kw):
    urls, log, got = [], [], []

    def fake(req, timeout=15):
        urls.append(req.full_url)
        return handler(req)
    with mock.patch("time.sleep"), mock.patch.object(netlog, "_orig_urlopen", fake):
        urllib.request.urlopen = netlog._wrapped
        src = SOURCE_REGISTRY[site]()
        if hasattr(src, "_opener"):                       # HypnoTube keeps its own cookie opener
            src._opener = types.SimpleNamespace(open=lambda req, timeout=20: fake(req))
        items = src.fetch(query, limit, kw.get("sort"), None, tempfile.mkdtemp(),
                          lambda m, l="info": log.append((l, m)), lambda *a: None, threading.Event(),
                          item_cb=got.append, skip_ids=kw.get("skip"))
    return items, urls, log


class Registry(unittest.TestCase):
    def test_listed_and_grouped(self):
        from core.source_groups import grouped
        video = dict(grouped(SOURCE_REGISTRY))["Video"]
        self.assertIn("hypnotube", video)
        self.assertIn("pmvhaven", video)
        for site in ("hypnotube", "pmvhaven"):
            self.assertEqual(SOURCE_REGISTRY[site].id, site)

    def test_quality_maps_to_sort_and_filters(self):
        from core import quality_map
        ht, pm = SOURCE_REGISTRY["hypnotube"], SOURCE_REGISTRY["pmvhaven"]
        self.assertEqual(quality_map.resolve(ht, "Best"), {"sort": "rating", "query_suffix": "minrating:85"})
        self.assertEqual(quality_map.resolve(ht, "Good"), {"sort": "views", "query_suffix": "minrating:70"})
        self.assertEqual(quality_map.resolve(ht, "Any"), {})
        self.assertEqual(quality_map.resolve(pm, "Best"), {"sort": "-bayesianRating", "query_suffix": "minrating:85"})


class Hypnotube(unittest.TestCase):
    def handler(self, req):
        url = req.full_url
        if url.endswith("/searchgate.php") or "/search/" in url:
            return reply(HT_PAGE)
        if url.endswith(".html"):
            return reply(HT_VIDEO.replace("b.mp4", url.rsplit("-", 1)[1].replace(".html", "") + ".mp4"))
        return reply(b"\x00VID" + url.encode())

    def test_download_picks_biggest_source(self):
        items, urls, log = run("hypnotube", self.handler)
        self.assertEqual([i.post_id for i in items], ["ht_222", "ht_111"])
        self.assertTrue(all(i.media_type == "video" and os.path.getsize(i.file_path) for i in items))
        self.assertTrue(any("/v/222.mp4" in u for u in urls) and not any("/v/a.mp4" in u for u in urls))

    def test_sort_label_becomes_the_site_path(self):
        _i, urls, _l = run("hypnotube", self.handler, sort="rating", limit=1)
        self.assertIn("https://hypnotube.com/search/spiral/rating/", urls)
        _i, urls, _l = run("hypnotube", self.handler, sort="Hot", limit=1)       # a sort from another site: ignored
        self.assertTrue(any(u.endswith("/searchgate.php") for u in urls))

    def test_minimum_rating_filters_cards(self):
        items, _u, _l = run("hypnotube", self.handler, query="spiral minrating:85")
        self.assertEqual([i.post_id for i in items], ["ht_222"])

    def test_skip_ids(self):
        items, _u, _l = run("hypnotube", self.handler, skip={"ht_222"})
        self.assertEqual([i.post_id for i in items], ["ht_111"])


class Pmvhaven(unittest.TestCase):
    def api(self, videos):
        def handler(req):
            url = req.full_url
            if "/api/videos" in url:
                return reply(json.dumps({"videos": videos, "total": len(videos),
                                         "pagination": {"hasNext": False, "total": len(videos)}}))
            return reply(b"\x00MP4" + url.encode())
        return handler

    def test_direct_files_kept_streams_skipped(self):
        vids = [{"_id": "a1", "videoUrl": "https://cdn.x/a.mp4", "title": "A"},
                {"_id": "b2", "videoUrl": "https://cdn.x/b/master.m3u8", "title": "B"}]
        items, _u, _l = run("pmvhaven", self.api(vids))
        self.assertEqual([i.post_id for i in items], ["pmv_a1"])

    def test_keyword_rows_without_a_file_link_are_looked_up(self):
        def handler(req):
            url = req.full_url
            if "/api/videos/search" in url:
                return reply(json.dumps({"videos": [{"_id": "k1", "title": "K"}, {"_id": "k2", "title": "S"}],
                                         "pagination": {"hasNext": False, "total": 2}}))
            if url.endswith("/api/videos/k1"):
                return reply(json.dumps({"data": {"videoUrl": "https://cdn.x/k1.mp4", "tags": []}}))
            if url.endswith("/api/videos/k2"):
                return reply(json.dumps({"data": {"videoUrl": "https://cdn.x/k2/master.m3u8", "tags": []}}))
            return reply(b"\x00MP4" + url.encode())
        items, urls, _l = run("pmvhaven", handler)
        self.assertEqual([i.post_id for i in items], ["pmv_k1"])         # the playlist is skipped, the file kept
        self.assertFalse(any("pmvhaven.com/search" in u for u in urls))     # no fallback to the website needed

    def test_tag_search_uses_sort_value(self):
        vids = [{"_id": "a1", "videoUrl": "https://cdn.x/a.mp4", "title": "A"}]
        _i, urls, _l = run("pmvhaven", self.api(vids), query="tag:Trans", sort="-views")
        api = [u for u in urls if "/api/videos?" in u][0]
        self.assertIn("sort=-views", api)
        self.assertIn("tags=Trans", api)

    def test_falls_back_to_website_when_only_streams(self):
        vids = [{"_id": "b2", "videoUrl": "https://cdn.x/b/master.m3u8", "title": "B"}]
        with mock.patch.object(pages.PmvhavenPageSource, "fetch", return_value=["page-result"]) as page_fetch:
            items, _u, log = run("pmvhaven", self.api(vids))
        self.assertEqual(items, ["page-result"])
        self.assertEqual(page_fetch.call_args[0][0], "spiral")
        self.assertTrue(any("stream playlists" in m for _l, m in log))

    def test_no_fallback_for_tag_searches(self):
        with mock.patch.object(pages.PmvhavenPageSource, "fetch") as page_fetch:
            run("pmvhaven", self.api([]), query="tag:Trans")
        page_fetch.assert_not_called()


class PageFallback(unittest.TestCase):
    def test_parse(self):
        url, title = pages.parse_video(PMV_PAGE)
        self.assertEqual(url, "https://cdn.pmvhaven.com/abc/master.m3u8")
        self.assertEqual(title, "Rapid 12")
        self.assertEqual(pages.parse_links(PMV_PAGE)[0][1], "6aca7db93cc0c5c8dff617ae")
        self.assertEqual(pages.clean_word("https://pmvhaven.com/search?q=hypno%20pmv"), "hypno pmv")

    def test_half_written_file_never_looks_like_media(self):
        seen = {}

        def fake_ffmpeg(cmd, **kw):
            seen["part"] = cmd[-1]
            with open(cmd[-1], "wb") as f:
                f.write(b"\x00" * 20000)
            return mock.Mock(returncode=0)
        folder = tempfile.mkdtemp()
        with mock.patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            src = pages.PmvhavenPageSource()
        with mock.patch("subprocess.run", side_effect=fake_ffmpeg):
            src._grab("https://cdn/x/master.m3u8", os.path.join(folder, "v.mp4"))
        self.assertFalse(seen["part"].lower().endswith((".mp4", ".webm", ".mov", ".m4v")))
        self.assertEqual(os.listdir(folder), ["v.mp4"])

    def test_ffmpeg_missing_is_a_clear_skip(self):
        log = []
        with mock.patch("shutil.which", return_value=None):
            src = pages.PmvhavenPageSource()
        self.assertEqual(src.fetch("x", 1, None, None, tempfile.mkdtemp(), lambda m, l="info": log.append(m),
                                   lambda *a: None, threading.Event()), [])
        self.assertTrue(any("ffmpeg" in m for m in log))


if __name__ == "__main__":
    unittest.main()
