"""Pornhub GIFs: search listing -> data-gif URLs."""
import unittest

from tests._net import fetch, reply

LISTING = '<div data-gif="https://ci.phncdn.com/www-static/gifs/55/55a.gif?hdnea=st%3D1"></div>'


class PornhubGifs(unittest.TestCase):
    def test_fetch_gif_search(self):
        def handler(url):
            if "/gifs/search" in url:
                return reply(LISTING)
            return reply(b"GIF" + url.encode()[-12:])

        items, *_ = fetch("pornhub_gifs", "sexy", handler, limit=5)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].post_id, "phg_55")

    def test_registered(self):
        from sources import SOURCE_BY_ID
        self.assertIn("pornhub_gifs", SOURCE_BY_ID)
