"""Per-preset download caps: python -m unittest tests.test_media_caps"""
import os
import tempfile
import unittest

from core import media_caps as mc
from core.scheduler import PresetWorker
from ae_settings.preset import Preset


def touch(folder, *names):
    for n in names:
        with open(os.path.join(folder, n), "wb") as f:
            f.write(b"x")


class Caps(unittest.TestCase):
    def test_settings(self):
        self.assertEqual(mc.caps_from_settings({}), {"images": 500, "videos": 500, "audio": 50})
        self.assertEqual(mc.caps_from_settings({"max_images_per_preset": "7", "max_audio_per_preset": "x"})["images"], 7)
        self.assertEqual(mc.caps_from_settings({"max_audio_per_preset": "x"})["audio"], 50)

    def test_counts_everything_in_the_folder(self):
        d = tempfile.mkdtemp()
        touch(d, "reddit__a.jpg", "b__reddit.png", "reddit__v.mp4", "redgifs__c.jpg", "gelbooru__v2.webm", ".hidden.jpg",
              "soundgasm__s.m4a", "half.tmp", "notes.txt")
        self.assertEqual(mc.count_for_folder(d), {"images": 3, "videos": 2, "audio": 1})      # all sites together
        self.assertEqual(mc.count_for_folder(os.path.join(d, "missing")), {"images": 0, "videos": 0, "audio": 0})

    def test_a_big_pool_from_one_site_blocks_every_site(self):
        d = tempfile.mkdtemp()
        touch(d, *[f"reddit__{i}.mp4" for i in range(5)])
        caps = {"images": 500, "videos": 3, "audio": 50}
        blocked = mc.blocked_kinds(mc.count_for_folder(d), caps)
        self.assertEqual(blocked, {"video"})
        self.assertEqual(mc.plan(blocked, mc.site_kinds("GIFs & Video")), (False, {"image"}))       # redgifs etc. still get images only

    def test_blocked_and_plan(self):
        caps = {"images": 2, "videos": 0, "audio": 1}
        self.assertEqual(mc.blocked_kinds({"images": 2, "videos": 999, "audio": 0}, caps), {"image"})
        both = mc.site_kinds("Image boards")
        self.assertEqual(mc.plan({"image"}, both), (False, {"video"}))
        self.assertEqual(mc.plan({"image", "video"}, both), (True, None))
        self.assertEqual(mc.plan(set(), both), (False, None))
        self.assertEqual(mc.plan({"audio"}, mc.site_kinds("Audio")), (True, None))
        self.assertEqual(mc.plan({"image"}, mc.site_kinds("Audio")), (False, None))
        self.assertEqual(mc.plan({"video"}, mc.site_kinds("Videos")), (True, None))      # a video-only site is skipped
        self.assertEqual(mc.plan({"image"}, mc.site_kinds("Videos")), (False, None))
        self.assertEqual(mc.plan({"audio"}, both), (False, None))      # audio from a picture site: item filter only


class Fake:
    category = "Image boards"
    seen = {}

    def __init__(self):
        pass

    def fetch(self, **kw):
        Fake.seen = {"wanted": getattr(self, "wanted_types", None)}
        return []


class Wiring(unittest.TestCase):
    def worker(self, caps, d):
        p = Preset(name="t", sources=[{"source_type": "fake", "query": "x"}])
        logs = []
        w = PresetWorker(p, {"fake": Fake}, os.path.dirname(d), None, on_log=lambda m, l="info": logs.append(m), caps=caps)
        return w, logs

    def test_full_site_is_skipped_and_partial_is_filtered(self):
        d = tempfile.mkdtemp()
        touch(d, "fake__a.jpg", "fake__b.jpg", "fake__c.mp4")
        w, logs = self.worker({"images": 2, "videos": 5, "audio": 0}, d)
        Fake.seen = {}
        w._fetch_one_source({"source_type": "fake", "query": "x"}, d)
        self.assertEqual(Fake.seen["wanted"], {"video"})
        w, logs = self.worker({"images": 2, "videos": 1, "audio": 0}, d)
        Fake.seen = {}
        self.assertEqual(w._fetch_one_source({"source_type": "fake", "query": "x"}, d), [])
        self.assertEqual(Fake.seen, {})
        self.assertTrue(any("cap" in m for m in logs))

    def test_no_caps_changes_nothing(self):
        d = tempfile.mkdtemp()
        touch(d, "fake__a.jpg")
        w, _ = self.worker({}, d)
        w._fetch_one_source({"source_type": "fake", "query": "x"}, d)
        self.assertIsNone(Fake.seen["wanted"])


if __name__ == "__main__":
    unittest.main()
