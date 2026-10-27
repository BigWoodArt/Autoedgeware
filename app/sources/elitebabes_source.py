"""EliteBabes tag feeds via the public WordPress REST API."""
import json
import re
import urllib.parse

from sources.json_board import JsonBoardSource, ApiError

BROWSER_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9",
}
HOST = "https://www.elitebabes.com"
CDN = "https://cdn.elitebabes.com"
CONTENT_URL_RE = re.compile(r"https://(?:www\.)?elitebabes\.com/content/[^\s,\"<]+", re.I)


def _to_cdn(url):
    return re.sub(r"^https://(?:www\.)?elitebabes\.com/content/", f"{CDN}/content/", url, flags=re.I)


def _keep_url(url):
    if not re.match(r"^https://cdn\.elitebabes\.com/content/", url, re.I):
        return None
    if re.search(r"/\d{4}-\d{2}_w\d+\.jpg$", url, re.I):
        return None
    if re.search(r"_masonry_\d+\.jpg$", url, re.I) and not re.search(r"_masonry_1200\.jpg$", url, re.I):
        return None
    return url


def posts_from_wp(posts):
    """Map WP posts (content.rendered = comma-separated image URLs) to normalised posts."""
    if not isinstance(posts, list):
        return []
    seen, out = set(), []
    for post in posts:
        raw = str((post or {}).get("content", {}).get("rendered") or "")
        title = re.sub(r"<[^>]+>", "", str((post or {}).get("title", {}).get("rendered") or "")).strip()
        for found in CONTENT_URL_RE.findall(raw):
            url = _keep_url(_to_cdn(found.rstrip(",.")))
            if not url:
                continue
            pid = url.rsplit("/", 1)[-1]
            if pid in seen:
                continue
            seen.add(pid)
            out.append({"id": pid, "url": url, "tags": [], "title": title})
    return out


class EliteBabesSource(JsonBoardSource):
    id, label = "elitebabes", "EliteBabes"
    category = "Gallery sites"
    prefix = "eb_"
    base_url = HOST
    check_query = "beautiful"
    default_limit = 50
    min_interval = 1.5
    has_media_priority = False
    order_choices = [("site", "Site order", {})]
    default_order = "site"
    min_score_choices = []
    query_hint = "tag slug (e.g. beautiful)"
    order_help = "Images follow the tag feed order from the site's API."

    @classmethod
    def suggest(cls, query):
        q = (query or "").strip().strip("/")
        if not q:
            return []
        entry = {"value": q, "label": f"{cls.label} {q}", "count": None}
        params = urllib.parse.urlencode({"search": q, "per_page": "20"})
        data = cls._suggest_json(f"{HOST}/wp-json/wp/v2/tags?{params}",
                                 headers=dict(BROWSER_HEADERS, Accept="application/json", Referer=f"{HOST}/"))
        if not isinstance(data, list):
            return [entry]
        match = next((t for t in data if isinstance(t, dict) and t.get("slug") == q), None)
        if not match:
            return []
        if match.get("count"):
            entry["count"] = int(match["count"])
        return [entry]

    def _headers(self):
        return dict(BROWSER_HEADERS, Accept="application/json", Referer=f"{self.base_url}/")

    def _download_headers(self):
        return dict(BROWSER_HEADERS, Referer=f"{self.base_url}/")

    def _tag_id(self, slug):
        params = urllib.parse.urlencode({"search": slug, "per_page": "20"})
        raw = self._open(f"{HOST}/wp-json/wp/v2/tags?{params}", headers=self._headers()).decode("utf-8", "replace")
        try:
            tags = json.loads(raw)
        except ValueError:
            raise ApiError("tag lookup wasn't JSON")
        if not isinstance(tags, list):
            raise ApiError("tag lookup failed")
        match = next((t for t in tags if isinstance(t, dict) and t.get("slug") == slug), None)
        if not match or not match.get("id"):
            raise ApiError(f'no tag "{slug}"')
        return int(match["id"])

    def _page(self, query, cursor):
        page = cursor or 1
        if page == 1:
            self._tag = self._tag_id(query)
        params = urllib.parse.urlencode({"tags": str(self._tag), "per_page": "50", "page": str(page)})
        referer = f"{self.base_url}/tag/{query}/"
        raw = self._open(f"{HOST}/wp-json/wp/v2/posts?{params}",
                         headers=dict(self._headers(), Referer=referer)).decode("utf-8", "replace")
        try:
            data = json.loads(raw)
        except ValueError:
            raise ApiError(f"posts page {page} wasn't JSON")
        posts = posts_from_wp(data)
        return posts, (page + 1 if posts and page < 5 else None)
