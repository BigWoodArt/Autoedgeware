"""Alt+click blacklist: blacklisted files are never downloaded or shown again. Offline."""
import os
import tempfile
import unittest

from ae_settings.preset import Preset
from core import blacklist
from core.display_queue import DisplayQueue
from core.scheduler import PresetWorker
from tests.test_scheduler_glue import GOOD, make_source


def worker(root, bl, source_cls, name="p"):
    preset = Preset(name=name, sources=[{"source_type": "fake", "query": "q"}], limit=10)
    logs, queue = [], DisplayQueue()
    w = PresetWorker(preset, {"fake": source_cls}, root, queue, blacklist_dir=bl,
                     on_log=lambda m, l="info": logs.append(m))
    return w, queue, logs


def one_pass(w, seen):
    dest = w.preset.media_dir(w.media_root)
    w._refresh_blacklist(seen)
    w._run_one_source_and_publish(w.preset.sources[0], dest, seen, {"flag": False})
    return dest


class Names(unittest.TestCase):
    def test_walks_subfolders(self):
        with tempfile.TemporaryDirectory() as bl:
            os.makedirs(os.path.join(bl, "Pack"))
            open(os.path.join(bl, "Pack", "a.jpg"), "w").close()
            self.assertEqual(blacklist.names(bl), {"a.jpg"})
            self.assertEqual(blacklist.names(os.path.join(bl, "nope")), set())


class Scheduler(unittest.TestCase):
    def test_blacklisted_post_is_not_downloaded_in_any_preset(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as bl:
            Fake = make_source([("a", GOOD), ("b", GOOD)])
            w1, q1, _ = worker(root, bl, Fake, "one")
            dest1 = one_pass(w1, set())
            self.assertEqual(Fake.downloads, 2)
            # Alt+click on a.jpg: Edgeware moves it into the blacklist folder
            os.makedirs(os.path.join(bl, "UnnamedPack"))
            os.replace(os.path.join(dest1, "fake__a.jpg"), os.path.join(bl, "UnnamedPack", "fake__a.jpg"))
            # a different preset with an empty seen list: 'a' must still be skipped before downloading
            Fake2 = make_source([("a", GOOD), ("b", GOOD)])
            w2, q2, logs = worker(root, bl, Fake2, "two")
            dest2 = one_pass(w2, set())
            self.assertEqual(Fake2.downloads, 1)
            self.assertFalse(os.path.exists(os.path.join(dest2, "fake__a.jpg")))
            self.assertTrue(any("blacklisted post" in m for m in logs))

    def test_download_with_a_blacklisted_name_is_deleted(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as bl:
            open(os.path.join(bl, "a.jpg"), "w").close()          # no post-id record at all
            Fake = make_source([("a", GOOD), ("b", GOOD)])
            w, queue, logs = worker(root, bl, Fake)
            seen = set()
            dest = one_pass(w, seen)
            self.assertFalse(os.path.exists(os.path.join(dest, "a.jpg")))
            self.assertTrue(os.path.exists(os.path.join(dest, "fake__b.jpg")))
            self.assertEqual(len(queue), 1)
            self.assertIn("a", seen)                               # not tried again next cycle
            self.assertTrue(any("skipped a blacklisted file" in m for m in logs))

    def test_restoring_a_file_lifts_the_block(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as bl:
            Fake = make_source([("a", GOOD)])
            w, queue, _ = worker(root, bl, Fake)
            one_pass(w, set())
            self.assertEqual(blacklist.names(bl), set())
            self.assertEqual(Fake.downloads, 1)


class PopupMove(unittest.TestCase):
    def test_same_file_blacklisted_twice_does_not_raise(self):
        src = open(os.path.join(os.path.dirname(__file__), "..", "edgeware_core", "src", "features", "popup.py"),
                   encoding="utf-8").read()
        self.assertIn("os.remove(target)", src)


if __name__ == "__main__":
    unittest.main()
