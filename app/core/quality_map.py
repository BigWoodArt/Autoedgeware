"""The per-row Any / Good / Best choice, in terms of each site's own sort and minimum-score choices.

The shared scraper files (sources/) describe a site by two lists: order_choices and min_score_choices, and
Source.resolve(order, min_score) turns a pair of choice keys into {'sort', 'time_range', 'query_suffix'}.
Autoedgeware's preset rows only say Any / Good / Best, so this table says which pair each word means per site.
Any = nothing is changed. A site missing from the table has no Good / Best (the box stays on Any). No Tk."""

# site id -> {"Good": (order key, min score), "Best": (order key, min score)}
# A number as min score = "about this score": the nearest step the site offers is used.
TABLE = {
    "reddit":     {"Good": ("top_month", ""), "Best": ("top_year", "")},
    "redgifs":    {"Good": ("top_month", ""), "Best": ("top_all", "")},
    "freesound":  {"Good": ("downloads", ""), "Best": ("rating", "")},
    "lemmy":      {"Good": ("top_month", ""), "Best": ("top_year", "")},
    "wallhaven":  {"Good": ("favorites", ""), "Best": ("top_year", "")},
    "civitai":    {"Good": ("reactions_month", ""), "Best": ("reactions_all", "")},
    "gelbooru":   {"Good": ("score", 10), "Best": ("score", 50)},
    "realbooru":  {"Good": ("score", 5), "Best": ("score", 20)},
    "hypnohub":   {"Good": ("score", 5), "Best": ("score", 20)},
    "rule34":     {"Good": ("score", 20), "Best": ("score", 100)},
    "safebooru":  {"Good": ("score", 5), "Best": ("score", 20)},
    "tbib":       {"Good": ("score", 5), "Best": ("score", 20)},
    "xbooru":     {"Good": ("score", 5), "Best": ("score", 20)},
    "e621":       {"Good": ("score", 50), "Best": ("score", 200)},
    "danbooru":   {"Good": ("score", 20), "Best": ("score", 100)},
    "yandere":    {"Good": ("score", 20), "Best": ("score", 100)},
    "konachan":   {"Good": ("score", 20), "Best": ("score", 100)},
    "derpibooru": {"Good": ("score", 100), "Best": ("score", 500)},
    "pornpics":   {"Good": ("site", 80), "Best": ("site", 95)},
    "babehub":    {"Good": ("site", 25), "Best": ("site", 100)},
    "pmvhaven":   {"Good": ("rated", "r70"), "Best": ("rated", "r85")},
    "hypnotube":  {"Good": ("views", "r70"), "Best": ("rating", "r85")},
}


def supported(site_id):
    return site_id in TABLE


def _nearest(choices, wanted):
    """Key of the numeric choice closest to `wanted` (a tie goes to the higher one); '' if the site has none."""
    best = None
    for key, _label, _params in choices:
        if not str(key).isdigit():
            continue
        gap = (abs(int(key) - wanted), -int(key))
        if best is None or gap < best[0]:
            best = (gap, key)
    return best[1] if best else ""


def resolve(source_cls, quality):
    """{'sort', 'time_range', 'query_suffix'} (any may be missing) for Good / Best; {} for Any or an unknown site."""
    pair = TABLE.get(getattr(source_cls, "id", ""), {}).get(quality)
    if not pair:
        return {}
    order, score = pair
    if isinstance(score, int):
        score = _nearest(source_cls.min_score_choices, score)
    return source_cls.resolve(order, score) or {}
