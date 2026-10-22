"""Small shared helpers for the video-site plugins: polite page fetch, streamed file download, title cleanup."""
import html
import os
import re
import time
import urllib.error
import urllib.request

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
MAX_VIDEO_BYTES = 250 * 1024 * 1024          # bigger files are skipped, not downloaded
CHUNK = 256 * 1024


class Pacer:
    """At least `gap` seconds between two requests to one site."""

    def __init__(self, gap=1.0):
        self.gap, self._last = gap, 0.0

    def wait(self):
        left = self.gap - (time.time() - self._last)
        if left > 0:
            time.sleep(left)
        self._last = time.time()


def get_text(url, pacer, referer=None, timeout=20):
    pacer.wait()
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9",
               "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"}
    if referer:
        headers["Referer"] = referer
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def download(url, dest_path, pacer, referer, stop_event=None, timeout=30):
    """Streams url to dest_path. Returns bytes written; raises ValueError when it is too big. Partial files are removed."""
    pacer.wait()
    headers = {"User-Agent": USER_AGENT, "Referer": referer, "Accept": "*/*"}
    part = dest_path + ".part"
    written = 0
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as resp:
            try:
                size = int(resp.headers.get("Content-Length") or 0)
            except (AttributeError, TypeError, ValueError):
                size = 0
            if size > MAX_VIDEO_BYTES:
                raise ValueError(f"file is {size // (1024 * 1024)} MB (limit {MAX_VIDEO_BYTES // (1024 * 1024)} MB)")
            with open(part, "wb") as out:
                while True:
                    if stop_event is not None and stop_event.is_set():
                        raise InterruptedError("stopped")
                    block = resp.read(CHUNK)
                    if not block:
                        break
                    written += len(block)
                    if written > MAX_VIDEO_BYTES:
                        raise ValueError("file is over the size limit")
                    out.write(block)
        if written == 0:
            raise ValueError("empty download")
        os.replace(part, dest_path)
        return written
    finally:
        if os.path.exists(part):
            try:
                os.remove(part)
            except OSError:
                pass


def clean_title(raw, fallback, strip_tail=r"\s*[-|]\s*(?:Videos\s*-\s*)?(?:Hypnotube|PMVHaven)\s*$"):
    text = html.unescape(re.sub(r"<[^>]+>", "", raw or "")).strip()
    text = re.sub(strip_tail, "", text, flags=re.I).strip()
    return text or fallback


def safe_name(title, fallback="video", limit=40):
    return re.sub(r'[\\/*?:"<>|\s]+', " ", title).strip()[:limit].strip() or fallback
