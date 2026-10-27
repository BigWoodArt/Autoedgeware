"""Pornhub Photos: album search -> photo pages -> large stills."""
import unittest

from tests._net import fetch, reply

LISTING = '<a href="/album/9001">album</a>'
ALBUM = '<a href="/photo/1001">x</a>'
PHOTO = 'https://ei.phncdn.com/pics/albums/x/original_1001.(m=e-yaaGqaq)foo.jpg'


class PornhubImages(unittest.TestCase):
    def test_fetch_album_search(self):
        def handler(url):
            if "/albums/search" in url:
                return reply(LISTING)
            if "/album/9001" in url:
                return reply(ALBUM)
            if "/photo/1001" in url:
                return reply(PHOTO)
            return reply(b"\xff\xd8\xff" + url.encode()[-20:])

        items, *_ = fetch("pornhub_images", "sexy", handler, limit=3)
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0].post_id.startswith("phi_"))

    def test_registered(self):
        from sources import SOURCE_BY_ID
        self.assertIn("pornhub_images", SOURCE_BY_ID)
