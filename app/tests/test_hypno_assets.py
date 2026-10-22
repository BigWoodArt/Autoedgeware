"""Autoedgeware-only: the generated spirals and binaural beats are what they claim to be."""
import os
import tempfile
import unittest
import wave
from pathlib import Path

from core import hypno_assets as a

ROOT = Path(__file__).resolve().parent.parent
REAL_VIDEO = (a.VIDEO_CYCLE_FRAMES, a.VIDEO_CYCLES, a.VIDEO_FPS)
REAL_LEVELS = dict(a.LEVELS)
REAL_FFMPEG_OK = a.ffmpeg_ok


def setUpModule():
    a.LEVELS["s"] = (160, 90)         # shape checks do not need the real sizes, and the real ones are slow to draw
    a.LEVELS["m"] = (640, 360)
    a.LEVELS["l"] = (640, 360)
    a.VIDEO_CYCLE_FRAMES, a.VIDEO_CYCLES, a.VIDEO_FPS = 6, 2, 30     # short clips: the real ones are tested in Video
    a.ffmpeg_ok = lambda: False       # the GIF path by default (fast); the Video tests switch ffmpeg back on


def tearDownModule():
    a.LEVELS.update(REAL_LEVELS)
    a.VIDEO_CYCLE_FRAMES, a.VIDEO_CYCLES, a.VIDEO_FPS = REAL_VIDEO
    a.ffmpeg_ok = REAL_FFMPEG_OK


class RealSize(unittest.TestCase):
    def test_sizes_are_sharp_enough_for_their_screens(self):
        s_, m, l = REAL_LEVELS["s"], REAL_LEVELS["m"], REAL_LEVELS["l"]
        self.assertGreaterEqual(m[0], 1280)
        self.assertGreaterEqual(l[0], 2560)
        self.assertTrue(all(w * 9 == h * 16 for w, h in (s_, m, l)))       # 16:9 like the screen

    def test_size_follows_the_widest_screen(self):
        self.assertEqual(a.pick_tier([1920, 1080]), "m")
        self.assertEqual(a.pick_tier([1920, 2560]), "l")
        self.assertEqual(a.pick_tier([]), "m")
        self.assertEqual(a.levels_up_to("l"), ["s", "m", "l"])
        self.assertEqual(a.levels_up_to("m"), ["s", "m"])
        self.assertEqual(a.tier_of("x/spiral_tri3_l_v5.gif"), "l")
        self.assertEqual(a.tier_of("x/spiral_tri3_s_v5.gif"), "s")


def crossings(samples):
    """Number of upward zero crossings = number of whole cycles."""
    return sum(1 for x, y in zip(samples, samples[1:]) if x < 0 <= y)


class Beats(unittest.TestCase):
    def test_left_and_right_differ_by_the_beat_frequency(self):
        import struct
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "b.wav")
            a.make_beat(path, 200, 6)
            with wave.open(path, "rb") as w:
                self.assertEqual((w.getnchannels(), w.getsampwidth(), w.getframerate()), (2, 2, a.BEAT_RATE))
                self.assertEqual(w.getnframes(), a.BEAT_RATE * a.BEAT_SECONDS)
                raw = w.readframes(w.getnframes())
        samples = struct.unpack("<%dh" % (len(raw) // 2), raw)
        left, right = samples[0::2], samples[1::2]
        seconds = a.BEAT_SECONDS
        self.assertAlmostEqual(crossings(left) / seconds, 200, delta=1)
        self.assertAlmostEqual(crossings(right) / seconds, 206, delta=1)

    def test_loop_has_no_jump_at_the_seam(self):
        import struct
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "b.wav")
            a.make_beat(path, 150, 3)
            with wave.open(path, "rb") as w:
                raw = w.readframes(w.getnframes())
        samples = struct.unpack("<%dh" % (len(raw) // 2), raw)
        left = samples[0::2]
        step = max(abs(left[i + 1] - left[i]) for i in range(0, 2000))
        self.assertLess(abs(left[-1] - left[0]), step * 2 + 1)      # last sample runs smoothly into the first

    def test_all_beat_frequencies_fit_whole_cycles_in_the_loop(self):
        for name, carrier, beat in a.BEATS:
            self.assertEqual((carrier * a.BEAT_SECONDS) % 1, 0, name)
            self.assertEqual(((carrier + beat) * a.BEAT_SECONDS) % 1, 0, name)
            self.assertTrue(2 <= beat <= 12, name)
        self.assertGreaterEqual(len(a.BEATS), 4)


class Spirals(unittest.TestCase):
    def test_one_spiral_is_a_black_and_white_loop(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "s.gif")
            a.make_spiral(path, 3, "arch", 2.0, 0.5, +1)
            im = Image.open(path)
            self.addCleanup(im.close)
            self.assertEqual(im.size, a.LEVELS["m"])
            self.assertEqual(im.n_frames, a.FRAMES)
            self.assertEqual(im.info.get("loop"), 0)                  # loops forever
            im.seek(0)
            first = im.convert("L")
            values = {v for v in first.getdata()}
            self.assertLessEqual(len(values), 16)
            self.assertIn(0, values)
            self.assertIn(255, values)                                 # black and white both present
            share_white = sum(1 for v in first.getdata() if v > 128) / (a.LEVELS["m"][0] * a.LEVELS["m"][1])
            self.assertTrue(0.3 < share_white < 0.7, share_white)
            im.seek(10)
            self.assertNotEqual(list(im.convert("L").getdata())[:5000], list(first.getdata())[:5000])   # it turns

    def test_variations_exist_and_are_distinct(self):
        self.assertGreaterEqual(len(a.SPIRALS), 6)
        self.assertEqual(len({s[1:] for s in a.SPIRALS}), len(a.SPIRALS))     # no two identical settings
        self.assertEqual(len(set(a.SPIRAL_NAMES)), len(a.SPIRAL_NAMES))
        self.assertTrue({-1, +1} <= {s[5] for s in a.SPIRALS})                 # both turning directions


class Ensure(unittest.TestCase):
    def test_makes_everything_once_and_redoes_empty_files(self):
        with tempfile.TemporaryDirectory() as d:
            folder = os.path.join(d, "hypno_assets")
            a.ensure_assets(folder)
            spirals, beats = a.available(folder)
            self.assertEqual(spirals, a.SPIRAL_NAMES)
            self.assertEqual(a.available(folder, "m")[0], a.SPIRAL_NAMES)
            self.assertFalse(os.path.exists(a.spiral_path(folder, a.SPIRAL_NAMES[0], "l")))   # the big size was not asked for
            self.assertEqual(beats, a.BEAT_NAMES)
            first = os.path.getmtime(a.beat_path(folder, a.BEAT_NAMES[0]))
            open(a.spiral_path(folder, a.SPIRAL_NAMES[0], "m"), "wb").close()      # a broken, empty file
            a.ensure_assets(folder)
            self.assertGreater(os.path.getsize(a.spiral_path(folder, a.SPIRAL_NAMES[0], "m")), 1000)
            self.assertEqual(os.path.getmtime(a.beat_path(folder, a.BEAT_NAMES[0])), first)   # left alone


if __name__ == "__main__":
    unittest.main()


class SpiralReachesEdges(unittest.TestCase):
    def test_corners_have_arms(self):
        import tempfile
        from PIL import Image
        for name, arms, shape, turns, width, direction in a.SPIRALS:
            with tempfile.TemporaryDirectory() as d:
                path = os.path.join(d, "s.gif")
                a.make_spiral(path, arms, shape, turns, width, direction)
                with Image.open(path) as im:
                    for frame in (0, a.FRAMES // 2):
                        im.seek(frame)
                        g = im.convert("L")
                        for box in ((0, 0, 60, 60), (580, 0, 640, 60), (0, 300, 60, 360), (580, 300, 640, 360)):
                            data = list(g.crop(box).getdata())
                            share = sum(1 for v in data if v > 128) / len(data)
                            self.assertTrue(0.05 < share < 0.95, (name, frame, box, share))


class OldRevisions(unittest.TestCase):
    def test_old_files_are_removed_and_current_ones_never_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            for old in ("spiral_tri3.gif", "spiral_tri3_hd.gif", "spiral_tri3_m_v1.gif", "spiral_revision_hd.txt"):
                open(os.path.join(d, old), "wb").close()
            a.ensure_assets(d, None, "m")
            names = os.listdir(d)
            self.assertFalse([n for n in names if n in ("spiral_tri3.gif", "spiral_tri3_hd.gif", "spiral_tri3_m_v1.gif",
                                                         "spiral_revision_hd.txt")])
            mine = a.spiral_path(d, a.SPIRAL_NAMES[0], "m")
            before = os.path.getmtime(mine)
            a.ensure_assets(d, None, "m")
            self.assertEqual(os.path.getmtime(mine), before)


if __name__ == "__main__":
    unittest.main()


class SpiralReachesEdges(unittest.TestCase):
    def test_corners_have_arms(self):
        import tempfile
        from PIL import Image
        for name, arms, shape, turns, width, direction in a.SPIRALS:
            with tempfile.TemporaryDirectory() as d:
                path = os.path.join(d, "s.gif")
                a.make_spiral(path, arms, shape, turns, width, direction)
                with Image.open(path) as im:
                    for frame in (0, a.FRAMES // 2):
                        im.seek(frame)
                        g = im.convert("L")
                        for box in ((0, 0, 60, 60), (580, 0, 640, 60), (0, 300, 60, 360), (580, 300, 640, 360)):
                            data = list(g.crop(box).getdata())
                            share = sum(1 for v in data if v > 128) / len(data)
                            self.assertTrue(0.05 < share < 0.95, (name, frame, box, share))


class Background(unittest.TestCase):
    def test_generator_script_makes_files_in_its_own_process(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as d:
            folder = os.path.join(d, "h")
            done = subprocess.run([sys.executable, str(ROOT / "core" / "hypno_gen.py"), folder, "s"],
                                  capture_output=True, timeout=300)
            self.assertEqual(done.returncode, 0, done.stderr[-300:])
            spirals, beats = a.available(folder, "s")
            self.assertEqual(len(spirals), len(a.SPIRAL_NAMES))


class Quick(unittest.TestCase):
    def test_first_spiral_is_there_fast_and_sharper_ones_replace_it(self):
        import time
        with tempfile.TemporaryDirectory() as d:
            folder = os.path.join(d, "h")
            t = time.time()
            a.ensure_first(folder)
            self.assertLess(time.time() - t, 10)
            spirals, beats = a.available(folder, "l")
            self.assertEqual(spirals, [a.SPIRAL_NAMES[0]])               # one spiral, small, playable now
            self.assertEqual(len(beats), len(a.BEAT_NAMES))
            self.assertTrue(a.best_spiral(folder, a.SPIRAL_NAMES[0], "l").endswith(f"_s_v{a.SPIRAL_REVISION}.gif"))
            a.ensure_level(folder, "m")
            self.assertTrue(a.best_spiral(folder, a.SPIRAL_NAMES[0], "l").endswith(f"_m_v{a.SPIRAL_REVISION}.gif"))   # sharper wins
            self.assertTrue(a.best_spiral(folder, a.SPIRAL_NAMES[1], "l").endswith(f"_m_v{a.SPIRAL_REVISION}.gif"))

    def test_second_launch_needs_no_drawing(self):
        with tempfile.TemporaryDirectory() as d:
            folder = os.path.join(d, "h")
            a.ensure_assets(folder, None, "m")
            before = {n: os.path.getmtime(os.path.join(folder, n)) for n in os.listdir(folder)}
            a.ensure_assets(folder, None, "m")
            after = {n: os.path.getmtime(os.path.join(folder, n)) for n in os.listdir(folder)}
            self.assertEqual(before, after)


import json
import subprocess


@unittest.skipUnless(REAL_FFMPEG_OK(), "ffmpeg not installed")
class Video(unittest.TestCase):
    """Sharper spiral sizes as H.264 video (real frame counts), and the fall back to GIF."""

    def setUp(self):
        self._saved = (a.ffmpeg_ok, a.VIDEO_CYCLE_FRAMES, a.VIDEO_CYCLES, a.VIDEO_FPS)
        a.ffmpeg_ok = REAL_FFMPEG_OK
        a.VIDEO_CYCLE_FRAMES, a.VIDEO_CYCLES, a.VIDEO_FPS = REAL_VIDEO

    def tearDown(self):
        a.ffmpeg_ok, a.VIDEO_CYCLE_FRAMES, a.VIDEO_CYCLES, a.VIDEO_FPS = self._saved

    @staticmethod
    def info(path):
        out = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
                                       "-show_entries", "stream=nb_read_frames,width,height,codec_name,pix_fmt",
                                       "-of", "json", path])
        return json.loads(out)["streams"][0]

    @staticmethod
    def frame(path, n, out):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-vf", "select=eq(n\\,%d)" % n, "-vframes", "1", out],
                       check=True)
        from PIL import Image
        return Image.open(out).convert("L")

    def test_video_has_the_right_shape_and_repeats_exactly(self):
        from PIL import ImageChops, ImageStat
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "s.mp4")
            a.make_spiral_video(path, 3, "arch", 2.0, 0.5, 1, (320, 180))
            i = self.info(path)
            self.assertEqual((i["codec_name"], i["pix_fmt"], i["width"], i["height"]), ("h264", "yuv420p", 320, 180))
            self.assertEqual(int(i["nb_read_frames"]), a.VIDEO_CYCLE_FRAMES * a.VIDEO_CYCLES)
            f0 = self.frame(path, 0, os.path.join(d, "f0.png"))
            again = self.frame(path, a.VIDEO_CYCLE_FRAMES, os.path.join(d, "fc.png"))
            self.assertEqual(ImageStat.Stat(ImageChops.difference(f0, again)).mean[0], 0.0)     # the turns join exactly
            near = self.frame(path, 1, os.path.join(d, "f1.png"))
            self.assertGreater(ImageStat.Stat(ImageChops.difference(f0, near)).mean[0], 0.5)    # and it does move

    def test_odd_sizes_work(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "o.mp4")
            a.make_spiral_video(path, 2, "arch", 3.0, 0.5, -1, (321, 181), cycle_frames=4, cycles=2)
            self.assertEqual(self.info(path)["width"], 320)

    def test_level_m_is_video_and_s_stays_gif(self):
        with tempfile.TemporaryDirectory() as d:
            logs = []
            a.ensure_level(d, "s", names=["tri3"], log=logs.append)
            a.ensure_level(d, "m", names=["tri3"], log=logs.append)
            self.assertTrue(os.path.isfile(a.spiral_path(d, "tri3", "s", ".gif")))
            self.assertTrue(os.path.isfile(a.spiral_path(d, "tri3", "m", ".mp4")))
            self.assertFalse(os.path.exists(a.spiral_path(d, "tri3", "m", ".gif")))
            self.assertTrue(a.best_spiral(d, "tri3", "m").endswith(".mp4"))
            self.assertEqual(a.tier_of(a.best_spiral(d, "tri3", "m")), "m")
            self.assertTrue(any("video" in m for m in logs))
            self.assertFalse([n for n in os.listdir(d) if n.endswith((".part", ".turn.mp4"))])

    def test_falls_back_to_gif_when_ffmpeg_is_missing_or_fails(self):
        with tempfile.TemporaryDirectory() as d:
            a.ffmpeg_ok = lambda: False
            a.ensure_level(d, "m", names=["tri3"])
            self.assertTrue(os.path.isfile(a.spiral_path(d, "tri3", "m", ".gif")))
        with tempfile.TemporaryDirectory() as d:
            a.ffmpeg_ok = REAL_FFMPEG_OK
            logs = []
            real = a.make_spiral_video

            def broken(*args, **kw):
                with open(args[0], "wb") as f:
                    f.write(b"half")
                raise RuntimeError("encoder exploded")
            a.make_spiral_video = broken
            try:
                a.ensure_level(d, "m", names=["tri3"], log=logs.append)
            finally:
                a.make_spiral_video = real
            self.assertTrue(os.path.isfile(a.spiral_path(d, "tri3", "m", ".gif")))
            self.assertFalse(os.path.exists(a.spiral_path(d, "tri3", "m", ".mp4")))
            self.assertFalse([n for n in os.listdir(d) if n.endswith(".part")])
            self.assertTrue(any("using a GIF" in m for m in logs))

    def test_video_beats_gif_at_the_same_size_and_cleanup_keeps_it(self):
        with tempfile.TemporaryDirectory() as d:
            for ext in (".gif", ".mp4"):
                with open(a.spiral_path(d, "tri3", "m", ext), "wb") as f:
                    f.write(b"x")
            self.assertTrue(a.best_spiral(d, "tri3", "m").endswith(".mp4"))
            with open(os.path.join(d, "spiral_tri3_m_v1.mp4"), "wb") as f:
                f.write(b"x")
            a.ensure_beats(d)
            a.ensure_assets(d, None, "s")
            names = os.listdir(d)
            self.assertIn(os.path.basename(a.spiral_path(d, "tri3", "m", ".mp4")), names)
            self.assertNotIn("spiral_tri3_m_v1.mp4", names)


if __name__ == "__main__":
    unittest.main()
