"""PornPics + Babehub: search -> galleries -> every picture, with page layouts copied from the real sites."""
import unittest

from tests._net import fetch, reply, err


def pp_gallery(gid, n, rating="95", tags=("Blonde", "Solo"), title="Nice set"):
    pics = "".join(f"<li class='thumbwook'><a class='rel-link' href='https://cdni.pornpics.com/1280/1/22/{gid}/{gid}_{i:03d}_ab{i}.jpg' "
                   f"data-size='1280x1920'><img src='x'></a></li>" for i in range(1, n + 1))
    tg = "".join(f"<a href='/tags/{t.lower()}/' target=_self title='{t} Pics' ><span>{t}</span></a>" for t in tags)
    return (f"<html><title>{title} - PornPics.com</title><h1>{title}</h1>"
            f'<div class="gallery-info__item tags"><span class="gallery-info__title">Categories:</span></div>'
            f'<div class="gallery-info__item tags"><span class="gallery-info__title">Tags:</span><div>{tg}</div></div>'
            f'<div class="gallery-info__item"><span class="info-rate"><span class="rate-count">{rating}%</span></span></div>'
            f"<ul id='tiles'>{pics}</ul></html>")


def pp_listing(gids):
    return "<ul>" + "".join(f'<li><a class="rel-link" href="https://www.pornpics.com/galleries/some-set-{g}/">x</a></li>'
                            for g in gids) + "</ul>"


def bh_gallery(gid, n, likes=180, tags=("Blonde", "Petite"), title="Set title"):
    pics = "".join(f'<li><a data-fancybox="images" data-srcset="https://cdn.babehub.com/c/{gid}_{i}_800.jpg 800w" '
                   f'href="https://cdn.babehub.com/c/{gid}_{i}_1200.jpg" data-width="1200"><img src="y"></a></li>'
                   for i in range(1, n + 1))
    tg = "".join(f'<a href="https://www.babehub.com/tag/{t.lower()}/" class="visible-tag">{t}</a> ' for t in tags)
    return (f"<html><h1>{title}</h1><p class=\"link-btn scroll\"><a class=\"overlay-b\" href=\"https://www.babehub.com/model/jane/\">Jane</a>"
            f"{tg}</p><ul>{pics}</ul><span id=\"thelike\">{likes}</span></html>")


def bh_listing(gids, next_url=None):
    nav = (f'<nav class="pagination-a"><ul><li class="prev"><li class="next"><a href="{next_url}">Next</a></li></ul></nav>'
           if next_url else "")
    return ('<a href="/search/post/blonde/" class="overlay-a">Galleries</a><a href="https://www.babehub.com/tag/blonde/">tag</a>'
            '<ul class="list-gallery">'
            + "".join(f'<li><a href="https://www.babehub.com/some-title-{g}/">x</a></li>' for g in gids) + "</ul>" + nav)


class PornPics(unittest.TestCase):
    def handler(self, pages=None, galleries=None):
        pages = pages or {}
        galleries = galleries or {1001: (3, "95"), 1002: (2, "60")}

        def h(u):
            if "/galleries/" in u:
                gid = int(u.rstrip("/").rsplit("-", 1)[1])
                n, rating = galleries[gid]
                return reply(pp_gallery(gid, n, rating))
            if "cdni.pornpics.com" in u:
                return reply("IMG:" + u)
            for key, body in sorted(pages.items(), key=lambda kv: -len(kv[0])):
                if key in u:
                    return reply(body)
            return reply(pp_listing([]))
        return h

    def test_downloads_every_picture_in_each_gallery(self):
        h = self.handler({"?q=blonde": pp_listing([1001, 1002])})
        items, urls, log, http, got = fetch("pornpics", "blonde", h, limit=50)
        self.assertEqual(len(items), 5)
        self.assertTrue(all(i.post_id.startswith("pnp_") for i in items))
        self.assertTrue(any("/?q=blonde" in u for u in urls))

    def test_limit_counts_pictures(self):
        h = self.handler({"?q=blonde": pp_listing([1001, 1002])})
        items, *_ = fetch("pornpics", "blonde", h, limit=4)
        self.assertEqual(len(items), 4)

    def test_min_rating_skips_whole_galleries(self):
        h = self.handler({"?q=blonde": pp_listing([1001, 1002])})
        items, urls, log, http, got = fetch("pornpics", "blonde score:>=80", h, limit=50)
        self.assertEqual(len(items), 3)
        self.assertTrue(any("skipped a gallery rated 60" in m for _, m in log))
        self.assertFalse(any("score" in u for u in urls))

    def test_skip_ids_and_single_gallery_link(self):
        h = self.handler()
        items, *_ = fetch("pornpics", "https://www.pornpics.com/galleries/some-set-1001/", h, limit=50,
                          skip={"pnp_1001_1001_001_ab1"})
        self.assertEqual(len(items), 2)

    def test_next_page_found_by_trying_the_usual_addresses(self):
        pages = {"/?q=blonde": pp_listing([1001]), "/?q=blonde&limit=20&offset=20": pp_listing([1002, 1001])}
        h = self.handler(pages)
        items, urls, log, http, got = fetch("pornpics", "blonde", h, limit=50)
        self.assertEqual(len(items), 5)                     # 1001 once, 1002 once
        self.assertTrue(any("page 2" in m for _, m in log))

    def test_runs_out_cleanly(self):
        h = self.handler({"?q=blonde": pp_listing([1001])})
        items, urls, log, http, got = fetch("pornpics", "blonde", h, limit=50)
        self.assertEqual(len(items), 3)
        self.assertTrue(any("search is used up" in m for _, m in log))

    def test_tags_are_read_and_the_guard_applies(self):
        def h(u):
            if "/galleries/" in u:
                return reply(pp_gallery(1001, 2, tags=("Blonde", "Underage")))
            return reply(pp_listing([1001])) if "q=" in u else reply("IMG" + u)
        items, *_ = fetch("pornpics", "blonde", h, limit=10)
        self.assertEqual(items, [])                          # a blocked tag keeps the gallery out

    def test_search_failure_is_logged(self):
        def h(u):
            raise err(u, 503)
        items, urls, log, http, got = fetch("pornpics", "blonde", h)
        self.assertEqual(items, [])
        self.assertTrue(any(l == "error" for l, _ in log))


class Babehub(unittest.TestCase):
    def handler(self, pages):
        def h(u):
            if "cdn.babehub.com" in u:
                return reply("IMG:" + u)
            gid = u.rstrip("/").rsplit("-", 1)[-1]
            if u.rstrip("/").split("/")[-1].startswith("some-title-"):
                return reply(bh_gallery(gid, 2, likes=int(gid) % 1000))
            for key, body in sorted(pages.items(), key=lambda kv: -len(kv[0])):
                if key in u:
                    return reply(body)
            return reply(bh_listing([]))
        return h

    def test_pictures_and_tag_links_are_not_mistaken_for_galleries(self):
        h = self.handler({"/search/post/blonde/": bh_listing([1500, 1600])})
        items, urls, log, http, got = fetch("babehub", "blonde", h, limit=50)
        self.assertEqual(len(items), 4)
        self.assertTrue(all(i.post_id.startswith("bbh_") for i in items))
        self.assertFalse(any("/tag/" in u for u in urls))

    def test_min_likes(self):
        h = self.handler({"/search/post/blonde/": bh_listing([1500, 1600])})        # likes = 500 and 600
        items, *_ = fetch("babehub", "blonde score:>=550", h, limit=50)
        self.assertEqual(len(items), 2)

    def test_page_two_follows_the_next_button(self):
        h = self.handler({"/search/post/blonde/": bh_listing([1500], "https://www.babehub.com/search/post/blonde/mpage/2/"),
                           "/search/post/blonde/mpage/2/": bh_listing([1600])})
        items, urls, log, http, got = fetch("babehub", "blonde", h, limit=50)
        self.assertEqual(len(items), 4)

    def test_page_two_without_a_button_uses_mpage(self):
        h = self.handler({"/search/post/blonde/": bh_listing([1500]), "/search/post/blonde/mpage/2/": bh_listing([1600])})
        items, *_ = fetch("babehub", "blonde", h, limit=50)
        self.assertEqual(len(items), 4)

    def test_real_saved_results_page(self):
        import os, glob
        from sources.gallery_sites import BabehubSource
        src = glob.glob(os.path.expanduser("~/.claude/uploads/*/*TransBabehub.html"))
        if not src:
            self.skipTest("saved page not available")
        with open(src[0], encoding="utf-8") as fh:
            raw = fh.read()
        b = BabehubSource()
        self.assertGreater(len(b._gallery_links(raw)), 20)
        self.assertEqual(b._next_link(raw), "https://www.babehub.com/search/post/Trans/mpage/2/")

    def test_randomize_still_downloads_everything(self):
        h = self.handler({"/search/post/blonde/": bh_listing([1500, 1600, 1700])})
        items, *_ = fetch("babehub", "blonde", h, limit=50, randomize=True)
        self.assertEqual(len(items), 6)


class Registered(unittest.TestCase):
    def test_in_every_list(self):
        from core.source_registry import SOURCE_REGISTRY
        from core.source_groups import grouped
        from core import quality_map
        from sources import SOURCE_BY_ID, grouped_sources
        for sid in ("pornpics", "babehub"):
            self.assertIn(sid, SOURCE_REGISTRY)
            self.assertIn(sid, SOURCE_BY_ID)
            self.assertTrue(quality_map.supported(sid))
            self.assertIn(sid, [i for _g, ids in grouped(list(SOURCE_REGISTRY)) for i in ids])
        self.assertEqual(SOURCE_BY_ID["pornpics"].resolve("site", "80"), {"query_suffix": "score:>=80"})


if __name__ == "__main__":
    unittest.main()


class FinderList(unittest.TestCase):
    def test_every_registered_site_is_searchable_or_excluded_on_purpose(self):
        from core import preset_finder
        from core.source_registry import SOURCE_REGISTRY
        listed = {s for s, _ in preset_finder.FINDER_SITES}
        self.assertEqual(set(SOURCE_REGISTRY) - listed - preset_finder.NOT_SEARCHABLE, set())
        self.assertEqual(listed - set(SOURCE_REGISTRY), set())

    def test_suggest_only_lists_words_the_site_has_results_for(self):
        import threading
        from unittest import mock
        from core import netlog
        import urllib.request
        from sources.gallery_sites import PornPicsSource

        def run(body):
            with mock.patch("time.sleep"), mock.patch.object(netlog, "_orig_urlopen", lambda req, timeout=15: reply(body)):
                urllib.request.urlopen = netlog._wrapped
                return PornPicsSource.suggest("blonde")
        self.assertEqual([e["value"] for e in run(pp_listing([1001]))], ["blonde"])
        self.assertEqual(run(pp_listing([])), [])

    def test_suggest_says_how_many_galleries_were_listed(self):
        from unittest import mock
        from core import netlog
        import urllib.request
        from sources.gallery_sites import PornPicsSource, BabehubSource

        def run(cls, body):
            with mock.patch("time.sleep"), mock.patch.object(netlog, "_orig_urlopen", lambda req, timeout=15: reply(body)):
                urllib.request.urlopen = netlog._wrapped
                return cls.suggest("blonde")[0]["label"]
        self.assertIn("3 galleries", run(PornPicsSource, pp_listing([1, 2, 3])))
        self.assertNotIn("+", run(PornPicsSource, pp_listing([1, 2, 3])))
        self.assertIn("20+ galleries", run(PornPicsSource, pp_listing(range(1, 21))))
        self.assertIn("2+ galleries", run(BabehubSource, bh_listing([1, 2], "https://www.babehub.com/search/post/blonde/mpage/2/")))
        self.assertNotIn("+", run(BabehubSource, bh_listing([1, 2])))
