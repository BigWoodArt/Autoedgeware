"""Autoedgeware-only: Hypno mode rules."""
import random
import unittest

from core import hypno_logic as h


class Rate(unittest.TestCase):
    def test_rate(self):
        self.assertAlmostEqual(h.image_rate(4000, 60), 9.0)
        self.assertAlmostEqual(h.image_rate(1000, 100), 60.0)
        self.assertEqual(h.image_rate(4000, 0), 0.0)
        self.assertEqual(h.image_rate(0, 50), 0.0)

    def test_level_grows_with_speed_and_is_off_with_no_popups(self):
        self.assertEqual(h.level(0.0), 0.0)
        self.assertEqual(h.level(0.2), 0.0)
        lows = [h.level(r) for r in (1, 3, 9, 20, 40, 100)]
        self.assertEqual(lows, sorted(lows))
        self.assertEqual(h.level(40), 1.0)
        self.assertEqual(h.level(500), 1.0)
        self.assertGreater(h.level(1), 0)

    def test_opacity_never_exceeds_25_percent(self):
        for lvl in (0, 0.3, 0.7, 1, 5):
            self.assertLessEqual(h.opacity(lvl), 0.20)
            self.assertGreaterEqual(h.opacity(lvl), h.MIN_OPACITY)
        self.assertEqual(h.opacity(1), 0.20)
        self.assertLess(h.opacity(0.2), h.opacity(0.8))

    def test_spiral_speed_range(self):
        self.assertEqual(h.speed(0), h.MIN_SPEED)
        self.assertEqual(h.speed(1), h.MAX_SPEED)
        self.assertLess(h.speed(0.2), h.speed(0.9))


class Decide(unittest.TestCase):
    def test_off_cases(self):
        self.assertEqual(h.decide(False, False, 0.5, 0, 100, False), "off")     # switched off
        self.assertEqual(h.decide(True, True, 0.5, 0, 100, True), "off")        # stopped / paused
        self.assertEqual(h.decide(True, False, 0.0, 0, 100, True), "off")       # no image popups (hibernating)

    def test_new_then_update_then_new_again(self):
        self.assertEqual(h.decide(True, False, 0.5, 10, 0, False), "new")
        self.assertEqual(h.decide(True, False, 0.5, 10, 500, True), "update")
        self.assertEqual(h.decide(True, False, 0.5, 600, 500, True), "new")


class Pick(unittest.TestCase):
    def test_avoids_the_last_one_and_covers_everything(self):
        rng = random.Random(1)
        names = ["a", "b", "c", "d"]
        seen, last = set(), None
        for _ in range(200):
            last_before = last
            last = h.pick(names, last, rng)
            self.assertNotEqual(last, last_before)
            seen.add(last)
        self.assertEqual(seen, set(names))

    def test_single_choice_and_empty(self):
        self.assertEqual(h.pick(["only"], "only"), "only")
        self.assertIsNone(h.pick([]))

    def test_change_time_is_in_range(self):
        for seed in range(20):
            t = h.next_change_time(1000, random.Random(seed))
            self.assertTrue(1000 + h.CHANGE_MIN_S <= t <= 1000 + h.CHANGE_MAX_S)


if __name__ == "__main__":
    unittest.main()
