import io
import os
import tempfile
import unittest
import zipfile

from core import apply_update, updater


class FakeResp:
    def __init__(self, data):
        self.data = data

    def read(self):
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def opener_for(mapping):
    def opener(req, timeout=0):
        url = req.full_url
        if url not in mapping:
            raise OSError("offline")
        return FakeResp(mapping[url])
    return opener


def make_zip(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


REPO_FILES = {
    "Autoedgeware-main/app/VERSION": "0.23.1\n",
    "Autoedgeware-main/app/run_engine.py": "new engine",
    "Autoedgeware-main/app/ae_settings/settings.json": "FROM REPO",
    "Autoedgeware-main/app/edgeware_core/data/blacklist/x.txt": "FROM REPO",
    "Autoedgeware-main/run.bat": "@echo new",
    "Autoedgeware-main/README.md": "new readme",
    "Autoedgeware-main/.gitignore": "x",
}


class Versions(unittest.TestCase):
    def test_parse_and_compare(self):
        self.assertEqual(updater.parse_version("v0.22.4"), (0, 22, 4))
        self.assertIsNone(updater.parse_version("<html>"))
        self.assertTrue(updater.is_newer("0.23.0", "0.22.9"))
        self.assertTrue(updater.is_newer("0.22.10", "0.22.9"))
        self.assertFalse(updater.is_newer("0.22.4", "0.22.4"))
        self.assertFalse(updater.is_newer("0.22.3", "0.22.4"))
        self.assertFalse(updater.is_newer("junk", "0.22.4"))

    def test_check(self):
        op = opener_for({updater.VERSION_URL: b"0.23.0\n"})
        self.assertEqual(updater.check("0.22.4", opener=op), "0.23.0")
        self.assertIsNone(updater.check("0.23.0", opener=op))

    def test_offline_is_silent(self):
        self.assertIsNone(updater.check("0.22.4", opener=opener_for({})))

    def test_garbage_ignored(self):
        op = opener_for({updater.VERSION_URL: b"<html>404</html>"})
        self.assertIsNone(updater.check("0.22.4", opener=op))


class Download(unittest.TestCase):
    def test_download_and_prepare(self):
        op = opener_for({updater.ZIP_URL: make_zip(REPO_FILES)})
        with tempfile.TemporaryDirectory() as d:
            root, _ = updater.download_and_prepare(d, opener=op)
            self.assertTrue(os.path.isfile(os.path.join(root, "app", "VERSION")))

    def test_bad_zip_refused(self):
        op = opener_for({updater.ZIP_URL: b"not a zip"})
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(RuntimeError):
                updater.download_and_prepare(d, opener=op)

    def test_wrong_zip_refused(self):
        op = opener_for({updater.ZIP_URL: make_zip({"a/b.txt": "x"})})
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(RuntimeError):
                updater.download_and_prepare(d, opener=op)


class Apply(unittest.TestCase):
    def test_copies_new_files_and_keeps_user_data(self):
        op = opener_for({updater.ZIP_URL: make_zip(REPO_FILES)})
        with tempfile.TemporaryDirectory() as work, tempfile.TemporaryDirectory() as inst:
            root, _ = updater.download_and_prepare(work, opener=op)
            os.makedirs(os.path.join(inst, "app", "ae_settings"))
            os.makedirs(os.path.join(inst, "app", "edgeware_core", "data", "blacklist"))
            for rel, text in (("app/VERSION", "0.22.4"), ("app/ae_settings/settings.json", "MINE"),
                              ("app/edgeware_core/data/blacklist/x.txt", "MINE")):
                with open(os.path.join(inst, rel), "w") as f:
                    f.write(text)
            failed = apply_update.apply(root, inst, lambda m: None)
            self.assertEqual(failed, [])
            read = lambda rel: open(os.path.join(inst, rel)).read()
            self.assertEqual(read("app/VERSION").strip(), "0.23.1")
            self.assertEqual(read("app/run_engine.py"), "new engine")
            self.assertEqual(read("app/ae_settings/settings.json"), "MINE")
            self.assertEqual(read("app/edgeware_core/data/blacklist/x.txt"), "MINE")
            self.assertFalse(os.path.exists(os.path.join(inst, ".gitignore")))

    def test_run_bat_is_copied_last(self):
        with tempfile.TemporaryDirectory() as d:
            for rel in ("run.bat", "a.txt", os.path.join("app", "z.py")):
                os.makedirs(os.path.dirname(os.path.join(d, rel)) or d, exist_ok=True)
                open(os.path.join(d, rel), "w").close()
            self.assertEqual(apply_update.plan(d)[-1], "run.bat")


class Wiring(unittest.TestCase):
    def test_gui_has_banner_and_setting(self):
        from pathlib import Path
        text = (Path(__file__).resolve().parent.parent / "gui" / "app.py").read_text(encoding="utf-8")
        for needle in ("_start_update_check", "_do_update", "check_for_updates", "updater.launch_helper"):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
