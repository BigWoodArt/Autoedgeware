"""Reddit albums, offline: python -m unittest tests.test_reddit_albums"""
import json
import tempfile
import threading
import unittest
import urllib.request
from unittest import mock

from tests._net import reply
from core import netlog
from core.source_registry import SOURCE_REGISTRY
from ae_sources.reddit_albums import album_from_json

NS = "http://www.w3.org/2005/Atom"


def post_json(ids, extra=None):
    meta = {i: {"status": "valid", "e": "Image", "m": "image/jpg", "s": {"u": f"https://preview.redd.it/{i}.jpg?x=1&amp;y=2"}}
            for i in ids}
    post = {"gallery_data": {"items": [{"media_id": i} for i in ids]}, "media_metadata": meta}
    post.update(extra or {})
    return json.dumps([{"data": {"children": [{"data": post}]}}])


def feed(link_kind="gallery"):
    content = ('&lt;a href="https://www.reddit.com/gallery/abc"&gt;[link]&lt;/a&gt;'
               '&lt;img src="https://preview.redd.it/aaa.jpg?w=1"&gt;')
    return (f'<feed xmlns="{NS}"><entry><title>Album</title><link href="https://www.reddit.com/r/x/comments/abc/album/"/>'
            f'<content type="html">{content}</content></entry></feed>')


def run(handler, limit=5, skip=None, xml=None):
    log, got = [], []
    urls = []

    def fake(req, timeout=15):
        urls.append(req.full_url)
        return handler(req.full_url)
    with mock.patch("time.sleep"), mock.patch.object(netlog, "_orig_urlopen", fake):
        urllib.request.urlopen = netlog._wrapped
        src = SOURCE_REGISTRY["reddit"]()
        src.rate_limiter.min_interval = 0
        items = src.fetch("x", limit, "New", "month", tempfile.mkdtemp(), lambda m, l="info": log.append(m),
                          lambda *a: None, threading.Event(), item_cb=got.append, skip_ids=skip)
    return items, got, urls


class Albums(unittest.TestCase):
    def test_all_pictures_saved_in_order(self):
        def h(u):
            if ".rss" in u:
                return reply(feed())
            if u.endswith(".json?raw_json=1"):
                return reply(post_json(["aaa", "bbb", "ccc"]))
            return reply(b"IMG" + u.encode())
        items, got, urls = run(h)
        self.assertEqual(len(items), 3)
        self.assertEqual(len(got), 3)
        self.assertEqual({i.post_id for i in items}, {"abc"})
        self.assertTrue(any("i.redd.it/bbb.jpg" in u for u in urls))

    def test_json_failure_keeps_first_picture(self):
        def h(u):
            if ".rss" in u:
                return reply(feed())
            if ".json" in u:
                raise OSError("down")
            return reply(b"IMG" + u.encode())
        items, _, _ = run(h)
        self.assertEqual(len(items), 1)

    def test_parse(self):
        pics = album_from_json(post_json(["a1", "b2"]))
        self.assertEqual([c[0][0] for c in pics], ["https://i.redd.it/a1.jpg", "https://i.redd.it/b2.jpg"])
        self.assertEqual(pics[0][1][0], "https://preview.redd.it/a1.jpg?x=1&y=2")     # fallback, unescaped
        self.assertEqual(album_from_json("nonsense"), [])
        self.assertEqual(album_from_json(json.dumps([{"data": {"children": [{"data": {}}]}}])), [])

    def test_animated_and_crosspost(self):
        meta = {"g1": {"status": "valid", "e": "AnimatedImage", "s": {"mp4": "https://preview.redd.it/g1.mp4?a=1&amp;b=2"}}}
        inner = {"gallery_data": {"items": [{"media_id": "g1"}]}, "media_metadata": meta}
        pics = album_from_json(json.dumps([{"data": {"children": [{"data": {"crosspost_parent_list": [inner]}}]}}]))
        self.assertEqual(pics[0][0][3], "video")
        self.assertIn("a=1&b=2", pics[0][0][0])

    def test_cap(self):
        ids = [f"i{n}" for n in range(60)]
        self.assertEqual(len(album_from_json(post_json(ids))), 30)


def rg_feed():
    content = '&lt;a href="https://www.redgifs.com/watch/SlyFox"&gt;[link]&lt;/a&gt;'
    return (f'<feed xmlns="{NS}"><entry><title>Clip</title><link href="https://www.reddit.com/r/x/comments/zz9/clip/"/>'
            f'<content type="html">{content}</content></entry></feed>')


def rg_handler(u):
    if ".rss" in u:
        return reply(rg_feed())
    if "auth/temporary" in u:
        return reply('{"token":"t"}')
    if "/v2/gifs/slyfox" in u:
        return reply('{"gif":{"urls":{"hd":"https://media.redgifs.com/SlyFox.mp4"}}}')
    return reply(b"VID" + u.encode())


class RedgifsDupes(unittest.TestCase):
    def test_reddit_post_marks_redgifs_clip_seen(self):
        seen = set()
        items, _, _ = run(rg_handler, skip=seen)
        self.assertEqual(len(items), 1)
        self.assertIn("rg_slyfox", seen)

    def test_clip_already_from_redgifs_is_skipped(self):
        seen = {"rg_slyfox"}
        items, _, urls = run(rg_handler, skip=seen)
        self.assertEqual(items, [])
        self.assertFalse(any("media.redgifs.com" in u for u in urls))
        self.assertIn("zz9", seen)


if __name__ == "__main__":
    unittest.main()
