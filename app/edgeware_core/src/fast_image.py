"""Fast, good-looking image scaling for popups (no Tk, so it can be tested on its own).

Pillow's Lanczos filter on a full-size photo is the slowest way to make a popup. Two cheaper steps give the same
look at popup size: a JPEG is decoded already shrunk by the decoder (draft: 1/2, 1/4 or 1/8), and the rest is
a bilinear resize that first averages big blocks (reducing_gap). Bilinear in Pillow is area-aware when shrinking,
so there is no jagged edge."""
from PIL import Image


def has_alpha(image):
    return image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info


def fast_resize(image, size):
    """A resized copy of `image` (a Pillow image) at size (w, h). Mode is RGB, or RGBA if the picture has
    transparency. Call it after the popup's geometry is worked out: draft() shrinks image.size."""
    width, height = max(1, int(size[0])), max(1, int(size[1]))
    keep_alpha = has_alpha(image)
    if image.format == "JPEG" and hasattr(image, "draft"):
        try:
            image.draft("RGB", (width, height))      # never smaller than (width, height)
        except Exception:
            pass
    if keep_alpha:
        image = image.convert("RGBA")
    elif image.mode != "RGB":
        image = image.convert("RGB")
    return image.resize((width, height), Image.BILINEAR, reducing_gap=2.0)
