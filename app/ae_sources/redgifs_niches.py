"""Redgifs for Autoedgeware: the Media Collector file in sources/, plus niches and tag picks.

Redgifs "niches" are curated playlists. A typed word often matches a niche when it matches no tag
(or only noisy text). So a plain word now goes:
  1. the best matching niches (3 at most, with enough clips), shared out evenly;
  2. else Redgifs' own tag of that name (the old way);
  3. else a free-text search, keeping only clips whose text really holds the word.
Query forms a preset row can hold:  word | niche:<id> | tag:<Tag> | a,b (several tags, old way)."""
import json
import math
import urllib.parse
from collections import Counter

from sources.redgifs_source import RedgifsSource as _Redgifs

API = "https://api.redgifs.com"
MIN_NICHE_GIFS = 20       # a niche with fewer clips is not worth a row
MAX_NICHES = 3            # niches pulled from for one typed word
# gifs/search order -> niches/{id}/gifs order (that API knows: trending, oldest, latest, best, hot)
NICHE_ORDER = {"score": "best", "trending": "trending", "latest": "latest",
               "top": "best", "top7": "hot", "top28": "best"}
SUGGEST_NICHES = 6
SUGGEST_TAGS = 6


def _gifs_of(data):
    """The list of clips in an API answer, whatever it calls it."""
    if isinstance(data, dict):
        if isinstance(data.get("gifs"), list):
            return data["gifs"]
        for v in data.values():
            if isinstance(v, list) and v and isinstance(v[0], dict) and "urls" in v[0]:
                return v
        return []
    return data if isinstance(data, list) else []


def _text_of(gif):
    tags = " ".join(str(t) for t in (gif.get("tags") or []))
    return f"{gif.get('description') or ''} {gif.get('title') or ''} {tags}".lower()


def _holds_word(gif, word):
    text = _text_of(gif)
    return all(w in text for w in word.lower().split())


class RedgifsSource(_Redgifs):
    _mode = None          # None | ("niche", id) | ("text", word)

    # ---------- lookups ----------
    def _api(self, path, params, log=None):
        token = self._get_token(log or (lambda *a, **k: None))
        if not token:
            return None
        url = f"{API}{path}?" + urllib.parse.urlencode(params)
        return json.loads(_Redgifs._get_text(self, url, extra_headers={"Authorization": f"Bearer {token}"}))

    def find_niches(self, word, log=None):
        """[{'id','name','gifs'}] best first: most clips, those with too few dropped."""
        try:
            data = self._api("/v2/niches", {"query": word, "count": 20, "page": 1}, log)
        except Exception as ex:
            if log:
                log(f"[Redgifs] niche lookup failed: {ex}", "warning")
            return []
        out = []
        for n in (data or {}).get("niches", []) if isinstance(data, dict) else []:
            if isinstance(n, dict) and n.get("id") and (n.get("gifs") or 0) >= MIN_NICHE_GIFS:
                out.append({"id": str(n["id"]), "name": str(n.get("name") or n["id"]), "gifs": int(n.get("gifs") or 0)})
        out.sort(key=lambda n: -n["gifs"])
        return out

    def common_tags(self, word, log=None):
        """(tags worth trying, results counted): the tags most used by clips whose text holds the word."""
        try:
            data = self._api("/v2/gifs/search", {"type": "g", "query": word, "order": "score", "count": 80, "page": 1}, log)
        except Exception as ex:
            if log:
                log(f"[Redgifs] tag lookup failed: {ex}", "warning")
            return [], 0
        gifs = [g for g in _gifs_of(data) if isinstance(g, dict) and _holds_word(g, word)]
        seen = Counter()
        names = {}
        for g in gifs:
            for t in {str(t) for t in (g.get("tags") or []) if str(t).strip()}:
                seen[t.lower()] += 1
                names.setdefault(t.lower(), t)
        ranked = sorted(seen.items(), key=lambda kc: (-kc[1], kc[0]))          # same count: alphabetical, so it is stable
        top = [(names[k], c) for k, c in ranked if c >= 2][:SUGGEST_TAGS]
        return top, len(gifs)

    @classmethod
    def suggest(cls, query):
        """Niches first (with clip counts), then the tags most used by clips that mention the word."""
        word = query.strip().lstrip("#")
        if not word:
            return []
        inst = cls()
        out = [{"value": f"niche:{n['id']}", "label": f"Redgifs niche: {n['name']}", "count": n["gifs"]}
               for n in inst.find_niches(word)[:SUGGEST_NICHES]]
        tags, total = inst.common_tags(word)
        out += [{"value": f"tag:{name}", "label": f"Redgifs tag: {name}  (in {c} of {total} matches)", "count": None}
                for name, c in tags]
        return out

    # ---------- the shared fetch, pointed somewhere else ----------
    def _resolve_tags(self, text, token, log):
        return [text.strip()] if self._mode else super()._resolve_tags(text, token, log)

    def _tag_hits(self, gifs, terms):
        return (0, 0) if self._mode else _Redgifs._tag_hits(gifs, terms)

    def _get_text(self, url, extra_headers=None, timeout=15):
        mode = self._mode
        if not mode or "/v2/gifs/search" not in url:
            return super()._get_text(url, extra_headers, timeout)
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
        page = q.get("page", "1")
        if mode[0] == "niche":
            new = f"{API}/v2/niches/{urllib.parse.quote(mode[1], safe='')}/gifs?" + urllib.parse.urlencode(
                {"order": NICHE_ORDER.get(q.get("order"), "best"), "count": q.get("count", 80), "page": page})
        else:
            new = f"{API}/v2/gifs/search?" + urllib.parse.urlencode(
                {"type": "g", "query": mode[1], "order": q.get("order", "score"), "count": q.get("count", 80), "page": page})
        data = json.loads(super()._get_text(new, extra_headers, timeout))
        gifs = [g for g in _gifs_of(data) if isinstance(g, dict)]
        if mode[0] == "text":
            gifs = [g for g in gifs if _holds_word(g, mode[1])]
        seen = self._page_ids            # a site that ignores paging must not loop forever
        fresh = [g for g in gifs if g.get("id") not in seen]
        seen.update(g.get("id") for g in gifs)
        return json.dumps({"gifs": gifs if page == "1" else fresh})

    def _run(self, mode, query, limit, *args, **kw):
        self._mode, self._page_ids = mode, set()
        try:
            return _Redgifs.fetch(self, query, limit, *args, **kw)
        finally:
            self._mode = None

    def fetch(self, query, limit, sort, time_range, dest_dir, log, progress, stop_event,
              early_preview_cb=None, randomize=False, prioritize_images=False, item_cb=None, skip_ids=None):
        q = (query or "").strip()
        once = [early_preview_cb]

        def preview(items):
            cb, once[0] = once[0], None
            if cb:
                cb(items)
        rest = (sort, time_range, dest_dir, log, progress, stop_event)
        kw = dict(early_preview_cb=preview if early_preview_cb else None, randomize=randomize,
                  prioritize_images=prioritize_images, item_cb=item_cb, skip_ids=skip_ids)
        low = q.lower()
        if low.startswith("niche:"):
            nid = q[6:].strip()
            return self._run(("niche", nid), nid, limit, *rest, **kw)
        if low.startswith("tag:"):
            return _Redgifs.fetch(self, q[4:].strip(), limit, *rest, **kw)
        if "," in q or not q:
            return _Redgifs.fetch(self, q, limit, *rest, **kw)

        niches = self.find_niches(q, log)[:MAX_NICHES]
        if niches:
            log("[Redgifs] niches for '%s': %s" % (q, ", ".join(f"{n['name']} ({n['gifs']})" for n in niches)))
            results, share = [], math.ceil(limit / len(niches))
            for i, n in enumerate(niches):
                if stop_event.is_set() or len(results) >= limit:
                    break
                want = min(share, limit - len(results))
                results += self._run(("niche", n["id"]), n["id"], want, *rest, **kw)
            if results or stop_event.is_set():
                return results
            log(f"[Redgifs] the niches gave nothing; trying the tag '{q}'", "warning")
        results = _Redgifs.fetch(self, q, limit, *rest, **kw)
        if results or stop_event.is_set():
            return results
        log(f"[Redgifs] no tag '{q}'; searching clip text for the word instead", "info")
        return self._run(("text", q), q, limit, *rest, **kw)
