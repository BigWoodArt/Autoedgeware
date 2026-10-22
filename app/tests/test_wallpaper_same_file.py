import os, tempfile, unittest
from PIL import Image
from core.wallpaper_changer import pil_save_copy


class SameFile(unittest.TestCase):
    def test_backup_is_current_wallpaper(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "original_wallpaper.png")
            Image.new("RGB", (4, 4)).save(path)
            self.assertEqual(pil_save_copy(path, os.path.join(d, "original_wallpaper")), path)
            self.assertTrue(os.path.getsize(path) > 0)
