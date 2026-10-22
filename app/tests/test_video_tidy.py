"""Cutting long videos and shrinking popup-only ones, offline (uses the real ffmpeg when it is installed)."""
import os
import subprocess
import tempfile
import unittest

from core import video_tidy as v

RULES = {"max_seconds": 3, "shrink_to": 180, "fs_min_height": 360}


class Plan(unittest.TestCase):
    def test_rules_from_settings(self):
        self.assertEqual(v.rules_from_settings({}), {"max_seconds": 120, "shrink_to": 720, "fs_min_height": 1080})
        r = v.rules_from_settings({"video_max_seconds": "abc", "video_shrink_to_px": 0, "fullscreen_video_min_height": 900})
        self.assertEqual(r, {"max_seconds": 120, "shrink_to": 0, "fs_min_height": 900})

    def test_cut_long_videos_only(self):
        rules = {"max_seconds": 120, "shrink_to": 0, "fs_min_height": 1080}
        self.assertEqual(v.plan(2160, 300, ".mp4", rules), (120, 0))           # a fullscreen candidate is cut, not shrunk
        self.assertEqual(v.plan(2160, 120.5, ".mp4", rules), (0, 0))           # within a second of the limit: leave it
        self.assertEqual(v.plan(480, 60, ".mp4", rules), (0, 0))
        self.assertEqual(v.plan(480, 600, ".webm", rules), (120, 0))
        self.assertEqual(v.plan(480, 600, ".avi", rules), (0, 0))              # a container we do not touch

    def test_shrink_only_what_is_never_fullscreen(self):
        rules = {"max_seconds": 0, "shrink_to": 720, "fs_min_height": 1080}
        self.assertEqual(v.plan(1080, 30, ".mp4", rules), (0, 720))            # popup-only: shrunk
        self.assertEqual(v.plan(2160, 30, ".mp4", rules), (0, 0))              # fullscreen candidate: full quality
        self.assertEqual(v.plan(1081, 30, ".mp4", rules), (0, 0))
        self.assertEqual(v.plan(720, 30, ".mp4", rules), (0, 0))               # already small
        self.assertEqual(v.plan(1080, 30, ".webm", rules), (0, 0))             # webm is only cut, never re-encoded
        self.assertEqual(v.plan(1080, 30, ".mp4", {"max_seconds": 0, "shrink_to": 0, "fs_min_height": 1080}), (0, 0))


@unittest.skipUnless(v.ffmpeg_ready(), "ffmpeg/ffprobe not installed")
class Real(unittest.TestCase):
    def make(self, d, name, w, h, seconds, audio=True):
        path = os.path.join(d, name)
        cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc=size={w}x{h}:rate=10:duration={seconds}"]
        if audio:
            cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}", "-c:a", "aac"]
        cmd += ["-c:v", "libx264", "-g", "5", "-pix_fmt", "yuv420p", path]
        subprocess.run(cmd, check=True)
        return path

    def test_long_video_is_cut_without_re_encoding(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.make(d, "long.mp4", 640, 360, 9)
            logs = []
            self.assertTrue(v.tidy(p, {"max_seconds": 3, "shrink_to": 0, "fs_min_height": 1080}, logs.append))
            h, secs = v.probe(p)
            self.assertEqual(h, 360)
            self.assertAlmostEqual(secs, 3, delta=0.7)
            self.assertTrue(any("cut to 3s" in m for m in logs))
            self.assertEqual(os.listdir(d), ["long.mp4"])

    def test_popup_only_video_is_shrunk_and_keeps_audio(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.make(d, "big.mp4", 640, 360, 2)
            self.assertTrue(v.tidy(p, {"max_seconds": 0, "shrink_to": 180, "fs_min_height": 480}))
            self.assertEqual(v.probe(p)[0], 180)
            streams = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
                                               "-of", "csv=p=0", p], text=True).split()
            self.assertIn("audio", streams)
            self.assertEqual(os.listdir(d), ["big.mp4"])

    def test_fullscreen_candidate_keeps_its_size(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.make(d, "tall.mp4", 640, 360, 2)
            self.assertFalse(v.tidy(p, {"max_seconds": 0, "shrink_to": 180, "fs_min_height": 300}))   # 360 > 300
            self.assertEqual(v.probe(p)[0], 360)

    def test_cut_and_shrink_together(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.make(d, "both.mp4", 640, 360, 8, audio=False)
            self.assertTrue(v.tidy(p, RULES | {"fs_min_height": 480}))
            h, secs = v.probe(p)
            self.assertEqual(h, 180)
            self.assertAlmostEqual(secs, 3, delta=0.5)

    def test_bad_file_and_missing_file_are_left_alone(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "bad.mp4")
            with open(p, "wb") as f:
                f.write(b"not a video at all")
            self.assertFalse(v.tidy(p, RULES))
            with open(p, "rb") as f:
                self.assertEqual(f.read(), b"not a video at all")
            self.assertFalse(v.tidy(os.path.join(d, "none.mp4"), RULES))
            self.assertEqual(os.listdir(d), ["bad.mp4"])

    def test_off_or_no_ffmpeg_changes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.make(d, "x.mp4", 640, 360, 5)
            before = os.path.getsize(p)
            self.assertFalse(v.tidy(p, {"max_seconds": 0, "shrink_to": 0, "fs_min_height": 1080}))
            self.assertFalse(v.tidy(p, {}))
            real = v.ffmpeg_ready
            v.ffmpeg_ready = lambda: False
            try:
                self.assertFalse(v.tidy(p, RULES))
            finally:
                v.ffmpeg_ready = real
            self.assertEqual(os.path.getsize(p), before)


if __name__ == "__main__":
    unittest.main()
