"""Pornhub album stills and GIF search (HTML listings; GIF file URLs resolved per detail page)."""
import re
import urllib.error
import urllib.parse
import urllib.request

from sources.http_bytes import download_ranged, probe_byte_size
from sources.json_board import JsonBoardSource, ApiError

BROWSER_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9",
}
HOST = "https://www.pornhub.com"
LARGE_PIC_RE = re.compile(
    r"https://ei\.phncdn\.com/pics/albums/[^\"'\\\s]*\(m=e-yaaGqaq\)[^\"'\\\s]+",
    re.I,
)
ALBUM_ID_RE = re.compile(r"/album/(\d+)", re.I)
PHOTO_ID_RE = re.compile(r"/photo/(\d+)", re.I)
GIF_ID_RE = re.compile(r"/gif/(\d+)", re.I)
MAX_GIF_BYTES = 100 * 1048576   # skip above this (scraper cap, not a GUI setting)
RANGE_GIF_BYTES = 8 * 1048576   # PH CDN often 503 on full GET above ~8–10 MB; use Range chunks


def _album_search_url(query, page):
    params = urllib.parse.urlencode({"search": query, "page": str(page)})
    return f"{HOST}/albums/search?{params}"


def _large_pics(html):
    return list({m.group(0) for m in LARGE_PIC_RE.finditer(html)})


class PornhubImagesSource(JsonBoardSource):
    id, label = "pornhub_images", "Pornhub Photos"
    category = "Gallery sites"
    prefix = "phi_"
    base_url = HOST
    default_limit = 30
    min_interval = 2.0
    has_media_priority = False
    order_choices = [("site", "Site order", {})]
    default_order = "site"
    min_score_choices = []
    check_query = "sexy"
    query_hint = "album search words"
    order_help = "Album search, then each album and photo page for the largest still (many requests)."

    @classmethod
    def suggest(cls, query):
        q = (query or "").strip()
        if not q:
            return []
        return [{"value": q, "label": f"{cls.label} {q}", "count": None}]

    def fetch(self, query, limit, sort, time_range, dest_dir, log, progress, stop_event,
              early_preview_cb=None, randomize=False, prioritize_images=False,
              item_cb=None, skip_ids=None):
        self._search_pages = [1, 2]
        self._album_ids = []
        self._photo_ids = []
        return super().fetch(query, limit, sort, time_range, dest_dir, log, progress, stop_event,
                             early_preview_cb, randomize, prioritize_images, item_cb, skip_ids)

    def _html(self, url, referer):
        raw = self._open(url, headers=dict(BROWSER_HEADERS, Accept="text/html", Referer=referer)).decode(
            "utf-8", "replace")
        if "Just a moment" in raw[:3000]:
            raise ApiError("got a browser-check page instead of results")
        return raw

    def _download_headers(self):
        return dict(BROWSER_HEADERS, Referer=f"{HOST}/albums")

    def _refill_photo_ids(self, query):
        while self._search_pages and len(self._album_ids) < 12:
            page = self._search_pages.pop(0)
            html = self._html(_album_search_url(query, page), f"{HOST}/albums")
            for aid in ALBUM_ID_RE.findall(html):
                if aid not in self._album_ids:
                    self._album_ids.append(aid)
        while self._album_ids and len(self._photo_ids) < 80:
            aid = self._album_ids.pop(0)
            try:
                html = self._html(f"{HOST}/album/{aid}", f"{HOST}/albums")
            except Exception:
                continue
            for pid in PHOTO_ID_RE.findall(html):
                if pid not in self._photo_ids:
                    self._photo_ids.append(pid)

    def _page(self, query, cursor):
        self._refill_photo_ids(query)
        posts = []
        while self._photo_ids and len(posts) < 6:
            pid = self._photo_ids.pop(0)
            try:
                html = self._html(f"{HOST}/photo/{pid}", f"{HOST}/albums")
            except Exception:
                continue
            for url in _large_pics(html):
                pic_id = re.search(r"original_(\d+)", url)
                posts.append({
                    "id": pic_id.group(1) if pic_id else pid,
                    "url": url,
                    "tags": [],
                    "title": f"photo {pid}",
                })
        more = bool(self._photo_ids or self._album_ids or self._search_pages)
        return posts, (1 if more else None)


class PornhubGifsSource(JsonBoardSource):
    id, label = "pornhub_gifs", "Pornhub GIFs"
    category = "Gallery sites"
    prefix = "phg_"
    base_url = HOST
    default_limit = 40
    min_interval = 2.0
    has_media_priority = False
    order_choices = [("site", "Site order", {})]
    default_order = "site"
    min_score_choices = []
    check_query = "sexy"
    query_hint = "GIF search words"
    order_help = "GIF search, then each GIF page for the signed file URL."

    @classmethod
    def suggest(cls, query):
        q = (query or "").strip()
        if not q:
            return []
        return [{"value": q, "label": f"{cls.label} {q}", "count": None}]

    def _html(self, url, referer):
        raw = self._open(url, headers=dict(BROWSER_HEADERS, Accept="text/html", Referer=referer)).decode(
            "utf-8", "replace")
        if "Just a moment" in raw[:3000]:
            raise ApiError("got a browser-check page instead of results")
        return raw

    def _download_headers(self):
        ref = getattr(self, "_gif_referer", None) or f"{HOST}/gifs"
        return dict(BROWSER_HEADERS, Referer=ref)

    def _gif_byte_size(self, url):
        return probe_byte_size(url, self._download_headers())

    def _download_bytes(self, url, log=None):
        size = getattr(self, "_current_gif_size", 0) or self._gif_byte_size(url)
        headers = self._download_headers()
        if size and size >= RANGE_GIF_BYTES:
            if log:
                log(f"   -> ranged download ({size // 1048576} MB gif)", "info")
            return download_ranged(url, size, headers, wait=self._wait)
        try:
            return super()._download_bytes(url, log)
        except urllib.error.HTTPError as ex:
            if ex.code == 503:
                size = size or self._gif_byte_size(url)
                if size:
                    if log:
                        log(f"   -> full GET failed ({ex.code}); retrying with ranges", "warning")
                    return download_ranged(url, size, headers, wait=self._wait)
            raise

    def _gif_search_url(self, query, page):
        params = urllib.parse.urlencode({"search": query, "page": str(page)})
        return f"{HOST}/gifs/search?{params}"

    def _page(self, query, cursor):
        page = cursor or 1
        if page > 3:
            return [], None
        html = self._html(self._gif_search_url(query, page), f"{HOST}/gifs")
        seen, posts = set(), []
        for gid in GIF_ID_RE.findall(html):
            if gid in seen:
                continue
            seen.add(gid)
            posts.append({
                "id": gid,
                "url": f"{HOST}/gif/{gid}",
                "tags": [],
                "title": f"gif {gid}",
            })
        return posts, (page + 1 if posts else None)

    def _resolve_url(self, post, log):
        pid = post.get("id")
        if not pid:
            return None
        self._gif_referer = f"{HOST}/gif/{pid}"
        try:
            html = self._html(f"{HOST}/gif/{pid}", f"{HOST}/gifs")
        except Exception:
            return None
        m = re.search(r'data-gif="([^"]+)"', html, re.I)
        if not m:
            return None
        url = m.group(1).replace("&amp;", "&")
        size = self._gif_byte_size(url)
        self._current_gif_size = size
        if size and size > MAX_GIF_BYTES:
            log(f"   -> skipped gif {pid}: {size // 1048576} MB (over {MAX_GIF_BYTES // 1048576} MB scraper cap)", "warning")
            return None
        return url
