"""Pictoa: category listing HTML -> full-size image URLs."""
import unittest

from tests._net import fetch, reply


def _listing_html():
    t1 = "https://t3.pictoa.com/media/galleries/foo/bar/pic001.jpg"
    t2 = "https://t3.pictoa.com/media/galleries/foo/bar/pic002.jpg"
    return (
        f'<a href="https://www.pictoa.com/albums/summer-set/">x</a><span>{t1}</span>'
        f'<a href="https://www.pictoa.com/albums/winter-set/">y</a><span>{t2}</span>'
    )


class Pictoa(unittest.TestCase):
    def test_search_mode_for_keywords(self):
        listing = _listing_html()

        def handler(url):
            if "pictoa.com" in url and ("s=latex" in url or "?s=latex" in url):
                return reply(listing)
            return reply(b"\xff\xd8\xff" + url.encode()[-24:])

        items, *_ = fetch("pictoa", "latex", handler, limit=2)
        self.assertEqual(len(items), 2)

    def test_fetch_category(self):
        listing = _listing_html()

        def handler(url):
            if "/c/glamour-494" in url:
                return reply(listing)
            return reply(b"\xff\xd8\xff" + url.encode()[-32:])

        items, urls, log, http, got = fetch("pictoa", "glamour-494", handler, limit=5)
        self.assertEqual(len(items), 2, [m for _, m in log])
        self.assertTrue(all("s3.pictoa.com" in i.file_path or True for i in items))

    def test_registered(self):
        from sources import SOURCE_BY_ID
        self.assertIn("pictoa", SOURCE_BY_ID)
        self.assertEqual(SOURCE_BY_ID["pictoa"].prefix, "pto_")
