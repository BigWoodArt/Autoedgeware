"""Autoedgeware-only: one fetch at a time per rate-limited site."""
import threading
import time
import unittest

from core import site_slots


class Slots(unittest.TestCase):
    def test_same_limited_site_runs_one_at_a_time(self):
        stop, running, peak, lock = threading.Event(), [0], [0], threading.Lock()

        def work():
            with site_slots.slot("reddit", stop) as got:
                self.assertTrue(got)
                with lock:
                    running[0] += 1
                    peak[0] = max(peak[0], running[0])
                time.sleep(0.05)
                with lock:
                    running[0] -= 1
        threads = [threading.Thread(target=work) for _ in range(4)]
        [t.start() for t in threads]; [t.join() for t in threads]
        self.assertEqual(peak[0], 1)

    def test_different_sites_run_together(self):
        stop = threading.Event()
        with site_slots.slot("reddit", stop) as a:
            self.assertTrue(a)
            started = []
            t = threading.Thread(target=lambda: started.append(site_slots.acquire("redgifs", stop)))
            t.start(); t.join(1)
            self.assertEqual(started, [True])
            site_slots.release("redgifs")

    def test_unlimited_sites_never_wait(self):
        stop = threading.Event()
        for _ in range(3):
            self.assertTrue(site_slots.acquire("realbooru", stop))

    def test_stop_while_waiting_gives_up_and_leaves_the_slot_alone(self):
        stop = threading.Event()
        waits = []
        with site_slots.slot("erome", threading.Event()) as holder:
            self.assertTrue(holder)
            result = []
            t = threading.Thread(target=lambda: result.append(site_slots.acquire("erome", stop, on_wait=lambda: waits.append(1), poll=0.05)))
            t.start(); time.sleep(0.15); stop.set(); t.join(2)
        self.assertEqual(result, [False])
        self.assertEqual(waits, [1])
        self.assertTrue(site_slots.acquire("erome", threading.Event()))   # holder released cleanly
        site_slots.release("erome")


if __name__ == "__main__":
    unittest.main()
