"""Autoedgeware-only: the pure logic behind the v0.10.10 window changes."""
import json
import os
import random
import re
import tempfile
import time
import unittest
from pathlib import Path

from ae_settings.preset import Preset
from ae_settings.preset_io import export_preset, import_presets
from ae_settings.wizard_logic import build_sources, clean_subreddit, safe_name, split_list
from core import custom_intensity
from core.friendly import friendly
from core.panic_users import PANIC_USERS
from core.pool_stats import count_media, status_line
from core.preset_pick import pick_preset
from core.splash_pick import choose_splash, pick_splash

ROOT = Path(__file__).resolve().parent.parent


def touch(folder, name, age=10, size=5):
    p = Path(folder) / name
    p.write_bytes(b"x" * size)
    t = time.time() - age
    os.utime(p, (t, t))
    return p


class PoolStats(unittest.TestCase):
    def test_counts_by_type_and_ignores_hidden_and_temp(self):
        with tempfile.TemporaryDirectory() as d:
            for n in ("a.jpg", "b.PNG", "c.gif", "d.mp4", "e.webm", "f.mp3", ".seen_post_ids.json", "g.jpg.tmp", "h.txt"):
                touch(d, n)
            self.assertEqual(count_media(d), (3, 2, 1))
        self.assertEqual(count_media("/no/such/folder"), (0, 0, 0))

    def test_status_lines(self):
        self.assertEqual(status_line((0, 0, 0), False, False), "Ready.")
        self.assertIn("first files", status_line((0, 0, 0), True, False))
        self.assertIn("1 image, 2 videos, 0 audio", status_line((1, 2, 0), True, True))
        self.assertIn("finished", status_line((5, 0, 0), False, True))
        self.assertEqual(status_line((9, 9, 9), True, True, 125), "Paused. Popups come back in 2:05.")


class Splash(unittest.TestCase):
    def test_only_finished_gif_jpg_png(self):
        with tempfile.TemporaryDirectory() as d:
            touch(d, "fresh.jpg", age=0)          # maybe still downloading
            touch(d, "empty.png", size=0)
            touch(d, "clip.mp4")
            touch(d, "ok.gif")
            got = pick_splash([d], check=lambda p: True)
            self.assertEqual(got.name, "ok.gif")

    def test_skips_broken_files_and_returns_none_when_nothing_opens(self):
        with tempfile.TemporaryDirectory() as d:
            touch(d, "bad.jpg")
            self.assertIsNone(pick_splash([d], check=lambda p: False))
            self.assertIsNone(pick_splash([d + "/nope"], check=lambda p: True))

    def test_choice_is_random_across_files(self):
        with tempfile.TemporaryDirectory() as d:
            for n in range(6):
                touch(d, f"{n}.jpg")
            seen = {pick_splash([d], rng=random.Random(s), check=lambda p: True).name for s in range(30)}
            self.assertGreater(len(seen), 2)

    def test_waits_then_uses_first_image_that_arrives(self):
        class Root:
            def __init__(self): self.calls = []
            def after(self, ms, fn): self.calls.append(ms); fn()
        answers = iter([None, None, Path("first.jpg")])
        got = []
        root = Root()
        choose_splash(root, ["x"], "default.png", lambda p, pooled: got.append((str(p), pooled)),
                      picker=lambda folders: next(answers))
        self.assertEqual(got, [("first.jpg", True)])
        self.assertEqual(len(root.calls), 2)

    def test_falls_back_to_default_after_timeout(self):
        class Root:
            def after(self, ms, fn): fn()
        got = []
        choose_splash(Root(), ["x"], "default.png", lambda p, pooled: got.append((str(p), pooled)),
                      timeout_ms=2000, poll_ms=500, picker=lambda folders: None)
        self.assertEqual(got, [("default.png", False)])


class Friendly(unittest.TestCase):
    def test_info_is_quiet_and_problems_are_plain(self):
        self.assertIsNone(friendly("[1/25] downloaded: thing", "info"))
        self.assertIn("slow down", friendly("[HTTP 429] Rate limited by Reddit, waiting 60s...", "warning"))
        self.assertIn("web pages", friendly("[RealBooru] API request failed (...) - falling back to HTML scrape", "warning"))
        self.assertIn("Log tab", friendly("something odd happened", "error"))


class Wizard(unittest.TestCase):
    def test_lists_and_names(self):
        self.assertEqual(split_list("a, b,, A\n c"), ["a", "b", "c"])
        self.assertEqual(clean_subreddit("r/aww/"), "aww")
        self.assertEqual(clean_subreddit("https://reddit.com/r/aww"), "aww")
        self.assertEqual(safe_name('a/b:c*?'), "abc")
        self.assertEqual(safe_name("  "), "My Preset")

    def test_reddit_uses_subreddits_and_others_use_keywords(self):
        src = build_sources("cats, dogs", "aww", ["reddit", "realbooru"])
        self.assertEqual([(s["source_type"], s["query"]) for s in src],
                         [("reddit", "aww"), ("realbooru", "cats"), ("realbooru", "dogs")])

    def test_nothing_usable_is_an_error(self):
        with self.assertRaises(ValueError):
            build_sources("", "aww", ["realbooru"])
        with self.assertRaises(ValueError):
            build_sources("cats", "", ["reddit"])
        with self.assertRaises(ValueError):
            build_sources("cats", "aww", [])


class PresetIO(unittest.TestCase):
    def test_round_trip_and_name_clash(self):
        p = Preset(name="Mine", sources=[{"source_type": "reddit", "query": "aww", "limit": 5, "quality": "Good"}])
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "p.json")
            export_preset(p, path)
            found, skipped = import_presets(path, ["Mine"], {"reddit"})
        self.assertEqual(skipped, 0)
        self.assertEqual(found[0].name, "Mine (2)")
        self.assertEqual(found[0].sources, p.sources)

    def test_untrusted_files(self):
        with tempfile.TemporaryDirectory() as d:
            def write(obj, name="x.json"):
                path = os.path.join(d, name)
                Path(path).write_text(obj if isinstance(obj, str) else json.dumps(obj), encoding="utf-8")
                return path
            with self.assertRaises(ValueError):
                import_presets(write("not json"), [])
            with self.assertRaises(ValueError):
                import_presets(write({"hello": 1}), [])
            with self.assertRaises(ValueError):
                import_presets(write({"autoedgeware_preset": 1, "preset": {"name": "x", "sources": [{"source_type": "evil", "query": "q"}]}}),
                               [], {"reddit"})
            weird = {"autoedgeware_preset": 1, "preset": {
                "name": "../../etc/x", "interval_seconds": -5, "limit": "many", "extra": "ignored",
                "sources": [{"source_type": "reddit", "query": "ok", "limit": 99999}, {"source_type": 5}, "junk"]}}
            found, skipped = import_presets(write(weird), [], {"reddit"})
            self.assertEqual(skipped, 2)
            self.assertEqual(found[0].name, "etcx")
            self.assertEqual((found[0].interval_seconds, found[0].limit), (300, 30))
            self.assertNotIn("limit", found[0].sources[0])


class CustomIntensity(unittest.TestCase):
    def test_defaults_parse_clean(self):
        raw = {k: custom_intensity.to_display(k, v) for k, v in custom_intensity.DEFAULTS.items()}
        values, errors = custom_intensity.parse(raw)
        self.assertEqual(errors, [])
        self.assertEqual(values["delay"], 3000)           # seconds shown, milliseconds stored
        self.assertEqual(values["corruptionMode"], 1)

    def test_bad_input_is_explained(self):
        _, errors = custom_intensity.parse({"delay": "fast", "popupMod": "150", "vidMod": "-1"})
        self.assertEqual(len(errors), 3)
        self.assertTrue(all(":" in e for e in errors))

    def test_build_cfg_keeps_base_and_leaves_our_own_key_out(self):
        values, _ = custom_intensity.parse({"delay": "2.5", "corruptionMode": False})
        cfg = custom_intensity.build_cfg({"audioMod": 77, "delay": 1}, values)
        self.assertEqual((cfg["delay"], cfg["audioMod"], cfg["corruptionMode"]), (2500, 50, 0))
        self.assertNotIn("speedup_percent", cfg)


class OnePreset(unittest.TestCase):
    def test_argument_then_last_used_then_first(self):
        a, b = Preset(name="A"), Preset(name="B")
        self.assertIs(pick_preset([a, b], {"last_preset": "A"}, ["x", "--preset", "B"]), b)
        self.assertIs(pick_preset([a, b], {"last_preset": "B"}, ["x"]), b)
        self.assertIs(pick_preset([a, b], {}, ["x"]), a)
        self.assertIs(pick_preset([a, b], {"last_preset": "gone"}, ["x"]), a)
        self.assertIsNone(pick_preset([], {}, ["x"]))


class PanicPatch(unittest.TestCase):
    def test_every_module_with_its_own_panic_is_patched(self):
        """Edgeware modules that do `from panic import panic` keep a private copy, so each must be in
        PANIC_USERS or a panic key would still close the whole app."""
        src = ROOT / "edgeware_core" / "src"
        users = {"panic"}
        for path in src.rglob("*.py"):
            rel = path.relative_to(src)
            if rel.parts[0] == "config" or rel.name in ("main_config.py", "main_edgeware.py", "panic.py"):
                continue    # the config window and entry points never run inside Autoedgeware
            text = path.read_text(encoding="utf-8")
            if re.search(r"^from panic import .*\bpanic\b", text, re.M):
                users.add(".".join(rel.with_suffix("").parts))
        self.assertEqual(users, set(PANIC_USERS))


if __name__ == "__main__":
    unittest.main()


class CountText(unittest.TestCase):
    def test_wording(self):
        from core.pool_stats import count_text
        self.assertEqual(count_text((11, 200, 5)), "11 images, 200 videos, 5 audio already downloaded")
        self.assertEqual(count_text((1, 1, 0)), "1 image, 1 video, 0 audio already downloaded")
        self.assertEqual(count_text((0, 0, 0)), "Nothing downloaded yet for this preset.")


class MovingPopups(unittest.TestCase):
    def test_presets_never_move_and_custom_offers_it(self):
        from gui.theme import INTENSITY_PRESETS
        self.assertTrue(all(b["movingChance"] == 0 for _n, b in INTENSITY_PRESETS))
        keys = [f[0] for f in custom_intensity.FIELDS]
        self.assertIn("movingChance", keys)
        self.assertIn("movingSpeed", keys)
        values, errors = custom_intensity.parse({"movingChance": "25", "movingSpeed": "9"})
        self.assertEqual((values["movingChance"], values["movingSpeed"]), (25, 9))
        self.assertEqual(custom_intensity.DEFAULTS["movingChance"], 0)
        _, errors = custom_intensity.parse({"movingSpeed": "0"})
        self.assertEqual(len(errors), 1)
