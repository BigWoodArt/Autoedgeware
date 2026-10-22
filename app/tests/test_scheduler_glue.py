"""Autoedgeware-specific tests (NOT part of the shared scraper set): how core/scheduler.py drives the
shared sources. Offline.   python -m unittest discover tests"""
import io
import json
import os
import tempfile
import unittest
import urllib.error
import urllib.request
from unittest import mock

from ae_settings.preset import Preset
from core import netlog
from core.display_queue import DisplayQueue
from core.media_item import MediaItem
from core.scheduler import PresetWorker, ScrapeScheduler


def make_source(files, seen_queries=None, http=None):
    """A stand-in source. files = [(post_id, bytes)]. Honours skip_ids/item_cb like the real ones."""
    class Fake:
        downloads = 0
        manifest_at_landing = []

        def __init__(self, **kw):
            pass

        def fetch(self, query, limit, sort, time_range, dest_dir, log, progress, stop_event,
                  early_preview_cb=None, randomize=False, prioritize_images=False,
                  item_cb=None, skip_ids=None):
            if seen_queries is not None:
                seen_queries.append(query)
            if http:
                http()
            out = []
            for pid, data in files:
                if skip_ids and pid in skip_ids:
                    continue
                path = os.path.join(dest_dir, f"{pid}.jpg")
                with open(path, "wb") as f:
                    f.write(data)
                Fake.downloads += 1
                item = MediaItem(file_path=path, caption=pid, media_type="image", post_id=pid, source_type="fake")
                out.append(item)
                if item_cb:
                    item_cb(item)
                    mpath = os.path.join(dest_dir, ".source_manifest.json")
                    if os.path.exists(mpath):
                        with open(mpath) as f:
                            Fake.manifest_at_landing.append(json.load(f).get(f"fake__{pid}.jpg"))
            return out
    return Fake


GOOD = b"\xff\xd8\xff\xe0 pretend jpeg"


class Glue(unittest.TestCase):
    def worker(self, root, source_cls, source_type="fake", query="q"):
        preset = Preset(name="p", sources=[{"source_type": source_type, "query": query}], limit=10)
        self.queue, self.logs = DisplayQueue(), []
        return PresetWorker(preset, {source_type: source_cls}, root, self.queue,
                            on_log=lambda m, l="info": self.logs.append((l, m)))

    def run_once(self, w, seen=None):
        dest = w.preset.media_dir(w.media_root)
        seen = w._load_seen() if seen is None else seen
        w._run_one_source_and_publish(w.preset.sources[0], dest, seen, {"flag": False})
        return dest, seen

    # ---- skip_ids / item_cb (v0.10.1) ----
    def test_second_cycle_downloads_nothing_and_source_known_at_landing(self):
        Fake = make_source([("a", GOOD), ("b", GOOD), ("c", GOOD)])
        with tempfile.TemporaryDirectory() as root:
            w = self.worker(root, Fake)
            dest, seen = self.run_once(w)
            self.assertEqual(Fake.downloads, 3)
            self.assertEqual(Fake.manifest_at_landing, ["fake"] * 3)   # named while fetch() was still running
            self.assertEqual(len(self.queue), 3)
            self.run_once(w, seen)
            self.assertEqual(Fake.downloads, 3)                        # nothing re-downloaded
            self.assertEqual(len(self.queue), 3)                       # nothing re-queued
            w2 = self.worker(root, Fake)                               # app restart: persisted seen file
            self.run_once(w2)
            self.assertEqual(Fake.downloads, 3)

    # ---- smallest picture ----
    def test_tiny_pictures_are_dropped_and_not_fetched_again(self):
        from PIL import Image
        import io as _io

        def png(w, h):
            b = _io.BytesIO()
            Image.new("RGB", (w, h), "red").save(b, "PNG")
            return b.getvalue()
        Fake = make_source([("tiny", png(120, 400)), ("big", png(800, 600))])
        with tempfile.TemporaryDirectory() as root:
            w = self.worker(root, Fake)
            w.min_image_px = 300
            dest, seen = self.run_once(w)
            self.assertFalse(any("tiny" in n for n in os.listdir(dest)))
            self.assertTrue(os.path.exists(os.path.join(dest, "fake__big.jpg")))
            self.assertIn("tiny", seen)
            self.assertEqual(len(self.queue), 1)
            w.min_image_px = 0                      # off: everything stays
            Fake2 = make_source([("tiny2", png(10, 10))])
            w2 = self.worker(root, Fake2)
            w2.min_image_px = 0
            dest, _ = self.run_once(w2, set())
            self.assertTrue(os.path.exists(os.path.join(dest, "fake__tiny2.jpg")))

    def test_long_new_videos_are_cut_on_arrival(self):
        import shutil
        import subprocess
        if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
            self.skipTest("no ffmpeg")
        from core import video_tidy
        with tempfile.TemporaryDirectory() as root:
            clip = os.path.join(root, "src.mp4")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=10:duration=8",
                            "-c:v", "libx264", "-g", "5", "-pix_fmt", "yuv420p", clip], check=True)
            data = open(clip, "rb").read()

            class Vid:
                def __init__(self, **kw):
                    pass

                def fetch(self, query, limit, sort, time_range, dest_dir, log, progress, stop_event,
                          early_preview_cb=None, randomize=False, prioritize_images=False,
                          item_cb=None, skip_ids=None):
                    path = os.path.join(dest_dir, "clip.mp4")
                    with open(path, "wb") as f:
                        f.write(data)
                    item = MediaItem(file_path=path, caption="c", media_type="video", post_id="v1", source_type="fake")
                    item_cb(item)
                    return [item]
            w = self.worker(root, Vid)
            w.video_rules = {"max_seconds": 3, "shrink_to": 0, "fs_min_height": 1080}
            dest, _ = self.run_once(w)
            self.assertAlmostEqual(video_tidy.probe(os.path.join(dest, "fake__clip.mp4"))[1], 3, delta=0.7)
            self.assertTrue(any("cut to 3s" in m for _, m in self.logs))

    def test_unreadable_picture_is_kept(self):
        from core import min_size
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.jpg")
            open(p, "wb").write(GOOD)
            self.assertFalse(min_size.image_too_small(p, 300))
            self.assertFalse(min_size.image_too_small(os.path.join(d, "missing.jpg"), 300))
        self.assertEqual(min_size.from_settings({}), 300)
        self.assertEqual(min_size.from_settings({"min_image_px": "abc"}), 300)
        self.assertEqual(min_size.from_settings({"min_image_px": 0}), 0)

    # ---- error pages saved as media (sync 2026.09.30.1) ----
    def test_error_page_download_is_discarded_and_not_recorded(self):
        Fake = make_source([("bad", b"<!doctype html><html>Rate limited</html>"), ("empty", b""), ("ok", GOOD)])
        with tempfile.TemporaryDirectory() as root:
            w = self.worker(root, Fake)
            dest, seen = self.run_once(w)
            self.assertFalse(os.path.exists(os.path.join(dest, "bad.jpg")))
            self.assertFalse(os.path.exists(os.path.join(dest, "empty.jpg")))
            self.assertTrue(os.path.exists(os.path.join(dest, "fake__ok.jpg")))
            self.assertEqual(seen, {"ok"})            # rejected posts stay retryable
            self.assertEqual(len(self.queue), 1)
            with open(os.path.join(dest, ".source_manifest.json")) as f:
                self.assertEqual(list(json.load(f)), ["fake__ok.jpg"])
            self.assertEqual(sum("error page" in m for _, m in self.logs), 2)

    # ---- pasted-URL cleanup (sync 2026.09.30.1) ----
    def test_pasted_url_is_cleaned_before_fetch(self):
        cases = [("reddit", "https://www.reddit.com/r/aww/", "aww"),
                 ("soundgasm", "https://soundgasm.net/u/SomeUser/some-slug", "SomeUser"),
                 ("reddit", "aww", "aww")]                # plain text is left alone
        for source_type, typed, expected in cases:
            with self.subTest(typed=typed):
                got = []
                Fake = make_source([], seen_queries=got)
                with tempfile.TemporaryDirectory() as root:
                    w = self.worker(root, Fake, source_type=source_type, query=typed)
                    self.run_once(w)
                self.assertEqual(got, [expected])

    # ---- netlog: installed by the scheduler, failed calls logged (sync 2026.09.30.1) ----
    def test_scheduler_start_installs_the_retry_wrapper(self):
        urllib.request.urlopen = netlog._orig_urlopen
        netlog._installed = False
        ScrapeScheduler(tempfile.gettempdir()).start([], {})
        self.assertIs(urllib.request.urlopen, netlog._wrapped)

    def test_failed_and_retried_requests_are_logged_but_successes_are_not(self):
        def err(url, code, body):
            return urllib.error.HTTPError(url, code, "x", {}, io.BytesIO(body))
        script = {"https://ok.test/": [("ok", b"fine")],
                  "https://gone.test/x": [("err", 404, b"<html>no such page</html>")],
                  "https://flaky.test/": [("err", 503, b"busy"), ("ok", b"fine")]}

        def fake(req, timeout=15):
            step = script[req.full_url].pop(0)
            if step[0] == "err":
                raise err(req.full_url, step[1], step[2])
            r = io.BytesIO(step[1])
            r.status, r.getcode = 200, (lambda: 200)
            r.__enter__, r.__exit__ = (lambda: r), (lambda *a: False)
            return r

        def hit_the_network():
            for url in script.copy():
                try:
                    urllib.request.urlopen(urllib.request.Request(url)).read()
                except urllib.error.HTTPError:
                    pass

        Fake = make_source([("a", GOOD)], http=hit_the_network)
        with tempfile.TemporaryDirectory() as root, mock.patch("time.sleep"), \
                mock.patch.object(netlog, "_orig_urlopen", fake):
            urllib.request.urlopen = netlog._wrapped
            self.run_once(self.worker(root, Fake))
        text = "\n".join(m for l, m in self.logs if l == "warning")
        self.assertIn("http 404", text)
        self.assertIn("no such page", text)              # the site's reply text is kept
        self.assertIn("http 503", text)
        self.assertIn("retr", text)                      # the call that only worked after a retry
        self.assertNotIn("ok.test", text)                # plain successes stay out of the log


if __name__ == "__main__":
    unittest.main()
