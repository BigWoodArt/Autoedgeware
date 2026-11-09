"""Reddit for Autoedgeware: the Media Collector file in sources/, plus albums.

The RSS feed shows only the first picture of a gallery post. For a gallery link this reads the post's own
JSON (post link + .json), lists every picture in order, saves all of them (up to MAX_ALBUM), and keeps
the post id the same for the whole album. One extra request per gallery post."""
import html
import json
import os
import re
import urllib.error

from sources.reddit_source import RedditSource as _Reddit

MAX_ALBUM = 30
REDGIFS_LINK = re.compile(r"redgifs\.com/(?:watch|ifr)/([A-Za-z0-9]+)", re.IGNORECASE)
MIME_EXT = {"image/jpg": ".jpg", "image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp"}


def _old_reddit(url):
    return re.sub(r"^https://(?:www\.)?reddit\.com", "https://old.reddit.com", url, count=1, flags=re.I)


def _looks_like_json(text):
    return bool(text) and text.lstrip()[:1] in "[{"


def _album_why(got):
    if got == "":
        return "page was not JSON"
    return got


def album_from_json(text):
    """[[(url, ext, label, type), ...] one candidate list per picture, in album order] from a post's JSON.
    Returns [] when the post is not a gallery. Never raises."""
    try:
        data = json.loads(text)
        post = data[0]["data"]["children"][0]["data"]
        if not post.get("gallery_data") and post.get("crosspost_parent_list"):
            post = post["crosspost_parent_list"][0]            # a crosspost of a gallery
        order = [i.get("media_id") for i in (post.get("gallery_data") or {}).get("items", [])]
        meta = post.get("media_metadata") or {}
    except Exception:
        return []
    out = []
    for n, mid in enumerate(order[:MAX_ALBUM], start=1):
        m = meta.get(mid) or {}
        if m.get("status", "valid") != "valid":
            continue
        s = m.get("s") or {}
        label = f"album {n}/{len(order)}"
        cands = []
        if m.get("e") == "AnimatedImage" and s.get("mp4"):
            cands.append((html.unescape(s["mp4"]), ".mp4", label, "video"))
        else:
            ext = MIME_EXT.get(str(m.get("m", "")).lower(), ".jpg")
            if re.fullmatch(r"[A-Za-z0-9]+", str(mid)):
                cands.append((f"https://i.redd.it/{mid}{ext}", ext, label, "image"))
            if s.get("u"):
                cands.append((html.unescape(s["u"]), ext, label + " (preview)", "image"))
            elif s.get("gif"):
                cands.append((html.unescape(s["gif"]), ".gif", label, "image"))
        if cands:
            out.append(cands)
    return out


class RedditSource(_Reddit):
    # "www" tries www then, on 403 or an HTML block page, old.reddit.com once.
    # "old" keeps using the host that answered. "off" stops asking: Reddit is blocking album JSON,
    # and every further gallery would spend another rate-limit slot to learn the same fact.
    _json_route = "www"

    def __init__(self):
        super().__init__()
        self._albums = {}          # post id -> candidate lists of pictures 2..n
        self._log = lambda *a, **k: None
        self._skip = None          # the preset's seen ids (shared with every site)
        self._rg_of_post = {}      # reddit post id -> the Redgifs clip id it links to

    @classmethod
    def reset_runtime(cls):
        """Test hook: album route and the shared Reddit clock."""
        cls._json_route = "www"
        from sources.reddit_source import RateLimiter
        RateLimiter.reset_shared()

    def _fetch_json(self, url):
        """JSON text, '' when the body is HTML, or the exception."""
        try:
            text = self._http_get_text(url)
        except Exception as ex:
            return ex
        return text if _looks_like_json(text) else ""

    def _album_json(self, url):
        """The post's JSON, or None. A 403 or an HTML block page tries old.reddit.com once,
        then stops asking for the rest of this run."""
        route = type(self)._json_route
        if route == "off":
            return None
        first = _old_reddit(url) if route == "old" else url
        got = self._fetch_json(first)
        if isinstance(got, str) and got:
            return got
        blocked = got == "" or (isinstance(got, urllib.error.HTTPError) and got.code == 403)
        old = _old_reddit(url)
        if route == "www" and blocked and old != first:
            got = self._fetch_json(old)
            if isinstance(got, str) and got:
                type(self)._json_route = "old"
                return got
            type(self)._json_route = "off"
            self._log(f"   -> album lookup failed ({_album_why(got)}); later galleries keep the first picture only", "warning")
            return None
        self._log(f"   -> album lookup failed ({_album_why(got)}); saving the first picture only", "warning")
        if route == "old" and blocked:
            type(self)._json_route = "off"
        return None

    @staticmethod
    def _post_id(entry):
        m = re.search(r"/comments/([a-z0-9]+)/", entry.get("link", ""), re.IGNORECASE)
        return m.group(1).lower() if m else ""

    def build_candidates(self, entry):
        link = self.extract_submission_link(entry.get("content_html", "")) or ""
        pid = self._post_id(entry)
        m = REDGIFS_LINK.search(link)
        if m and pid:
            rg = m.group(1).lower()
            if self._skip is not None and f"rg_{rg}" in self._skip:
                self._log(f"   -> already have Redgifs clip {rg} (same clip as another post); skipped")
                self._skip.add(pid)
                return []
            self._rg_of_post[pid] = rg
        if pid and re.search(r"reddit\.com/gallery/", link, re.IGNORECASE) and not getattr(self, "_site_check", False):
            text = self._album_json(entry["link"].split("?")[0].rstrip("/") + ".json?raw_json=1")
            pics = album_from_json(text) if text else []
            if pics:
                self._albums[pid] = pics[1:]
                return pics[0]
        return super().build_candidates(entry)

    def fetch(self, query, limit, sort, time_range, dest_dir, log, progress, stop_event,
              early_preview_cb=None, randomize=False, prioritize_images=False,
              item_cb=None, skip_ids=None):
        from core.media_item import MediaItem
        self._log = log
        self._skip = skip_ids
        extras = []

        def save_rest(item):
            wanted = getattr(self, "wanted_types", None)
            title = re.sub(r'[\\/*?:"<>|]', "", item.caption or "")[:40].strip()
            for cands in self._albums.pop(item.post_id, []):
                if stop_event.is_set():
                    break
                if wanted and cands[0][3] not in wanted:
                    continue
                for url, ext, label, kind in cands:
                    result, path = self.download_one(url, ext, title, dest_dir, log)
                    if result == "ok":
                        log(f"   -> {label}: saved")
                        extra = MediaItem(file_path=path, caption=item.caption, media_type=kind,
                                          source_label=item.source_label, post_id=item.post_id,
                                          source_type="reddit")
                        extras.append(extra)
                        if item_cb is not None:
                            item_cb(extra)
                        break
                    if result == "dupe":
                        break

        def on_item(item):
            rg = self._rg_of_post.pop(item.post_id, "")
            if rg and self._skip is not None:
                self._skip.add(f"rg_{rg}")      # the Redgifs site will now skip this clip
            if item_cb is not None:
                item_cb(item)
            save_rest(item)

        results = super().fetch(query, limit, sort, time_range, dest_dir, log, progress, stop_event,
                                early_preview_cb, randomize, prioritize_images, on_item, skip_ids)
        return list(results) + extras
