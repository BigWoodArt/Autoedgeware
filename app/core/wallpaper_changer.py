"""Desktop wallpaper changer: saves the user's wallpaper, swaps in wide images from the running preset, and
puts the original back on Stop, Panic or exit.

- A wallpaper image must be at least 1000 px wide with a roughly 16:9 shape (16:10 up to about 2:1).
- Images are noted as they download: every tick looks at new files only (results are remembered).
- The wallpaper changes at most once per interval (default 2 minutes).
- The original is COPIED into our own folder first (Windows rewrites its own wallpaper cache file on every
  change, so the path it reports cannot be trusted later). A state file remembers an unfinished run, so if the
  program was killed, the next start keeps the true original instead of saving one of our images as 'original'.

The OS calls and the image-size lookup are passed in, so this is testable with no desktop and no Tk."""
import atexit
import json
import os
import random
import shutil
import time

MIN_WIDTH = 1000
RATIO_MIN, RATIO_MAX = 1.55, 1.95
WALLPAPER_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}
MAX_NEW_PER_TICK = 60


def fits(width, height):
    if not width or not height or width < MIN_WIDTH:
        return False
    return RATIO_MIN <= width / height <= RATIO_MAX


def pil_size(path):
    from PIL import Image
    with Image.open(path) as im:
        return im.size


def pil_save_copy(src, dst_base):
    """Copy src next to dst_base with a proper extension (the Windows cache file has none). Returns the path."""
    from PIL import Image
    with Image.open(src) as im:
        fmt = (im.format or "").upper()
    ext = {"JPEG": ".jpg", "PNG": ".png", "BMP": ".bmp"}.get(fmt)
    if ext:
        dst = dst_base + ext
        if os.path.normcase(os.path.abspath(src)) != os.path.normcase(os.path.abspath(dst)):
            shutil.copyfile(src, dst)       # already our own backup (a crashed run left it set): keep it
        return dst
    dst = dst_base + ".png"
    with Image.open(src) as im:
        im.convert("RGB").save(dst, "PNG")
    return dst


class WallpaperChanger:
    def __init__(self, folders_fn, state_dir, get_wallpaper, set_wallpaper, interval_s=120, size_of=pil_size,
                 save_copy=pil_save_copy, log=None, clock=time.time, rng=random):
        self.folders_fn, self.state_dir = folders_fn, state_dir
        self.get_wallpaper, self.set_wallpaper = get_wallpaper, set_wallpaper
        self.interval_s, self.size_of, self.save_copy = interval_s, size_of, save_copy
        self.log, self.clock, self.rng = log or (lambda m: None), clock, rng
        self.active = False
        self.backup = None
        self._known = {}          # path -> fits (True/False), so each file is measured once
        self._used = set()        # shown this round; cleared when everything has been shown
        self._last_change = None
        self._last_path = None
        self._atexit = False

    # ----- state file -----
    @property
    def _state_path(self):
        return os.path.join(self.state_dir, "wallpaper_state.json")

    def _read_state(self):
        try:
            with open(self._state_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _write_state(self, active):
        try:
            os.makedirs(self.state_dir, exist_ok=True)
            with open(self._state_path, "w", encoding="utf-8") as f:
                json.dump({"active": active, "backup": self.backup}, f)
        except OSError:
            pass

    # ----- lifecycle -----
    def start(self):
        """Save the current wallpaper (once) and begin allowing changes. Returns False if it could not be saved,
        in which case the wallpaper is never touched."""
        if self.active:
            return True
        state = self._read_state()
        if state.get("active") and state.get("backup") and os.path.isfile(state["backup"]):
            self.backup = state["backup"]
            self.log("wallpaper: a previous run did not finish - keeping its saved original")
        else:
            try:
                current = self.get_wallpaper()
                if not current or not os.path.isfile(str(current)):
                    self.log("wallpaper: could not find your current wallpaper - not changing it")
                    return False
                os.makedirs(self.state_dir, exist_ok=True)
                self.backup = self.save_copy(str(current), os.path.join(self.state_dir, "original_wallpaper"))
            except Exception as ex:
                self.log(f"wallpaper: could not save your current wallpaper ({ex}) - not changing it")
                return False
        self.active = True
        self._last_change = None
        self._write_state(True)
        if not self._atexit:
            atexit.register(self.stop)
            self._atexit = True
        return True

    def stop(self):
        """Put the original back. Safe to call any number of times."""
        if not self.active:
            return
        self.active = False
        restored = False
        if self.backup and os.path.isfile(self.backup):
            try:
                self.set_wallpaper(self.backup)
                restored = True
            except Exception as ex:
                self.log(f"wallpaper: could not restore ({ex})")
        self._write_state(not restored)    # stays 'unfinished' if the restore failed
        if restored:
            self.log("wallpaper: your original wallpaper is back")

    restore = stop

    # ----- picking -----
    def scan(self):
        """Note new images that fit. Looks at a limited number of new files per call."""
        new = 0
        for folder in self.folders_fn():
            try:
                names = os.listdir(folder)
            except OSError:
                continue
            names = list(names)
            self.rng.shuffle(names)         # not folder order: the first picture must differ from run to run
            for name in names:
                path = os.path.join(folder, name)
                if path in self._known or os.path.splitext(name)[1].lower() not in WALLPAPER_EXTS:
                    continue
                if new >= MAX_NEW_PER_TICK:
                    return
                new += 1
                try:
                    w, h = self.size_of(path)
                except Exception:
                    w = h = 0
                self._known[path] = fits(w, h)

    def candidates(self):
        return [p for p, ok in self._known.items() if ok and os.path.isfile(p)]

    def tick(self):
        """Call every few seconds. Returns the path it set, or None."""
        if not self.active:
            return None
        self.scan()
        now = self.clock()
        if self._last_change is not None and now - self._last_change < self.interval_s:
            return None
        pool = self.candidates()
        if not pool:
            return None
        fresh = [p for p in pool if p not in self._used and p != self._last_path]
        if not fresh:
            self._used.clear()
            fresh = [p for p in pool if p != self._last_path] or pool
        choice = self.rng.choice(fresh)
        try:
            self.set_wallpaper(choice)
        except Exception as ex:
            self.log(f"wallpaper: could not set {os.path.basename(choice)} ({ex})")
            self._last_change = now
            return None
        self._used.add(choice)
        self._last_path = choice
        self._last_change = now
        self.log(f"wallpaper: now {os.path.basename(choice)} ({len(pool)} fitting image(s) noted)")
        return choice
