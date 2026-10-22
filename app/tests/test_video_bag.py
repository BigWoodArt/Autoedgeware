"""Autoedgeware-only: watchlist sizing and the video shuffle bag."""
import unittest

from core.video_bag import bag_eligible, watchlist_size


class Size(unittest.TestCase):
    def test_sizes(self):
        self.assertEqual(watchlist_size(0), 20)
        self.assertEqual(watchlist_size(100), 20)
        self.assertEqual(watchlist_size(101), 50)
        self.assertEqual(watchlist_size(400), 50)


class Bag(unittest.TestCase):
    def play(self, files, n, recent_size=3):
        played, recent, order = set(), [], []
        for _ in range(n):
            elig, played = bag_eligible(files, recent, played)
            pick = elig[0]
            order.append(pick)
            played.add(pick)
            recent.append(pick)
            recent[:] = recent[-recent_size:]
        return order

    def test_every_file_plays_once_before_any_repeat(self):
        files = [f"v{i}" for i in range(10)]
        order = self.play(files, 10)
        self.assertEqual(sorted(order), sorted(files))

    def test_new_file_mid_cycle_joins_the_bag(self):
        files = [f"v{i}" for i in range(6)]
        played, recent = {"v0", "v1", "v2"}, ["v2"]
        elig, played = bag_eligible(files + ["new"], recent, played)
        self.assertIn("new", elig)
        self.assertNotIn("v0", elig)

    def test_deleted_file_is_forgotten(self):
        elig, played = bag_eligible(["a", "b"], [], {"a", "gone"})
        self.assertEqual(played, {"a"})
        self.assertEqual(elig, ["b"])

    def test_bag_refills_when_empty_without_back_to_back(self):
        files = ["a", "b", "c", "d"]
        elig, played = bag_eligible(files, ["d"], set(files))
        self.assertEqual(sorted(elig), ["a", "b", "c"])
        self.assertEqual(played, set())

    def test_all_in_watchlist_stays_empty(self):
        elig, _ = bag_eligible(["a", "b"], ["a", "b"], set())
        self.assertEqual(elig, [])


if __name__ == "__main__":
    unittest.main()
