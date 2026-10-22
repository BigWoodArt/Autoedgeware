"""Shuffle-bag + watchlist sizing for popup picks. No Edgeware or Tk imports.

Watchlist: how many recent shows of a kind are kept out of the draw. 50 once the pool passes 100 files,
else 20.

Bag (used for videos): every file plays once before any file plays again. Files are judged by what is on
disk at pick time, so a video downloaded mid-cycle is simply "not played yet" and joins the bag at once;
a deleted video just drops out. When every file has played, the bag refills (the watchlist still stops a
back-to-back repeat at the seam)."""

BIG_POOL = 100
BIG_WATCHLIST = 50
SMALL_WATCHLIST = 20


def watchlist_size(pool_total):
    return BIG_WATCHLIST if pool_total > BIG_POOL else SMALL_WATCHLIST


def bag_eligible(found, recent, played):
    """found: all files now on disk. recent: watchlist (iterable). played: set of files played this cycle.
    Returns (eligible, played). played is cleared (a new cycle) when no unplayed file is left outside the
    watchlist but files outside the watchlist exist. The set is edited in place and also returned."""
    recent = set(recent)
    live = set(found)
    played &= live                       # forget files that were deleted
    eligible = [f for f in found if f not in recent and f not in played]
    if not eligible:
        eligible = [f for f in found if f not in recent]
        if eligible:
            played.clear()
    return eligible, played
