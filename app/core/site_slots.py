"""One fetch at a time per rate-limited site, shared by every preset and source.

Each source object paces its own requests, so two Reddit sources used to run two separate clocks and hit
Reddit at double the safe rate, which makes the 429 'slow down' replies (and the 60 second waits) worse.
With one slot per site, a second Reddit source waits its turn, while every OTHER site keeps downloading
in parallel. Fast image boards are not limited here. No Tk or Edgeware imports; testable on its own."""
import contextlib
import threading

ONE_AT_A_TIME = {"reddit", "redgifs", "erome", "soundgasm", "freesound", "coomer", "fapello", "kemono", "hypnotube", "pmvhaven", "pornpics", "babehub"}
_slots = {site: threading.Semaphore(1) for site in ONE_AT_A_TIME}


def acquire(site, stop_event, on_wait=None, poll=0.5):
    """True once the slot is ours; False if stop was requested while waiting. Sites without a limit
    return True at once."""
    sem = _slots.get(site)
    if sem is None:
        return True
    if sem.acquire(blocking=False):
        return True
    if on_wait:
        on_wait()
    while not stop_event.is_set():
        if sem.acquire(timeout=poll):
            return True
    return False


def release(site):
    sem = _slots.get(site)
    if sem is not None:
        sem.release()


@contextlib.contextmanager
def slot(site, stop_event, on_wait=None):
    got = acquire(site, stop_event, on_wait)
    try:
        yield got
    finally:
        if got:
            release(site)
