"""PornPics and Babehub picture-gallery scrapers (one file, shared engine).

Both sites work the same way: a search (or a tag page) lists galleries, and each gallery page holds its pictures
(full size, no login) with tags and a rating. This scraper searches, opens the galleries one after another, and
downloads every picture inside each one until the limit is reached.

Query can be a search word ("blonde"), a tag/model/listing page link, or one gallery link.
Rating: PornPics shows a percent score, Babehub shows a like count. Neither page shows a date, so there is no
date sort. The min-score box skips whole galleries below that rating before any picture is downloaded.
"""
import html
import json
import os
import random
import re
import urllib.error
import urllib.parse

from sources.json_board import JsonBoardSource, ApiError

BROWSER_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9",
}
IMG_EXTS = r"(?:jpe?g|png|webp|gif)"
SCORE_TOKEN = re.compile(r"\bscore:>=(\d+)\b")


def _score_choices(values, label):
    return [("", "Any", {})] + [(str(n), label.format(n=n), {"query_suffix": f"score:>={n}"}) for n in values]


def _clean(text):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", text or ""))).strip()


class _GallerySite(JsonBoardSource):
    category = "Gallery sites"
    has_media_priority = False
    priority_media = "image"
    default_limit = 60
    min_interval = 1.5
    check_query = "blonde"
    query_hint = "search word, tag page link or gallery link"
    order_choices = [("site", "Site order", {})]
    default_order = "site"
    order_help = ("Galleries come in the site's own order (no date is shown on its pages). Every picture in "
                  "each gallery is downloaded, gallery after gallery, until the limit.")
    base_url = ""
    gallery_re = None            # finds gallery links in a listing page (group 0 = the link)
    stem_re = None               # picture file name -> post id part
    full_page = 9999             # galleries on a full results page (more pages follow); a next link also says so

    # ---- per-site hooks
    def _search_url(self, query):
        return f"{self.base_url}/?q={urllib.parse.quote_plus(query)}"

    def _page_candidates(self, listing_url, n, query):
        """Likely addresses for result page n (n >= 2), best guess first."""
        return []

    def _parse_gallery(self, raw, url):
        """-> (title, tags, rating or None, [picture urls])"""
        raise NotImplementedError

    @classmethod
    def suggest(cls, query):
        """One entry for the word if the site's search lists galleries for it; [] when it lists none; the plain
        entry when the site can't be reached. Never raises."""
        q = " ".join((query or "").split())
        if not q:
            return []
        entry = {"value": q, "label": f"{cls.label} {q}", "count": None}
        try:
            probe = cls()
            raw = probe._open(probe._search_url(q), timeout=8).decode("utf-8", "replace")
        except urllib.error.HTTPError as ex:
            return [] if ex.code == 404 else [entry]
        except Exception:
            return [entry]
        if "Just a moment" in raw[:3000]:
            return [entry]
        n = len(probe._gallery_links(raw))
        if not n:
            return []
        more = bool(probe._next_link(raw)) or n >= probe.full_page      # the sites give no total, so say "N+"
        entry["label"] = f"{cls.label} {q}  -  {n}{'+' if more else ''} galleries on the first page"
        return [entry]

    # ---- life cycle
    def fetch(self, query, limit, sort, time_range, dest_dir, log, progress, stop_event,
              early_preview_cb=None, randomize=False, prioritize_images=False,
              item_cb=None, skip_ids=None):
        self._rand, self._log, self._stop = randomize, log, stop_event
        self._queue, self._queued = [], set()
        self._listing, self._page_no, self._good, self._single = None, 0, None, False
        self._min_score = 0
        self._galleries = 0
        return super().fetch(query, limit, sort, time_range, dest_dir, log, progress, stop_event,
                             early_preview_cb, randomize, prioritize_images, item_cb, skip_ids)

    def _normalize_query(self, query):
        m = SCORE_TOKEN.search(query)
        if m:
            self._min_score = int(m.group(1))
            query = SCORE_TOKEN.sub("", query)
        return " ".join(query.split())

    def _headers(self):
        return dict(BROWSER_HEADERS, Accept="text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
                    Referer=self.base_url + "/")

    def _download_headers(self):
        return dict(BROWSER_HEADERS, Referer=self.base_url + "/")

    def _get_text(self, url):
        raw = self._open(url).decode("utf-8", "replace")
        if "Just a moment" in raw[:3000] and "<html" in raw[:3000].lower():
            raise ApiError("got a browser-check page instead of the site")
        return raw

    # ---- paging: search page -> galleries -> pictures
    def _page(self, query, cursor):
        """One call = the pictures of the next usable gallery. Returns ([], None) when nothing is left."""
        while not self._stop.is_set():
            if not self._queue:
                if self._single or not self._load_more_galleries(query):
                    return [], None
                continue
            gallery = self._queue.pop(0)
            try:
                posts = self._gallery_posts(gallery)
            except Exception as ex:
                self._log(f"[{self.label}] could not open {gallery}: {self._explain(ex)}", "warning")
                continue
            if posts:
                return posts, "more"
        return [], None

    def _gallery_links(self, text):
        text = text.replace("\\/", "/")
        out = []
        for m in self.gallery_re.finditer(text):
            link = m.group(0)
            if link.startswith("/"):
                link = self.base_url + link
            link = link.split("?")[0].split("#")[0]
            if not link.endswith("/"):
                link += "/"
            if link not in out:
                out.append(link)
        return out

    def _is_gallery_url(self, url):
        return bool(self.gallery_re.fullmatch(url.split("?")[0].split("#")[0].rstrip("/") + "/")) or \
            bool(self.gallery_re.fullmatch(url.split("?")[0].split("#")[0]))

    def _add_galleries(self, links):
        fresh = [g for g in links if g not in self._queued]
        self._queued.update(fresh)
        if self._rand:
            random.shuffle(fresh)
        self._queue.extend(fresh)
        return len(fresh)

    def _load_more_galleries(self, query):
        if self._listing is None:                                   # first call: work out where to start
            if query.lower().startswith("http"):
                if self._is_gallery_url(query):
                    self._single = True
                    self._queue = [query.split("?")[0]]
                    self._log(f"[{self.label}] opening that gallery")
                    return True
                self._listing = query
            else:
                self._listing = self._search_url(query)
            self._page_no = 1
            try:
                raw = self._get_text(self._listing)
            except Exception as ex:
                self._log(f"[{self.label}] search request failed: {self._explain(ex)}", "error")
                return False
            added = self._add_galleries(self._gallery_links(raw))
            self._next_hint = self._next_link(raw)
            self._log(f"[{self.label}] page 1: {added} gallery(ies) listed")
            return bool(added)

        n = self._page_no + 1
        cands = ([self._next_hint] if self._next_hint else []) + self._page_candidates(self._listing, n, query)
        if self._good is not None:                                  # the style that worked last time goes first
            cands.sort(key=lambda c: 0 if self._style(c) == self._good else 1)
        tried = set()
        for url in cands:
            if url in tried or self._stop.is_set():
                continue
            tried.add(url)
            try:
                raw = self._get_text(url)
            except Exception:
                continue
            added = self._add_galleries(self._gallery_links(raw))
            if added:
                self._page_no, self._good = n, self._style(url)
                self._next_hint = self._next_link(raw)
                self._log(f"[{self.label}] page {n}: {added} more gallery(ies)")
                return True
        self._log(f"[{self.label}] no further result pages found - the search is used up")
        return False

    @staticmethod
    def _style(url):
        m = re.search(r"([?&](?:offset|page|paged)=)|(/page/)|(srch\.php)", url)
        return m.group(0) if m else "other"

    @staticmethod
    def _next_link(raw):
        for pat in (r'<link[^>]+rel=["\']next["\'][^>]*href=["\']([^"\']+)["\']',
                    r'<a[^>]+rel=["\']next["\'][^>]*href=["\']([^"\']+)["\']',
                    r'<a[^>]+href=["\']([^"\']+)["\'][^>]*rel=["\']next["\']',
                    r'<li[^>]+class=["\'][^"\']*\bnext\b[^"\']*["\'][^>]*>\s*<a[^>]+href=["\']([^"\']+)["\']'):
            m = re.search(pat, raw, re.I)
            if m:
                return html.unescape(m.group(1))
        return None

    def _gallery_posts(self, url):
        raw = self._get_text(url)
        title, tags, rating, pics = self._parse_gallery(raw, url)
        gid = (re.search(r"-(\d+)/?$", url.split("?")[0]) or re.search(r"(\d+)", url) or [None, "0"])[1]
        self._galleries += 1
        if not pics:
            self._log(f"[{self.label}] no pictures found on {url} (the page layout may have changed)", "warning")
            return []
        if self._min_score and rating is not None and rating < self._min_score:
            self._log(f"[{self.label}] skipped a gallery rated {rating:g} (minimum {self._min_score}): {title[:50]}")
            return []
        self._log(f"[{self.label}] gallery {self._galleries}: {title[:60]} - {len(pics)} picture(s)"
                  + (f", rating {rating:g}" if rating is not None else ""))
        posts = []
        for pic in pics:
            stem = os.path.splitext(pic.split("?")[0].rsplit("/", 1)[-1])[0]
            posts.append({"id": f"{gid}_{stem}", "url": pic, "tags": tags, "title": title, "text": title})
        return posts


class PornPicsSource(_GallerySite):
    id, label, prefix = "pornpics", "PornPics", "pnp_"
    base_url = "https://www.pornpics.com"
    full_page = 20
    gallery_re = re.compile(r"(?:https?://(?:www\.)?pornpics\.com)?/galleries/[a-z0-9][a-z0-9-]*-\d+/?")
    min_score_choices = _score_choices((70, 80, 90, 95), "{n}%+ rated")
    order_help = _GallerySite.order_help + " Min score = the gallery's percent rating."

    def _page_candidates(self, listing_url, n, query):
        off = (n - 1) * 20
        sep = "&" if "?" in listing_url else "?"
        out = []
        if "/?q=" in listing_url:
            out.append(f"{self.base_url}/search/srch.php?q={urllib.parse.quote_plus(query)}&lang=en&limit=20&offset={off}")
        out += [f"{listing_url}{sep}limit=20&offset={off}", f"{listing_url}{sep}offset={off}",
                f"{listing_url}{sep}page={n}"]
        return out

    def _parse_gallery(self, raw, url):
        m = re.search(r"<h1[^>]*>(.*?)</h1>", raw, re.S) or re.search(r"<title>(.*?)</title>", raw, re.S)
        title = re.sub(r"\s*-\s*PornPics\.com\s*$", "", _clean(m.group(1))) if m else ""
        tags = []
        i = raw.find('gallery-info__title">Tags')
        if i >= 0:
            block = raw[i:i + 8000]
            end = block.find("gallery-info__item", 30)
            block = block[:end] if end > 0 else block
        tags = [_clean(t) for t in re.findall(r"""<a[^>]+href=['"]/tags/[^'"]+['"][^>]*>(.*?)</a>""", block, re.S)]
        m = re.search(r'class="rate-count">\s*([\d.]+)\s*%', raw)
        rating = float(m.group(1)) if m else None
        pics = []
        for p in re.findall(r"""href=['"](https://cdni\.pornpics\.com/1280/[^'"]+?\.%s)['"]""" % IMG_EXTS, raw, re.I):
            if p not in pics:
                pics.append(p)
        return title, [t for t in tags if t], rating, pics


class BabehubSource(_GallerySite):
    id, label, prefix = "babehub", "Babehub", "bbh_"
    base_url = "https://www.babehub.com"
    gallery_re = re.compile(r"(?:https?://(?:www\.)?babehub\.com)?/[a-z0-9][a-z0-9-]*-\d+/?(?=[\"'\s<?#]|$)")
    min_score_choices = _score_choices((25, 50, 100, 200), "{n}+ likes")
    order_help = _GallerySite.order_help + " Min score = the gallery's like count."

    def _search_url(self, query):
        return f"{self.base_url}/search/post/{urllib.parse.quote(query, safe='')}/"

    def _page_candidates(self, listing_url, n, query):
        # Real layout (checked on a saved results page): /search/post/<word>/ and /search/post/<word>/mpage/2/
        base = re.sub(r"/mpage/\d+/?$", "", listing_url.split("?")[0]).rstrip("/")
        return [f"{base}/mpage/{n}/", f"{base}/page/{n}/", f"{listing_url.rstrip('/')}?page={n}"]

    def _gallery_links(self, text):
        links = super()._gallery_links(text)
        skip = ("/tag/", "/model/", "/channel/", "/sort/", "/page/", "/mpage/", "/go/", "/search/")
        return [g for g in links if not any(s in g for s in skip)]

    def _parse_gallery(self, raw, url):
        m = re.search(r"<h1[^>]*>(.*?)</h1>", raw, re.S) or re.search(r"<title>(.*?)</title>", raw, re.S)
        title = _clean(m.group(1)) if m else ""
        tags = []
        i = raw.find("link-btn scroll")
        if i >= 0:
            block = raw[i:]
            block = block[:block.find("</p>")]
            tags = [_clean(t) for t in re.findall(
                r"""<a[^>]+href=["']https://www\.babehub\.com/(?:tag|model|channel)/[^"']+["'][^>]*>(.*?)</a>""",
                block, re.S)]
        m = re.search(r'id="thelike"[^>]*>\s*(\d[\d,]*)', raw)
        rating = float(m.group(1).replace(",", "")) if m else None
        pics = []
        for p in re.findall(r"""<a[^>]+data-fancybox=["']images["'][^>]*?\shref=["'](https://cdn\.babehub\.com/[^"']+?\.%s)["']"""
                            % IMG_EXTS, raw, re.I):
            if p not in pics:
                pics.append(p)
        return title, [t for t in tags if t], rating, pics
