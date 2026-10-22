"""Smallest picture worth keeping: an image whose shorter side is under the limit is dropped. 0 = no limit.
A picture that cannot be read is kept (never throw away what we cannot judge). No Tk, so it can be tested."""
DEFAULT_MIN_IMAGE_PX = 300
SETTING_KEY = "min_image_px"


def from_settings(settings):
    try:
        return max(0, min(10000, int(float(settings.get(SETTING_KEY, DEFAULT_MIN_IMAGE_PX)))))
    except (TypeError, ValueError):
        return DEFAULT_MIN_IMAGE_PX


def image_too_small(path, min_px):
    if not min_px:
        return False
    try:
        from PIL import Image
        with Image.open(path) as im:
            return min(im.size) < min_px
    except Exception:
        return False
