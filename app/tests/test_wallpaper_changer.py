"""Autoedgeware-only: wallpaper changer, with a fake desktop."""
import json
import os
import tempfile
import unittest
from pathlib import Path

from core.wallpaper_changer import WallpaperChanger, fits

ROOT = Path(__file__).resolve().parent.parent


class Fits(unittest.TestCase):
    def test_filters(self):
        self.assertTrue(fits(1920, 1080))
        self.assertTrue(fits(1000, 600))
        self.assertTrue(fits(2560, 1440))
        self.assertTrue(fits(1920, 1200))
        self.assertFalse(fits(999, 562))          # too narrow
        self.assertFalse(fits(1080, 1920))        # portrait
        self.assertFalse(fits(1500, 1500))        # square
        self.assertFalse(fits(3000, 1000))        # far too wide
        self.assertFalse(fits(0, 0))


class Fake:
    """A pretend desktop plus clock."""
    def __init__(self, tmp):
        self.tmp = tmp
        self.orig = os.path.join(tmp, "TranscodedWallpaper")
        Path(self.orig).write_bytes(b"ORIGINAL")
        self.current = self.orig
        self.sets = []
        self.now = 1000.0
        self.sizes = {}
        self.media = os.path.join(tmp, "media")
        os.makedirs(self.media)

    def get(self): return self.current
    def set(self, path):
        self.sets.append(path)
        self.current = path
    def clock(self): return self.now
    def size_of(self, path): return self.sizes[os.path.basename(path)]
    def save_copy(self, src, dst_base):
        dst = dst_base + ".jpg"
        Path(dst).write_bytes(Path(src).read_bytes())
        return dst
    def add(self, name, size):
        Path(self.media, name).write_bytes(b"IMG")
        self.sizes[name] = size

    def changer(self, interval=120):
        return WallpaperChanger(lambda: [self.media], os.path.join(self.tmp, "state"), self.get, self.set,
                                interval_s=interval, size_of=self.size_of, save_copy=self.save_copy, clock=self.clock)


class Behaviour(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.f = Fake(self._t.name)

    def tearDown(self):
        self._t.cleanup()

    def test_first_picture_is_not_always_the_same(self):
        import core.wallpaper_changer as wc
        old = wc.MAX_NEW_PER_TICK
        wc.MAX_NEW_PER_TICK = 1                 # a big folder is noted a few files at a time
        try:
            for i in range(30):
                self.f.add(f"w{i:02d}.jpg", (1920, 1080))
            firsts = set()
            for _ in range(12):
                c = self.f.changer(); c.start()
                firsts.add(os.path.basename(c.tick()))
                c.stop()
            self.assertGreater(len(firsts), 1)
        finally:
            wc.MAX_NEW_PER_TICK = old

    def test_saves_original_then_changes_then_restores(self):
        self.f.add("wide.jpg", (1920, 1080))
        c = self.f.changer()
        self.assertTrue(c.start())
        self.assertEqual(Path(c.backup).read_bytes(), b"ORIGINAL")
        self.assertEqual(self.f.sets, [])                       # nothing changed yet
        self.assertTrue(c.tick().endswith("wide.jpg"))
        self.f.current = os.path.join(self.f.media, "wide.jpg")
        Path(self.f.orig).write_bytes(b"OVERWRITTEN BY WINDOWS")   # the cache file drifts: our copy must not
        c.stop()
        self.assertEqual(self.f.sets[-1], c.backup)
        self.assertEqual(Path(self.f.sets[-1]).read_bytes(), b"ORIGINAL")

    def test_only_fitting_images_are_used(self):
        self.f.add("portrait.jpg", (1080, 1920))
        self.f.add("small.png", (800, 450))
        self.f.add("clip.mp4", (1920, 1080))
        c = self.f.changer(); c.start()
        self.assertIsNone(c.tick())
        self.f.add("good.png", (3840, 2160))
        self.assertTrue(c.tick().endswith("good.png"))      # noted as soon as it 'downloads'

    def test_at_most_one_change_per_interval(self):
        self.f.add("a.jpg", (1920, 1080)); self.f.add("b.jpg", (1920, 1080))
        c = self.f.changer(120); c.start()
        self.assertIsNotNone(c.tick())
        self.f.now += 119
        self.assertIsNone(c.tick())
        self.f.now += 2
        second = c.tick()
        self.assertIsNotNone(second)
        self.assertEqual(len(self.f.sets), 2)
        self.assertNotEqual(self.f.sets[0], self.f.sets[1])   # never the same one twice in a row

    def test_cycles_through_everything_before_repeating(self):
        names = [f"w{i}.jpg" for i in range(4)]
        for n in names: self.f.add(n, (1920, 1080))
        c = self.f.changer(1); c.start()
        seen = []
        for _ in range(4):
            seen.append(os.path.basename(c.tick())); self.f.now += 5
        self.assertEqual(sorted(seen), sorted(names))

    def test_stop_is_idempotent_and_does_nothing_if_never_started(self):
        c = self.f.changer()
        c.stop()
        self.assertEqual(self.f.sets, [])
        c.start(); c.stop(); c.stop()
        self.assertEqual(self.f.sets, [c.backup])

    def test_run_again_after_stop_saves_the_wallpaper_as_it_is_then(self):
        self.f.add("w.jpg", (1920, 1080))
        c = self.f.changer(1); c.start(); c.tick(); c.stop()
        self.f.current = self.f.orig
        Path(self.f.orig).write_bytes(b"NEW ORIGINAL")
        self.assertTrue(c.start())
        self.assertEqual(Path(c.backup).read_bytes(), b"NEW ORIGINAL")

    def test_killed_run_keeps_the_true_original(self):
        self.f.add("w.jpg", (1920, 1080))
        c1 = self.f.changer(1); c1.start(); c1.tick()           # ... program killed here, no stop()
        Path(self.f.orig).write_bytes(b"A WALLPAPER OF OURS")     # whatever is 'current' is now ours
        c2 = self.f.changer(1)
        self.assertTrue(c2.start())
        self.assertEqual(Path(c2.backup).read_bytes(), b"ORIGINAL")

    def test_never_touches_the_wallpaper_if_it_cannot_be_saved(self):
        self.f.add("w.jpg", (1920, 1080))
        self.f.current = None
        c = self.f.changer(); 
        self.assertFalse(c.start())
        self.assertIsNone(c.tick())
        self.assertEqual(self.f.sets, [])

    def test_failed_restore_stays_marked_unfinished(self):
        c = self.f.changer(); c.start()
        def boom(path): raise OSError("nope")
        c.set_wallpaper = boom
        c.stop()
        state = json.loads(Path(c._state_path).read_text())
        self.assertTrue(state["active"])


class Wiring(unittest.TestCase):
    def test_every_stop_path_restores(self):
        engine = (ROOT / "run_engine.py").read_text(encoding="utf-8")
        self.assertIn("_panic_module.restore_panic_wallpaper = changer.stop", engine)
        self.assertIn("changer.stop()", engine)                                  # our panic wrapper
        self.assertIn("engine_control.restore_wallpaper(state)", engine)         # exit
        ctl = (ROOT / "core/engine_control.py").read_text(encoding="utf-8")
        self.assertIn("restore_wallpaper(state)", ctl)                           # Stop / pause / embedded panic
        self.assertIn("changer.start()", ctl)                                    # Run again
        gui = (ROOT / "gui/app.py").read_text(encoding="utf-8")
        self.assertIn("engine_control.restore_wallpaper(self._live_state)", gui) # window closed
        self.assertEqual(gui.count("engine_control.resume_popups(self._live_state)"), 2)


if __name__ == "__main__":
    unittest.main()


class EngineControl(unittest.TestCase):
    """Stop / pause / panic / Run reach the changer through engine_control."""
    class Changer:
        def __init__(self): self.calls = []
        def start(self): self.calls.append("start")
        def stop(self): self.calls.append("stop")

    class State:
        audio_players = []
        popups = []

    def make(self):
        from core import engine_control
        st = self.State(); st.ae_wallpaper = self.Changer()
        return engine_control, st

    def test_stop_restores_and_run_starts_again(self):
        ctl, st = self.make()
        ctl.stop_popups(st)
        self.assertEqual(st.ae_wallpaper.calls, ["stop"])
        ctl.resume_popups(st)
        self.assertEqual(st.ae_wallpaper.calls, ["stop", "start"])

    def test_embedded_panic_restores(self):
        ctl, st = self.make()
        ctl.make_embedded_panic()(None, None, st)
        self.assertEqual(st.ae_wallpaper.calls, ["stop"])
        ctl.resume_popups()

    def test_no_changer_is_fine(self):
        from core import engine_control as ctl
        st = self.State()
        ctl.stop_popups(st); ctl.resume_popups(st); ctl.resume_popups(); ctl.restore_wallpaper(None)
