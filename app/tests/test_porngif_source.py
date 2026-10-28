"""PornGIF: search HTML -> gif URLs."""
import unittest

from tests._net import fetch, reply


class PornGif(unittest.TestCase):
    def test_fetch_search(self):
        html = '<a href="https://porngif.xxx/gif/42.gif">x</a><img src="/gif/99.gif">'

        def handler(url):
            if "?s=" in url or url.endswith("porngif.xxx/"):
                return reply(html)
            return reply(b"GIF" + url.encode()[-8:])

        items, *_ = fetch("porngif", "sexy", handler, limit=10)
        self.assertEqual(len(items), 2)

    def test_registered(self):
        from sources import SOURCE_BY_ID
        self.assertEqual(SOURCE_BY_ID["porngif"].prefix, "pgf_")
