"""Preset Finder logic: turn one keyword into ready-to-tick (site, search) suggestions by asking each
site's own lookup. No Tk here, so it can be tested.

Sites that have a suggest() (Reddit, Danbooru, e621, ...) return real matches with counts. Sites that
do not still get one 'search this term as typed' entry, so every chosen site can be part of a preset.
Anything that points at minors is dropped (core/safety.py)."""
import concurrent.futures
import re
from dataclasses import dataclass
from typing import Optional

from core.safety import is_blocked, query_blocked
from sources.base import Source

PER_SITE = 5          # suggestions kept per site
WARN_ABOVE = 30       # more sources than this makes downloads slow
SEARCH_TIMEOUT = 6.0  # seconds to wait for all sites

# (site id, ticked at first). Only sites that take a keyword/tag/subreddit; audio and
# creator-page sites need a user name or link, so they are added by hand in Edit Preset.
FINDER_SITES = [
    ("reddit", True), ("redgifs", True), ("realbooru", True), ("hypnohub", True), ("hypnotube", True), ("pmvhaven", False),
    ("gelbooru", False), ("rule34", False), ("safebooru", False),
    ("danbooru", False), ("e621", False), ("yandere", False), ("konachan", False),
    ("derpibooru", False), ("wallhaven", False), ("lemmy", False), ("civitai", False),
    ("tbib", False), ("xbooru", False), ("pornpics", False), ("babehub", False), ("pictoa", False),
    ("elitebabes", False), ("erome", False),
]
# Registered sites left out of the list on purpose (they need a user name, link or key, not a keyword):
NOT_SEARCHABLE = {"soundgasm", "freesound", "coomer", "fapello", "kemono"}
PER_SITE_MORE = {"redgifs": 12}   # niches and tags both listed
DEFAULT_TICK_PER_SITE = {"reddit": 3, "redgifs": 2}   # every other site: its top result


@dataclass
class Pick:
    site: str
    value: str                 # what goes in the preset row's query
    label: str                 # what the list shows
    count: Optional[int] = None
    ticked: bool = False
    note: str = ""             # e.g. 'no answer in time'

    @property
    def key(self):
        return (self.site, self.value.strip().lower())


def has_suggest(source_cls):
    own = getattr(source_cls, "suggest", None)
    base = Source.suggest
    return own is not None and getattr(own, "__func__", own) is not getattr(base, "__func__", base)


def clean_term(term):
    return re.sub(r"\s+", " ", (term or "").strip())[:80]


def _typed(site, source_cls, term, note=""):
    label = getattr(source_cls, "label", site)
    return Pick(site, term, f"{label}: search \"{term}\"", None, False, note)


def _safe_suggest(source_cls, term):
    try:
        return list(source_cls.suggest(term) or [])
    except Exception:
        return []


def find(term, sites, registry, per_site=PER_SITE, timeout=SEARCH_TIMEOUT, suggest_fn=None):
    """Returns {site: [Pick, ...]} in the order of `sites`. Raises ValueError for a blocked or empty term.
    suggest_fn(source_cls, term) exists so tests need no network."""
    term = clean_term(term)
    if not term:
        raise ValueError("Type a word to search for.")
    if query_blocked(term):
        raise ValueError("That search is not allowed.")
    suggest_fn = suggest_fn or _safe_suggest
    out = {site: [] for site in sites}
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(sites)))
    futures = {}
    for site in sites:
        cls = registry.get(site)
        if cls is None:
            continue
        if has_suggest(cls):
            futures[pool.submit(suggest_fn, cls, term)] = site
        else:
            out[site] = [_typed(site, cls, term)]
    done, not_done = concurrent.futures.wait(futures, timeout=timeout)
    pool.shutdown(wait=False, cancel_futures=True)
    for fut in done:
        site = futures[fut]
        cls = registry[site]
        picks = []
        limit = PER_SITE_MORE.get(site, per_site)
        for s in fut.result()[:limit * 2]:
            value = str(s.get("value", "")).strip()
            label = str(s.get("label", value)).strip()
            if not value or is_blocked(value) or is_blocked(label):
                continue
            count = s.get("count")
            picks.append(Pick(site, value, label, count if isinstance(count, int) else None))
        out[site] = picks[:limit] or [_typed(site, cls, term, "no matches found")]
    for fut in not_done:
        site = futures[fut]
        out[site] = [_typed(site, registry[site], term, "no answer in time")]
    for site, picks in out.items():
        for p in picks[:DEFAULT_TICK_PER_SITE.get(site, 1)]:
            p.ticked = True       # every searched site: its top result(s) start ticked
    return out


def merge(existing, found):
    """Add new picks to the list without duplicating or changing what is already there (ticks stay)."""
    have = {p.key for p in existing}
    for picks in found.values():
        for p in picks:
            if p.key not in have:
                existing.append(p)
                have.add(p.key)
    return existing


def to_sources(picks):
    from ae_settings.preset import source_entry
    seen, out = set(), []
    for p in picks:
        if p.ticked and p.key not in seen:
            seen.add(p.key)
            out.append(source_entry(p.site, p.value))
    return out
