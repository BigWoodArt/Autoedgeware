"""Decouples downloading from displaying. PresetWorkers download in
batches per source (however fast that source responds) and drop
finished items straight into this shared pool. A separate DisplayWorker
pops ONE random item off the pool on its own steady timer, so display
order mixes freely across sources and presets regardless of which one
happens to be mid-download right now - e.g. 20 Reddit images and a
Soundgasm file can all be waiting at once, and what shows next is
picked at random from that whole waiting pool, not source-by-source."""
import random
import threading
import time


class DisplayQueue:
    """Thread-safe pool of (preset, item) pairs waiting to be shown."""

    def __init__(self):
        self._items = []
        self._lock = threading.Lock()

    def add_many(self, preset, items):
        with self._lock:
            self._items.extend((preset, item) for item in items)

    def pop_random(self):
        with self._lock:
            if not self._items:
                return None
            idx = random.randrange(len(self._items))
            return self._items.pop(idx)

    def __len__(self):
        with self._lock:
            return len(self._items)


class DisplayWorker(threading.Thread):
    """Pops one random item off the queue every interval_seconds and
    hands it to on_display(preset, item) - e.g. the Edgeware popup
    bridge. Runs independently of however many PresetWorkers happen to
    be downloading at any given moment."""

    def __init__(self, queue, on_display, interval_seconds=5, on_log=None):
        super().__init__(daemon=True)
        self.queue = queue
        self.on_display = on_display
        self.interval_seconds = max(1, interval_seconds)
        self.on_log = on_log or (lambda msg, level="info": None)
        self.stop_event = threading.Event()

    def stop(self):
        self.stop_event.set()

    def run(self):
        while not self.stop_event.is_set():
            waited = 0
            while waited < self.interval_seconds and not self.stop_event.is_set():
                time.sleep(min(1, self.interval_seconds - waited))
                waited += 1
            if self.stop_event.is_set():
                break
            entry = self.queue.pop_random()
            if entry:
                preset, item = entry
                try:
                    self.on_display(preset, item)
                except Exception as ex:
                    self.on_log(f"display callback failed: {ex}", "error")
