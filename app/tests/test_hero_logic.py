"""Hero mode rules (no Tk, no sound). python -m unittest discover tests"""
import random
import unittest

from core import hero_logic as h


def seq(seed=1, **cfg):
    return h.Sequencer(h.clean_config(cfg), random.Random(seed))


class Config(unittest.TestCase):
    def test_clamped_and_text_tolerated(self):
        c = h.clean_config({"bpm_min": "abc", "bpm_max": 5000, "round_s": "-4", "hold_s": 9999, "frenzy_pct": 250})
        self.assertEqual((c["bpm_min"], c["bpm_max"], c["round_s"], c["hold_s"], c["frenzy_pct"]), (50, 240, 40, 13, 100))

    def test_fastest_stays_above_slowest(self):
        c = h.clean_config({"bpm_min": 120, "bpm_max": 60})
        self.assertGreaterEqual(c["bpm_max"], c["bpm_min"] + 10)

    def test_from_settings(self):
        cfg, text, volume = h.from_settings({"hero_text": False, "hero_click_volume": "70", "hero_bpm_min": 80})
        self.assertEqual((text, volume, cfg["bpm_min"]), (False, 70, 80))


class Timeline(unittest.TestCase):
    def test_first_hit_waits_for_the_circle_to_cross(self):
        events = seq().take_until(60)
        self.assertGreaterEqual(events[0].time, 2.5)

    def test_events_in_order_and_never_repeated(self):
        s = seq()
        a = s.take_until(30)
        b = s.take_until(60)
        times = [e.time for e in a + b]
        self.assertEqual(times, sorted(times))
        self.assertEqual(len(times), len(set(times)))
        self.assertTrue(all(e.time > 30 for e in b))

    def test_hold_is_silent_and_marked(self):
        s = seq(7, frenzy_pct=0, round_s=40, hold_s=8)
        events = s.take_until(300)
        spans = [(a, b) for a, b, p in s.phases if p.hold]
        self.assertTrue(spans)
        for a, b in spans:
            self.assertEqual([e for e in events if a <= e.time < b], [])
            _idx, phase, _off = s.phase_at((a + b) / 2)
            self.assertTrue(phase.hold)

    def test_never_faster_than_the_cap(self):
        s = seq(3, bpm_min=200, bpm_max=240, frenzy_pct=100)
        events = s.take_until(400)
        for i in range(len(events)):
            window = [e for e in events if events[i].time <= e.time < events[i].time + 1.0]
            self.assertLessEqual(len(window), h.MAX_HITS_PER_SECOND + 1)

    def test_popups_are_spaced_and_on_hits(self):
        s = seq(5, frenzy_pct=100)
        events = s.take_until(400)
        popups = [e.time for e in events if e.popup]
        self.assertTrue(popups)
        for a, b in zip(popups, popups[1:]):
            self.assertGreaterEqual(b - a, h.MIN_POPUP_GAP_S - 1e-9)

    def test_build_speeds_up(self):
        s = seq(9, frenzy_pct=0, round_s=120)
        events = s.take_until(400)
        for a, b, p in s.phases:
            if p.name == "build" and p.tokens == h.PATTERNS["steady"][0]:
                inside = [e.time for e in events if a <= e.time < b]
                gaps = [y - x for x, y in zip(inside, inside[1:])]
                self.assertLess(sum(gaps[-5:]) / 5, sum(gaps[:5]) / 5)
                return
        self.skipTest("no plain build in this seed")

    def test_pause_pattern_leaves_a_gap(self):
        s = seq()
        phase = h.Phase("t", "t", 20, 60, 60, h.PATTERNS["three"][0], 2)
        s._make_events(0.0, phase)
        gaps = [round(y.time - x.time, 2) for x, y in zip(s.events, s.events[1:])]
        self.assertIn(2.0, gaps)           # 60 bpm: one beat = 1 s, so three hits then a 2 s gap
        self.assertIn(1.0, gaps)

    def test_phase_order_in_an_arc(self):
        names = [p.name for p in h.make_arc(h.clean_config({"frenzy_pct": 100}), random.Random(2))]
        self.assertEqual(names, ["warmup", "steady", "steady", "build", "build", "frenzy", "hold", "ease"])
        names = [p.name for p in h.make_arc(h.clean_config({"frenzy_pct": 0}), random.Random(2))]
        self.assertNotIn("frenzy", names)


class Frenzy(unittest.TestCase):
    def test_frenzy_is_one_even_beat_after_another(self):
        for seed in range(30):
            arc = h.make_arc(h.clean_config({"frenzy_pct": 100}), random.Random(seed))
            frenzy = next(p for p in arc if p.name == "frenzy")
            self.assertEqual(frenzy.tokens, ["x"])          # no rests, no doubles, no triplets
            self.assertEqual(frenzy.beats_per_popup, 1)

    def test_frenzy_has_no_gaps_in_the_timeline(self):
        s = seq(2, frenzy_pct=100)
        events = s.take_until(400)
        for a, b, p in s.phases:
            if p.name == "frenzy":
                inside = [e.time for e in events if a <= e.time < b]
                gaps = [round(y - x, 3) for x, y in zip(inside, inside[1:])]
                self.assertLessEqual(max(gaps) - min(gaps), 0.1 * max(gaps) + 0.02)   # even spacing (tempo is fixed)
                return
        self.fail("no frenzy made")

    def test_round_adds_up_to_the_setting_with_or_without_frenzy(self):
        for round_s in (40, 120, 300):
            for frenzy in (True, False):
                cfg = h.clean_config({"round_s": round_s, "hold_s": 10})
                arc = h.make_arc(cfg, random.Random(1), frenzy=frenzy)
                self.assertEqual(any(p.name == "frenzy" for p in arc), frenzy)
                self.assertAlmostEqual(sum(p.seconds for p in arc), cfg["round_s"], places=6)
                self.assertEqual([p.seconds for p in arc if p.hold], [cfg["hold_s"]])

    def test_build_says_speed_up(self):
        arc = h.make_arc(h.clean_config({}), random.Random(2), frenzy=False)
        for p in arc:
            self.assertEqual(p.text.startswith("Speed up."), p.name == "build")

    def test_tempo_climbs_round_by_round_then_levels_off(self):
        cfg = h.clean_config({"round_s": 60, "hold_s": 5, "frenzy_pct": 0, "ramp_rounds": 4, "bpm_min": 50, "bpm_max": 140})
        s = h.Sequencer(cfg, random.Random(3))
        s.ensure(60 * 8)
        tops, cur = [], 0
        for a, b, p in s.phases:
            if p.name == "warmup" and cur:
                tops.append(cur); cur = 0
            if p.name == "build":
                cur = max(cur, p.bpm1)
        tops.append(cur)
        self.assertLess(tops[0], tops[1])
        self.assertLess(tops[1], tops[3])
        self.assertAlmostEqual(tops[4], tops[5], delta=tops[4] * 0.12)       # full range from round 5 on (noise only)

    def test_fair_share_of_rounds(self):
        for pct, per_round in ((50, 0.5), (25, 0.25), (100, 1.0), (0, 0.0)):
            s = seq(7, frenzy_pct=pct)
            s.ensure(240 * 40)
            names = [p.name for _, _, p in s.phases]
            rounds = names.count("warmup")
            self.assertGreaterEqual(rounds, 30)
            self.assertAlmostEqual(names.count("frenzy") / rounds, per_round, delta=0.08)

    def test_fifty_percent_never_skips_two_rounds_in_a_row(self):
        for seed in range(20):
            s = seq(seed, frenzy_pct=50)
            s.ensure(240 * 30)
            marks, cur = [], False
            for _, _, p in s.phases:
                if p.name == "warmup":
                    marks.append(cur); cur = False
                if p.name == "frenzy":
                    cur = True
            marks = marks[1:]
            for a, b, c in zip(marks, marks[1:], marks[2:]):
                self.assertTrue(a or b or c)

    def test_neighbouring_patterns_differ(self):
        for seed in range(30):
            arc = h.make_arc(h.clean_config({"frenzy_pct": 0}), random.Random(seed))
            mids = [p.tokens for p in arc if p.name in ("steady", "build")]
            for a, b in zip(mids, mids[1:]):
                self.assertNotEqual(a, b)


class Boundaries(unittest.TestCase):
    def test_no_double_dot_where_a_phase_ends_and_the_next_begins(self):
        checked = 0
        for seed in range(60):
            s = seq(seed, round_s=40, hold_s=5, frenzy_pct=50, bpm_min=50, bpm_max=140)
            events = s.take_until(600)
            for (a, b, p), (c, d, q) in zip(s.phases, s.phases[1:]):
                if p.hold or q.hold:
                    continue
                before = [e.time for e in events if a <= e.time < b]
                after = [e.time for e in events if c <= e.time < d]
                if before and after:
                    checked += 1
                    self.assertGreaterEqual(after[0] - before[-1], 0.3 - 1e-9)
                    beat = 60.0 / max(p.bpm1, 1)
                    self.assertGreaterEqual(after[0] - before[-1], min(0.6 * beat, 0.3) - 1e-9)
        self.assertGreater(checked, 200)


class Upcoming(unittest.TestCase):
    def test_next_phase_is_the_one_after(self):
        s = seq(1, frenzy_pct=0, round_s=40, hold_s=5)
        _i, now_phase, _o = s.phase_at(1.0)
        start, nxt = s.next_phase(1.0)
        self.assertEqual(now_phase.name, "warmup")
        self.assertEqual(nxt.name, "steady")
        self.assertAlmostEqual(start, 2.5 + 7)       # (40 - 5 hold) / 5 shares
        # asking never disturbs what is handed out later
        first = s.take_until(30)
        self.assertEqual([e.time for e in first], sorted(e.time for e in first))


class PopupDelay(unittest.TestCase):
    def test_bounds_and_hold(self):
        slow = h.Phase("a", "a", 10, 30, 30, ["x"], 4)
        fast = h.Phase("b", "b", 10, 240, 240, ["x"], 1)
        self.assertEqual(h.popup_delay_ms(slow, 30), h.POPUP_DELAY_MAX_MS)
        self.assertEqual(h.popup_delay_ms(fast, 240), h.POPUP_DELAY_MIN_MS)
        self.assertEqual(h.popup_delay_ms(h.Phase("h", "Hold.", 5, hold=True), 0), 1000)

    def test_levels_follow_the_phase(self):
        arc = {p.name: p for p in h.make_arc(h.clean_config({"frenzy_pct": 100}), random.Random(4))}
        self.assertGreater(arc["frenzy"].level_at(1), arc["steady"].level_at(1))
        self.assertLess(arc["hold"].level_at(1), arc["warmup"].level_at(1))
        self.assertGreaterEqual(arc["hold"].level_at(1), 0.05)


if __name__ == "__main__":
    unittest.main()


class PaceTests(unittest.TestCase):
    def test_slow_preset_starts_low_fast_preset_starts_high(self):
        slow = h.pace_curve(5000, 120)(0)
        fast = h.pace_curve(1250, 30)(0)
        self.assertEqual(slow, 0.0)
        self.assertGreater(fast, 0.5)

    def test_pace_rises_over_time_and_caps(self):
        f = h.pace_curve(5000, 120, 20)
        self.assertLess(f(0), f(400))
        self.assertLessEqual(f(100000), 1.0)
        self.assertEqual(h.pace_curve(5000, 120, 20, corruption=False)(5000), 0.0)

    def test_scaled_tempo_follows_pace(self):
        cfg = h.clean_config({})
        slow = h.Sequencer(cfg, random.Random(1), pace_fn=lambda t: 0.0)
        fast = h.Sequencer(cfg, random.Random(1), pace_fn=lambda t: 1.0)
        for s in (slow, fast):
            s.ensure(300)
        top = lambda s: max(p.bpm1 for _a, _b, p in s.phases if p.name == "build")
        self.assertLess(top(slow), top(fast))

    def test_hold_and_frenzy_unchanged(self):
        cfg = h.clean_config({"frenzy_pct": 100})
        seq = h.Sequencer(cfg, random.Random(3), pace_fn=lambda t: 0.0)
        seq.ensure(400)
        for _a, _b, p in seq.phases:
            if p.name == "frenzy":
                self.assertEqual(p.bpm0, cfg["bpm_max"])


class PatternsAreDistinct(unittest.TestCase):
    def test_no_two_patterns_are_the_same_rhythm(self):
        def shape(tokens):                       # gaps between hits over one loop, as a repeating ratio, any start
            times = []
            for i, tok in enumerate(tokens):
                for k, ch in enumerate(tok):
                    if ch == "x":
                        times.append(i + k / len(tok))
            loop = len(tokens)
            gaps = [round(b - a, 3) for a, b in zip(times, times[1:] + [times[0] + loop])]
            unit = min(gaps)
            gaps = [round(g / unit, 3) for g in gaps]
            return min(tuple(gaps[i:] + gaps[:i]) for i in range(len(gaps)))
        shapes = [shape(t) for t, _ in h.PATTERNS.values()]
        self.assertEqual(len(shapes), len(set(shapes)))
