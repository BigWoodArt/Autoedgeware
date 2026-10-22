"""Turns the first-run form into a preset's source list. No Tk here, so it can be tested."""
import re

from ae_settings.preset import source_entry

BAD_NAME_CHARS = re.compile(r'[\\/:*?"<>|]')


def safe_name(name, fallback="My Preset"):
    cleaned = BAD_NAME_CHARS.sub("", (name or "")).strip().strip(".")
    return cleaned[:60] or fallback


def split_list(text):
    """'a, b,, c' -> ['a','b','c'] (commas or new lines; duplicates dropped, order kept)."""
    seen, out = set(), []
    for part in re.split(r"[,\n]", text or ""):
        part = part.strip()
        if part and part.lower() not in seen:
            seen.add(part.lower())
            out.append(part)
    return out


def clean_subreddit(text):
    text = text.strip()
    text = re.sub(r"^(https?://)?(www\.)?reddit\.com/", "", text)
    text = re.sub(r"^/?r/", "", text)
    return text.strip("/ ")


def build_sources(keywords_text, subreddits_text, sites):
    """sites: list of source ids. Reddit uses subreddits; every other site uses the keywords.
    Raises ValueError when nothing usable would result."""
    keywords = split_list(keywords_text)
    subs = [s for s in (clean_subreddit(x) for x in split_list(subreddits_text)) if s]
    sources = []
    for site in sites:
        if site == "reddit":
            sources += [source_entry("reddit", s) for s in subs]
        else:
            sources += [source_entry(site, k) for k in keywords]
    if not sources:
        raise ValueError("Pick at least one site, and type a keyword (or a subreddit for Reddit).")
    return sources


def nature_sources():
    """The built-in starter: nature pictures and clips. Safe for anyone and needs no keys."""
    return [
        source_entry("reddit", "EarthPorn"),
        source_entry("reddit", "NatureGifs"),
        source_entry("wallhaven", "nature"),
    ]
