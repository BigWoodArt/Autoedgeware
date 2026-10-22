"""Picks the startup splash from the preset's own downloaded media, and waits briefly for the first
image on a fresh run. No Edgeware or Tk imports (the caller passes in a root with .after())."""
import os
import random
import time
from pathlib import Path

SPLASH_EXTS = {".jpg", ".jpeg", ".png", ".gif"}
MIN_AGE_SECONDS = 1.0     # a file touched this recently may still be mid-download


def _openable(path):
    try:
        from PIL import Image
        with Image.open(path) as im:
            im.verify()
        return True
    except Exception:
        return False


def pick_splash(folders, rng=random, min_age=MIN_AGE_SECONDS, now=None, check=_openable, tries=8):
    """A random finished gif/jpg/png from any of the folders, or None."""
    now = time.time() if now is None else now
    found = []
    for folder in folders:
        try:
            names = os.listdir(folder)
        except OSError:
            continue
        for name in names:
            if name.startswith(".") or os.path.splitext(name)[1].lower() not in SPLASH_EXTS:
                continue
            path = Path(folder) / name
            try:
                st = path.stat()
            except OSError:
                continue
            if st.st_size > 0 and now - st.st_mtime >= min_age:
                found.append(path)
    rng.shuffle(found)
    for path in found[:tries]:
        if check(path):
            return path
    return None


def choose_splash(root, folders, default, on_choice, timeout_ms=10000, poll_ms=500, picker=pick_splash):
    """Calls on_choice(path, from_pool) once: a pool image as soon as one exists, else the default
    after timeout_ms. `root` only needs .after(ms, fn)."""
    def attempt(elapsed):
        picked = picker(folders)
        if picked is not None:
            on_choice(picked, True)
        elif elapsed >= timeout_ms:
            on_choice(default, False)
        else:
            root.after(poll_ms, lambda: attempt(elapsed + poll_ms))
    attempt(0)
