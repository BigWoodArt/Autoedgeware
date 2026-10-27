"""Ranged HTTP download helper."""
import unittest
from unittest import mock

from sources.http_bytes import download_ranged, probe_byte_size


class HttpBytes(unittest.TestCase):
    def test_download_ranged_joins_chunks(self):
        url = "https://cdn.example/big.gif"
        total = 5
        calls = []

        def fake_urlopen(req, timeout=60):
            calls.append(req.headers.get("Range"))
            m = req.headers.get("Range", "").split("-")
            start = int(m[0].split("=")[1])
            end = int(m[1])
            data = bytes(range(start, end + 1))
            return mock.Mock(read=lambda: data, headers={}, __enter__=lambda s: s, __exit__=lambda *a: None)

        with mock.patch("urllib.request.urlopen", fake_urlopen):
            body = download_ranged(url, total, {"User-Agent": "t"}, chunk=2)
        self.assertEqual(body, bytes(range(5)))
        self.assertEqual(calls, ["bytes=0-1", "bytes=2-3", "bytes=4-4"])
