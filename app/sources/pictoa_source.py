"""Pictoa category pages: /c/{slug}/ and paginated listings -> full-size CDN images."""
import re

from sources.json_board import JsonBoardSource, ApiError

BROWSER_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9",
}
PAIRED_RE = re.compile(
    r'href="(https://www\.pictoa\.com/albums/[^"]+)"[\s\S]{0,1500}?'
    r'(https://t\d+\.pictoa\.com/media/galleries/[^"\'\\\s]+)',
    re.I,
)
LOOSE_RE = re.compile(r"https://t\d+\.pictoa\.com/media/galleries/[^\"'\\\s]+", re.I)
ALBUM_SLUG_RE = re.compile(r"/albums/([^/]+)")


def _upgrade_url(url):
    return re.sub(r"https://t(\d+)\.pictoa\.com/", r"https://s\1.pictoa.com/", url, flags=re.I)


def _extract_posts(html):
    seen, posts = set(), []
    for m in PAIRED_RE.finditer(html):
        url = _upgrade_url(m.group(2))
        if url in seen:
            continue
        seen.add(url)
        pid = url.rstrip("/").rsplit("/", 1)[-1]
        title = ""
        sm = ALBUM_SLUG_RE.search(m.group(1))
        if sm:
            title = sm.group(1).replace("-", " ")
        posts.append({"id": pid, "url": url, "tags": [], "title": title})
    if posts:
        return posts
    for m in LOOSE_RE.finditer(html):
        url = _upgrade_url(m.group(0))
        if url in seen:
            continue
        seen.add(url)
        pid = url.rstrip("/").rsplit("/", 1)[-1]
        posts.append({"id": pid, "url": url, "tags": [], "title": ""})
    return posts


class PictoaSource(JsonBoardSource):
    id, label = "pictoa", "Pictoa"
    category = "Gallery sites"
    prefix = "pto_"
    base_url = "https://www.pictoa.com"
    check_query = "glamour-494"
    default_limit = 50
    min_interval = 1.5
    has_media_priority = False
    order_choices = [("site", "Site order", {})]
    default_order = "site"
    min_score_choices = []
    query_hint = "category slug (e.g. glamour-494) or /c/glamour-494/ link"
    order_help = "Pictures follow the site's category listing order, page by page."

    @classmethod
    def suggest(cls, query):
        q = (query or "").strip().strip("/")
        if q.startswith("http"):
            m = re.search(r"/c/([a-z0-9][a-z0-9-]*)/?", q, re.I)
            q = m.group(1) if m else q
        if not q:
            return []
        return [{"value": q, "label": f"{cls.label} {q}", "count": None}]

    def _normalize_query(self, query):
        q = (query or "").strip()
        m = re.search(r"/c/([a-z0-9][a-z0-9-]*)/?", q, re.I)
        return m.group(1) if m else q.strip("/")

    def _headers(self):
        return dict(BROWSER_HEADERS, Accept="text/html", Referer=f"{self.base_url}/")

    def _download_headers(self):
        return dict(BROWSER_HEADERS, Referer=f"{self.base_url}/")

    def _listing_url(self, slug, page):
        base = f"{self.base_url}/c/{slug}/"
        return base if page <= 1 else f"{base}page{page}.html"

    def _page(self, query, cursor):
        slug = query
        page = cursor or 1
        if page > 21:
            return [], None
        raw = self._open(self._listing_url(slug, page), headers=self._headers()).decode("utf-8", "replace")
        if "Just a moment" in raw[:3000]:
            raise ApiError("got a browser-check page instead of results")
        posts = _extract_posts(raw)
        return posts, (page + 1 if posts else None)
