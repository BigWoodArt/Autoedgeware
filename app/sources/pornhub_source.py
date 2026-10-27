"""Pornhub album stills: search listings, then each photo page for the large variant."""
import re
import urllib.parse

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


def _photo_ids(html):
    ids = set()
    for m in re.finditer(r"/photo/(\d+)", html, re.I):
        ids.add(m.group(1))
    for m in re.finditer(r"original_(\d+)\.", html, re.I):
        ids.add(m.group(1))
    return list(ids)


def _large_pics(html):
    return list({m.group(0) for m in LARGE_PIC_RE.finditer(html)})


def _album_search_url(query, page):
    params = urllib.parse.urlencode({"search": query, "page": str(page)})
    return f"{HOST}/albums/search?{params}"


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
    order_help = "Album search, then each photo page for the largest still (many requests per item)."

    @classmethod
    def suggest(cls, query):
        q = (query or "").strip()
        if not q:
            return []
        return [{"value": q, "label": f"{cls.label} {q}", "count": None}]

    def fetch(self, query, limit, sort, time_range, dest_dir, log, progress, stop_event,
              early_preview_cb=None, randomize=False, prioritize_images=False,
              item_cb=None, skip_ids=None):
        self._list_pages = [1, 2]
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
        while self._list_pages and len(self._photo_ids) < 80:
            page = self._list_pages.pop(0)
            html = self._html(_album_search_url(query, page), f"{HOST}/albums")
            for pid in _photo_ids(html):
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
        more = bool(self._photo_ids or self._list_pages)
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
    order_help = "GIF search listings; file URLs include a short-lived token from the page."

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
        return dict(BROWSER_HEADERS, Referer=f"{HOST}/gifs")

    def _gif_search_url(self, query, page):
        params = urllib.parse.urlencode({"search": query, "page": str(page)})
        return f"{HOST}/gifs/search?{params}"

    def _page(self, query, cursor):
        page = cursor or 1
        if page > 3:
            return [], None
        html = self._html(self._gif_search_url(query, page), f"{HOST}/gifs")
        seen, posts = set(), []
        for m in re.finditer(r'data-gif="(https:[^"]+)"', html, re.I):
            url = m.group(1).replace("&amp;", "&")
            gid = re.search(r"/(\d+)[ab]\.gif", url.split("?")[0], re.I)
            pid = gid.group(1) if gid else url
            if pid in seen:
                continue
            seen.add(pid)
            posts.append({"id": pid, "url": url, "tags": [], "title": f"gif {pid}"})
        return posts, (page + 1 if posts else None)
