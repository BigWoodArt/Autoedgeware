"""The scheduler gives every fetch a Stop button and a size limit (core/netlog.py DownloadControl)."""
import threading
import unittest
from unittest import mock

from core import netlog
from tests._net import reply


class Control(unittest.TestCase):
    def read_with(self, ctl, payload, headers=None):
        def fake(req, timeout=15):
            r = reply(payload)
            r.headers = headers or {}
            return r
        with mock.patch.object(netlog, "_orig_urlopen", fake):
            netlog.set_control(ctl)
            try:
                return netlog._wrapped(mock.Mock(full_url="https://x/f")).read()
            finally:
                netlog.clear_control()

    def test_normal_download_passes_through(self):
        ctl = netlog.DownloadControl(threading.Event(), threading.Event(), 10 * 1048576)
        self.assertEqual(self.read_with(ctl, b"abc" * 1000), b"abc" * 1000)

    def test_stop_interrupts(self):
        stop = threading.Event()
        stop.set()
        with self.assertRaises(netlog.DownloadInterrupted):
            self.read_with(netlog.DownloadControl(stop, threading.Event(), 0), b"abc")

    def test_file_over_the_limit_is_refused(self):
        ctl = netlog.DownloadControl(threading.Event(), threading.Event(), 1048576)
        with self.assertRaises(netlog.DownloadInterrupted):
            self.read_with(ctl, b"x" * 3 * 1048576, {"Content-Length": str(3 * 1048576), "Content-Type": "video/mp4"})

    def test_pmvhaven_cap_is_higher_than_the_rest(self):
        from core.scheduler import MAX_DOWNLOAD_MB, PMVHAVEN_DOWNLOAD_MB, download_cap_bytes
        self.assertEqual(download_cap_bytes("reddit"), MAX_DOWNLOAD_MB * 1048576)
        self.assertEqual(download_cap_bytes("pmvhaven"), PMVHAVEN_DOWNLOAD_MB * 1048576)
        self.assertGreater(PMVHAVEN_DOWNLOAD_MB, MAX_DOWNLOAD_MB)

    def test_scheduler_wires_it(self):
        from pathlib import Path
        src = (Path(__file__).parent.parent / "core" / "scheduler.py").read_text(encoding="utf-8")
        self.assertIn("netlog.set_control(netlog.DownloadControl(self.stop_event", src)
        self.assertIn("netlog.clear_control()", src)


if __name__ == "__main__":
    unittest.main()
