"""How the source picker groups the sites. No Tk imports, so it can be tested on its own.

The shared scraper files carry their own 'category' text; those are not edited here (they are mirrored from
AutoPack Builder), so the picker groups by this table instead. A site missing from the table still shows up,
under Images, so a new source can never vanish from the list."""

GROUPS = [
    ("Image Boards", ["gelbooru", "realbooru", "hypnohub", "rule34", "safebooru", "tbib", "xbooru",
                      "e621", "danbooru", "yandere", "konachan", "derpibooru"]),
    ("Audio", ["soundgasm", "freesound"]),
    ("Video", ["redgifs", "erome", "hypnotube", "pmvhaven"]),
    ("Images", ["reddit", "wallhaven", "civitai", "lemmy", "coomer", "fapello", "kemono", "pornpics", "babehub", "pictoa"]),
]
FALLBACK_GROUP = "Images"


def grouped(source_ids):
    """[(group name, [source ids])] in picker order, only ids that exist, each exactly once."""
    available = list(source_ids)
    known = {sid for _g, ids in GROUPS for sid in ids}
    result = []
    for name, ids in GROUPS:
        members = [sid for sid in ids if sid in available]
        if name == FALLBACK_GROUP:
            members += [sid for sid in available if sid not in known]
        if members:
            result.append((name, members))
    return result
