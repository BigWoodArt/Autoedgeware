import unittest
from pathlib import Path

SRC = (Path(__file__).resolve().parent.parent / "run_engine.py").read_text(encoding="utf-8")


class StartupDelay(unittest.TestCase):
    def test_setting_is_read(self):
        self.assertIn('startup_delay_seconds', SRC)

    def test_delay_uses_after(self):
        self.assertIn("root.after(wait_s * 1000, begin)", SRC)

    def test_zero_starts_now(self):
        self.assertIn("    else:\n        begin()", SRC)

    def test_delay_capped(self):
        self.assertIn("min(3600", SRC)


if __name__ == "__main__":
    unittest.main()
