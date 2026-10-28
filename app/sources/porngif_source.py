"""PornGIF site search -> direct .gif URLs."""
import re
import urllib.parse

from sources.json_board import JsonBoardSource, ApiError

BROWSER_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9",
}
GIF_RE = re.compile(r"(?:https://porngif\.xxx/)?gif/(\d+)\.gif", re.I)


def _extract_posts(html):
    seen, posts = set(), []
    for m in GIF_RE.finditer(html):
        gid = m.group(1)
        if gid in seen:
            continue
        seen.add(gid)
        url = f"https://porngif.xxx/gif/{gid}.gif"
        posts.append({"id": gid, "url": url, "tags": [], "title": f"gif {gid}"})
    return posts


class PornGifSource(JsonBoardSource):
    id, label = "porngif", "PornGIF"
    category = "Gallery sites"
    prefix = "pgf_"
    base_url = "https://porngif.xxx"
    check_query = "sexy"
    default_limit = 50
    min_interval = 1.5
    has_media_priority = False
    priority_media = "image"
    order_choices = [("site", "Site order", {})]
    default_order = "site"
    min_score_choices = []
    query_hint = "search words (site search is loosely tagged)"
    order_help = "GIFs come from the site's search results page."

    @classmethod
    def suggest(cls, query):
        q = (query or "").strip()
        if not q:
            return []
        return [{"value": q, "label": f"{cls.label} {q}", "count": None}]

    def _headers(self):
        return dict(BROWSER_HEADERS, Accept="text/html", Referer=f"{self.base_url}/")

    def _download_headers(self):
        return dict(BROWSER_HEADERS, Referer=f"{self.base_url}/")

    def _page(self, query, cursor):
        if cursor:
            return [], None
        qs = urllib.parse.urlencode({"s": query})
        raw = self._open(f"{self.base_url}/?{qs}", headers=self._headers()).decode("utf-8", "replace")
        if "Just a moment" in raw[:3000]:
            raise ApiError("got a browser-check page instead of results")
        posts = _extract_posts(raw)
        return posts, None
