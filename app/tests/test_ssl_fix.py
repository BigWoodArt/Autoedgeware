import ssl
import sys
import types
import unittest
from unittest import mock

from core import ssl_fix


class SslFix(unittest.TestCase):
    def setUp(self):
        self._orig = ssl._create_default_https_context

    def tearDown(self):
        ssl._create_default_https_context = self._orig

    def test_without_certifi_nothing_changes(self):
        with mock.patch.dict(sys.modules, {"certifi": None}):
            self.assertFalse(ssl_fix.install())
        self.assertIs(ssl._create_default_https_context, self._orig)

    def test_adds_bundle_and_keeps_verification_on(self):
        fake = types.SimpleNamespace(where=lambda: "bundle.pem")
        loaded = []
        real_ctx = ssl.create_default_context()
        real_ctx.load_verify_locations = lambda cafile=None, **k: loaded.append(cafile)
        with mock.patch.dict(sys.modules, {"certifi": fake}), \
                mock.patch.object(ssl, "create_default_context", return_value=real_ctx):
            self.assertTrue(ssl_fix.install())
            ctx = ssl._create_default_https_context()
        self.assertEqual(loaded, ["bundle.pem"])
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(ctx.check_hostname)

    def test_skip_option_turns_checks_off(self):
        self.assertTrue(ssl_fix.install(skip_checks=True))
        ctx = ssl._create_default_https_context()
        self.assertEqual(ctx.verify_mode, ssl.CERT_NONE)

    def test_flag_read_from_settings_file(self):
        import json, os, tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "settings.json")
            with open(path, "w") as f:
                json.dump({"skip_certificate_checks": True}, f)
            ssl_fix.install_from_file(path)
            self.assertEqual(ssl._create_default_https_context().verify_mode, ssl.CERT_NONE)
            with open(path, "w") as f:
                json.dump({}, f)
            ssl_fix.install_from_file(path)
            self.assertNotEqual(ssl._create_default_https_context().verify_mode, ssl.CERT_NONE)
        self.assertFalse(ssl_fix.install_from_file(os.path.join(d, "missing.json")) is None)

    def test_off_by_default_and_in_gui(self):
        from ae_settings.settings import DEFAULTS
        from pathlib import Path
        self.assertFalse(DEFAULTS["skip_certificate_checks"])
        gui = (Path(__file__).resolve().parent.parent / "gui" / "app.py").read_text(encoding="utf-8")
        self.assertIn("Skip certificate checks", gui)
        self.assertIn("Activate only on a trusted network", gui)

    def test_entry_points_call_it(self):
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        for name in ("gui_main.py", "main.py", "run_engine.py"):
            self.assertIn("ssl_fix.install_from_file(", (root / name).read_text(encoding="utf-8"), name)


if __name__ == "__main__":
    unittest.main()
