"""Popup image scaling, offline: python -m unittest tests.test_fast_image"""
import io
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "edgeware_core", "src"))
from PIL import Image, ImageChops, ImageStat   # noqa: E402

from fast_image import fast_resize   # noqa: E402


def photo(w, h):
    """Smooth, photo-like picture (soft colour blobs plus a few edges), not pixel noise."""
    from PIL import ImageDraw, ImageFilter
    im = Image.new("RGB", (w, h), (30, 60, 120))
    d = ImageDraw.Draw(im)
    for n in range(40):
        x, y, r = (n * 977) % w, (n * 613) % h, 20 + (n * 37) % (max(w, h) // 5)
        d.ellipse((x - r, y - r, x + r, y + r), fill=((n * 53) % 256, (n * 97) % 256, (n * 29) % 256))
    return im.filter(ImageFilter.GaussianBlur(max(2, w // 200)))


def jpeg_of(im):
    b = io.BytesIO()
    im.save(b, "JPEG", quality=90)
    b.seek(0)
    return Image.open(b)


class Scaling(unittest.TestCase):
    def test_jpeg_comes_out_at_the_asked_size_and_rgb(self):
        src = jpeg_of(photo(2400, 1800))
        out = fast_resize(src, (400, 300))
        self.assertEqual(out.size, (400, 300))
        self.assertEqual(out.mode, "RGB")

    def test_looks_like_the_slow_filter(self):
        im = photo(1600, 1200)
        slow = im.resize((320, 240), Image.LANCZOS)
        fast = fast_resize(im, (320, 240))
        diff = ImageStat.Stat(ImageChops.difference(slow, fast)).mean
        self.assertLess(max(diff), 6.0)
        src = jpeg_of(im)
        ref = src.copy().resize((320, 240), Image.LANCZOS)
        diff = ImageStat.Stat(ImageChops.difference(ref, fast_resize(src, (320, 240)))).mean
        self.assertLess(max(diff), 8.0)             # JPEG decoded shrunk: still the same picture

    def test_transparency_is_kept(self):
        im = Image.new("RGBA", (500, 500), (255, 0, 0, 0))
        out = fast_resize(im, (100, 100))
        self.assertEqual(out.mode, "RGBA")
        self.assertEqual(out.getpixel((50, 50))[3], 0)
        pal = Image.new("P", (50, 50))
        pal.info["transparency"] = 0
        self.assertEqual(fast_resize(pal, (20, 20)).mode, "RGBA")

    def test_other_modes_become_rgb_and_tiny_sizes_work(self):
        self.assertEqual(fast_resize(Image.new("L", (300, 300), 90), (60, 60)).mode, "RGB")
        self.assertEqual(fast_resize(Image.new("RGB", (30, 30)), (0, 0)).size, (1, 1))
        self.assertEqual(fast_resize(Image.new("RGB", (30, 30)), (90, 90)).size, (90, 90))   # enlarging too

    def test_much_faster_than_lanczos_on_a_big_jpeg(self):
        im = photo(4000, 3000)
        b = io.BytesIO()
        im.save(b, "JPEG", quality=85)
        data = b.getvalue()

        def timed(fn):
            t = time.perf_counter()
            for _ in range(3):
                fn(Image.open(io.BytesIO(data)))
            return time.perf_counter() - t
        slow = timed(lambda i: i.resize((500, 375), Image.LANCZOS).convert("RGBA"))
        fast = timed(lambda i: fast_resize(i, (500, 375)))
        self.assertLess(fast, slow * 0.6)


if __name__ == "__main__":
    unittest.main()
