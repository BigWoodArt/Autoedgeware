"""Live smoke tests for gallery sources (optional: AUTOEDGEWARE_NET=1)."""
import os
import tempfile
import threading
import unittest

from sources import SOURCE_BY_ID

# (site_id, query) — queries the user asked to verify
SMOKE = [
    ("pictoa", "latex"),
    ("pictoa", "glamour-494"),
    ("elitebabes", "beautiful"),
    ("elitebabes", "captions"),
    ("porngif", "latex"),
    ("porngif", "captions"),
    ("pornhub_gifs", "latex"),
    ("pornhub_gifs", "captions"),
    ("pornhub_images", "latex"),
    ("pornhub_images", "beautiful"),
    ("pornpics", "latex"),
    ("pornpics", "beautiful"),
    ("sexcom_pics", "latex"),
    ("sexcom_gifs", "latex"),
]
# WP API returns no posts for these words today; scraper still handles them without crashing.
OPTIONAL_EMPTY = {("elitebabes", "captions")}


@unittest.skipUnless(os.environ.get("AUTOEDGEWARE_NET"), "set AUTOEDGEWARE_NET=1 for live gallery smoke")
class GalleryNetSmoke(unittest.TestCase):
    def test_each_source_downloads_at_least_one(self):
        for site, query in SMOKE:
            with self.subTest(site=site, query=query):
                cls = SOURCE_BY_ID[site]
                src = cls()
                log = []
                items = src.fetch(
                    query, 2, None, None, tempfile.mkdtemp(),
                    lambda m, l="info": log.append((l, m)),
                    lambda *a: None,
                    threading.Event(),
                )
                if not items and (site, query) in OPTIONAL_EMPTY:
                    continue
                self.assertGreater(len(items), 0, [m for _, m in log if "failed" in m.lower() or "0 item" in m])
