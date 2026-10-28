"""Live gallery smoke: python tools/gallery_smoke.py"""
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sources import SOURCE_BY_ID  # noqa: E402

CASES = [
    ("pictoa", "latex"),
    ("pictoa", "glamour-494"),
    ("elitebabes", "beautiful"),
    ("elitebabes", "captions"),
    ("porngif", "latex"),
    ("porngif", "captions"),
    ("pornhub_gifs", "latex"),
    ("pornhub_gifs", "captions"),
    ("pornhub_images", "latex"),
    ("pornhub_images", "beautiful"),
    ("pornpics", "latex"),
    ("pornpics", "beautiful"),
    ("sexcom_pics", "latex"),
    ("sexcom_gifs", "latex"),
]
# Site API has no matching posts (scraper exits cleanly).
OPTIONAL_EMPTY = {("elitebabes", "captions")}


def run_one(site, query, limit=1):
    src = SOURCE_BY_ID[site]()

    def logger(msg, level="info"):
        print(f"  [{level}] {msg}")

    items = src.fetch(
        query, limit, None, None, tempfile.mkdtemp(),
        logger, lambda *a: None, threading.Event(),
    )
    if not items and (site, query) in OPTIONAL_EMPTY:
        print(f"SKIP {site} '{query}' -> 0 (no site results; expected)\n")
        return True
    ok = len(items) >= 1
    print(f"{'OK' if ok else 'FAIL'} {site} '{query}' -> {len(items)} file(s)\n")
    return ok


def main():
    only = set(sys.argv[1:]) if len(sys.argv) > 1 else None
    ok_all = True
    for site, query in CASES:
        if only and query not in only and not (query == "glamour-494" and "latex" in only):
            continue
        if not run_one(site, query):
            ok_all = False
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
