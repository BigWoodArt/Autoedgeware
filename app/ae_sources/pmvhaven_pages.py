"""PMVHaven: search page -> video pages -> the HLS master.m3u8 inside the page's __NUXT_DATA__ -> ffmpeg -> .mp4.

Confirmed by probe: /search?q=<word> lists /video/<slug>_<24 hex id> links in its static HTML (about 8 per page),
and the video page holds the master playlist URL as one JSON string (https:\\u002F\\u002F...master.m3u8).
Not confirmed: whether q= really narrows the list, and any sort option, so no sort/quality is offered.
Needs ffmpeg on PATH; the file host wants a Referer."""
import json
import os
import re
import shutil
import subprocess
import urllib.parse

from sources.base import Source
from core.media_item import MediaItem
from core.winproc import quiet
from core.scheduler import PMVHAVEN_DOWNLOAD_MB
from ae_sources import _web, pmvhaven_dns

pmvhaven_dns.install()

SITE = "https://pmvhaven.com"
VIDEO_LINK_RE = re.compile(r'href=["\'](?:https?://(?:www\.)?pmvhaven\.com)?(/video/[A-Za-z0-9_\-%.]*?_([0-9a-f]{24}))(?:[?"\'#&])', re.I)
M3U8_RE = re.compile(r'"(https:\\u002F\\u002F[^"]*?master\.m3u8)"')
M3U8_PLAIN_RE = re.compile(r'(https://[^"\'\s\\]+?master\.m3u8[^"\'\s\\]*)')
TITLE_RE = re.compile(r'<title>(.*?)</title>', re.I | re.S)
MAX_SECONDS = 1200          # ffmpeg copies at most this much of one video
FFMPEG_TIMEOUT = 900


def clean_word(text):
    text = (text or "").strip()
    m = re.match(r"https?://(?:www\.)?pmvhaven\.com/search\?(?:.*&)?q=([^&#]+)", text, re.I)
    return urllib.parse.unquote_plus(m.group(1)) if m else text


def parse_links(page):
    seen, out = set(), []
    for path, vid in VIDEO_LINK_RE.findall(page.replace("&amp;", "&")):
        if vid not in seen:
            seen.add(vid)
            out.append((path, vid))
    return out


def parse_video(page):
    """(master playlist url or None, title)."""
    url = None
    m = M3U8_RE.search(page)
    if m:
        try:
            url = json.loads(f'"{m.group(1)}"')
        except json.JSONDecodeError:
            url = None
    if url is None:
        m = M3U8_PLAIN_RE.search(page)
        url = m.group(1) if m else None
    t = TITLE_RE.search(page)
    return url, _web.clean_title(t.group(1) if t else "", "pmvhaven")


class PmvhavenPageSource(Source):
    id = "pmvhaven_pages"
    label = "PMVHaven"
    category = "GIFs & Video"
    query_hint = "a search word (e.g. hypno)"
    check_query = "hypno"
    default_limit = 3
    priority_media = "video"

    def __init__(self):
        self.pacer = _web.Pacer(1.0)
        self.ffmpeg = shutil.which("ffmpeg")

    @staticmethod
    def search_url(query):
        return f"{SITE}/search?q={urllib.parse.quote(query.strip(), safe='')}"

    def _grab(self, m3u8, dest):
        part = dest + ".part"        # not a media extension: the popup engine must not pick up half a file
        cmd = [self.ffmpeg, "-nostdin", "-y", "-loglevel", "error",
               "-user_agent", _web.USER_AGENT, "-headers", f"Referer: {SITE}/\r\n",
               "-i", m3u8, "-t", str(MAX_SECONDS), "-c", "copy", "-bsf:a", "aac_adtstoasc", "-f", "mp4", part]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=FFMPEG_TIMEOUT,
                           check=True, **quiet())
            if not os.path.exists(part) or os.path.getsize(part) < 10_000:
                raise ValueError("ffmpeg wrote an empty file")
            if os.path.getsize(part) > PMVHAVEN_DOWNLOAD_MB * 1048576:
                raise ValueError("file is over the size limit")
            os.replace(part, dest)
        except subprocess.CalledProcessError as ex:
            raise ValueError((ex.stderr or b"").decode("utf-8", "replace").strip()[-200:] or "ffmpeg failed")
        finally:
            if os.path.exists(part):
                try:
                    os.remove(part)
                except OSError:
                    pass

    def fetch(self, query, limit, sort, time_range, dest_dir, log, progress, stop_event,
              early_preview_cb=None, randomize=False, prioritize_images=False,
              item_cb=None, skip_ids=None):
        word = clean_word(query)
        if not word:
            log("[PMVHaven] needs a search word", "warning")
            return []
        if not self.ffmpeg:
            log("[PMVHaven] ffmpeg was not found on PATH; PMVHaven videos need it. Skipped.", "warning")
            return []
        os.makedirs(dest_dir, exist_ok=True)
        url = self.search_url(word)
        log(f"Searching PMVHaven for '{word}'...")
        try:
            page = _web.get_text(url, self.pacer, referer=SITE + "/", timeout=30)
        except Exception as ex:
            log(f"[PMVHaven] search failed: {ex}", "error")
            return []
        links = parse_links(page)
        if not links:
            snippet = re.sub(r"\s+", " ", page).strip()[:300]
            log(f"No PMVHaven videos for '{word}'. Reply began: {snippet!r}", "warning")
            return []
        log(f"[PMVHaven] '{word}': {len(links)} video(s) on the first page")
        if randomize:
            import random
            random.shuffle(links)
        results = []
        for i, (path, vid) in enumerate(links, start=1):
            if stop_event.is_set():
                log("--- Stopped by user ---", "warning")
                break
            if len(results) >= limit:
                break
            post_id = f"pmvhaven_{vid}"
            if skip_ids and post_id in skip_ids:
                continue
            progress(i, len(links), "PMVHaven videos")
            try:
                m3u8, title = parse_video(_web.get_text(SITE + path, self.pacer, referer=url, timeout=30))
            except Exception as ex:
                log(f"   -> could not open video {vid}: {ex}", "warning")
                continue
            if not m3u8:
                log(f"   -> no stream found on page {vid}", "warning")
                continue
            dest = os.path.join(dest_dir, f"{_web.safe_name(title, 'pmvhaven')}_{vid[-8:]}.mp4")
            if not os.path.exists(dest):
                log(f"   -> fetching stream for '{title}' (can take a minute)...")
                try:
                    self._grab(m3u8, dest)
                except Exception as ex:
                    log(f"   -> skipped '{title}': {ex}", "warning")
                    continue
            log(f"[{len(results) + 1}/{limit}] downloaded '{title}'")
            item = MediaItem(file_path=dest, caption=title, media_type="video", source_label=f"PMVHaven: {word}",
                             post_id=post_id, source_type="pmvhaven", attribution=SITE + path)
            results.append(item)
            if item_cb is not None:
                item_cb(item)
            if early_preview_cb is not None and len(results) == 3:
                early_preview_cb(list(results))
                early_preview_cb = None
        log(f"--- PMVHaven '{word}': {len(results)} video(s) collected ---")
        return results
