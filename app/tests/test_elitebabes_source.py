"""EliteBabes: WP REST tag -> posts -> CDN image URLs."""
import json
import unittest

from tests._net import fetch, reply


def _tags():
    return json.dumps([{"id": 9, "slug": "beautiful", "count": 100}])


def _posts():
    body = (
        "https://www.elitebabes.com/content/2024/01/photo_a.jpg , "
        "https://www.elitebabes.com/content/2024/01/2024-01_w200.jpg , "
        "https://www.elitebabes.com/content/2024/01/photo_b.jpg"
    )
    return json.dumps([{"title": {"rendered": "Set one"}, "content": {"rendered": body}}])


class EliteBabes(unittest.TestCase):
    def test_fetch_tag(self):
        def handler(url):
            if "/tags?" in url:
                return reply(_tags())
            if "/posts?" in url:
                return reply(_posts())
            return reply(b"\xff\xd8\xff" + url.encode()[-24:])

        items, *_ = fetch("elitebabes", "beautiful", handler, limit=10)
        self.assertEqual(len(items), 2)

    def test_posts_from_wp_filters_thumbs(self):
        from sources.elitebabes_source import posts_from_wp
        posts = posts_from_wp(json.loads(_posts()))
        urls = [p["url"] for p in posts]
        self.assertEqual(len(urls), 2)
        self.assertTrue(all("cdn.elitebabes.com" in u for u in urls))
        self.assertFalse(any("_w200" in u for u in urls))

    def test_registered(self):
        from sources import SOURCE_BY_ID
        self.assertEqual(SOURCE_BY_ID["elitebabes"].prefix, "eb_")
