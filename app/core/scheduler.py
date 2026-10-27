"""Runs one background thread per enabled Preset, plus one shared
DisplayWorker (core/display_queue.py). Each cycle, a PresetWorker
shuffles ALL of the preset's source rows (not just one) and downloads
from ALL of them CONCURRENTLY (one thread per source within the
cycle) rather than one after another - so a slow source (Reddit,
typically) doesn't block faster ones from finishing and becoming
available. Each source respects its own per-row limit if set (falling
back to the preset's limit) - handy for something like Soundgasm
where one long audio file per cycle is plenty, next to an image
source that wants 20.

Downloading and displaying are deliberately decoupled: as soon as a
source finishes, its new items go straight into the shared display
queue rather than being shown immediately - the DisplayWorker is what
actually pops items, one at a time at its own pace, chosen at RANDOM
from whatever has piled up across every source and preset. That way
"download 20 from Reddit, then 20 more from Gelbooru" doesn't mean
"show all 20 Reddit ones before any Gelbooru one" - the two batches
mix freely once they're both waiting.

Persistent seen-post tracking lives here (per preset, on disk). It is
handed to every source as skip_ids and checked BEFORE anything is
downloaded, so a re-scrape only fetches what's new (and a scan can walk
deeper into a listing instead of replaying its first N items). Each file
is registered the moment it lands (item_cb), which is also what lets
popup log lines name a file's source right away."""
import json
import os
import random
import threading
import time

from core import blacklist, media_caps, min_size, netlog, quality_map, site_slots, source_tag, video_tidy
from core.display_queue import DisplayQueue, DisplayWorker
from core.query_clean import clean_query
from core.thumbs import looks_like_error_page


# Edgeware's Alt+click sends a popup's file here (edgeware_core/data/blacklist/<pack name>/).
BLACKLIST_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "edgeware_core", "data", "blacklist")

MAX_DOWNLOAD_MB = 300     # a single file bigger than this is skipped
PMVHAVEN_DOWNLOAD_MB = 2048  # PMV Haven videos run long; the 300 MB cap dropped them


def download_cap_bytes(source_type):
    mb = PMVHAVEN_DOWNLOAD_MB if source_type == "pmvhaven" else MAX_DOWNLOAD_MB
    return mb * 1048576
AUDIO_SOURCE_TYPES = {"soundgasm"}  # long-form audio - a handful is plenty, unlike 20 images
MAX_AUDIO_DOWNLOAD_LIMIT = 5

# Reddit's RSS only supports a time window on Top/Controversial - Hot
# and New have no time filter at all, so "Hot this month" isn't a real
# option. Rotated randomly each cycle when the preset leaves sort
# unset, for variety between runs instead of always fetching "New".
REDDIT_RANDOM_SORTS = [("Top", "month"), ("Hot", ""), ("New", "")]

# Gelbooru/RealBooru/HypnoHub share one codebase and its sort meta-tag
# convention (confirmed from real page source) - appended into the tag
# query itself, not a separate parameter. Tacked on automatically when
# the user's own query doesn't already specify one.
# Rule34 / Safebooru / TBIB / Xbooru are deliberately NOT in this set: nobody has confirmed they understand these
# sort tags, and a tag a site doesn't know could silently return zero results. skip_ids already lets each scrape
# reach further into their listings, so they don't need it.
BOORU_SOURCE_TYPES = {"gelbooru", "realbooru", "hypnohub"}
# Lower starts first. On a fresh run the startup splash waits for the first picture, and the quick image
# sites should get there before Reddit (paced) and the video-heavy sites.
SLOW_FIRST_RANK = {"reddit": 3, "redgifs": 3, "erome": 3, "hypnotube": 3, "pmvhaven": 3, "soundgasm": 4, "freesound": 4}
BOORU_SORT_TAGS = ["sort:score", "sort:updated", "sort:random"]


class _NullLog:
    def __call__(self, msg, level="info"):
        pass


class _NullProgress:
    def __call__(self, current, total, prefix=""):
        pass


def _write_json_atomic(path, obj):
    """Write-then-rename so a reader (the popup engine reads the source
    manifest constantly) never sees a half-written file. On Windows the
    rename can briefly fail if a reader has the file open - retry."""
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f)
    for attempt in range(6):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.05)
    os.replace(tmp, path)


class PresetWorker(threading.Thread):
    def __init__(self, preset, source_registry, media_root, display_queue, on_new_media=None,
                 on_log=None, source_kwargs=None, run_once=False, blacklist_dir=None, caps=None, min_image_px=0, video_rules=None):
        super().__init__(daemon=True)
        self.preset = preset
        self.source_registry = source_registry
        self.media_root = media_root
        self.display_queue = display_queue
        self.on_new_media = on_new_media  # notification only now - display_queue handles showing
        self.on_log = on_log or _NullLog()
        self.source_kwargs = source_kwargs or {}  # e.g. {"gelbooru": {"api_key":.., "user_id":..}}
        self._blocked_by_site = {}    # site -> kinds it has filled up this pass
        self.video_rules = video_rules or {}      # core/video_tidy.py; {} = leave videos as downloaded
        self.min_image_px = min_image_px or 0     # core/min_size.py; 0 = keep every picture
        self.caps = caps or {}        # per-preset download caps (core/media_caps.py); {} = none
        self.run_once = run_once  # do one pass over all sources then stop, instead of looping forever
        self.blacklist_dir = BLACKLIST_DIR if blacklist_dir is None else blacklist_dir
        self._blocked = set()        # file names in the blacklist folder, refreshed every cycle
        self.stop_event = threading.Event()
        self.seen_path = os.path.join(media_root, preset.name, ".seen_post_ids.json")
        self._seen_lock = threading.Lock()

    def _load_seen(self):
        if os.path.exists(self.seen_path):
            try:
                with open(self.seen_path, "r", encoding="utf-8") as f:
                    return set(json.load(f))
            except Exception:
                return set()
        return set()

    def _save_seen(self, seen):
        try:
            _write_json_atomic(self.seen_path, sorted(seen))
        except Exception as ex:
            self.on_log(f"[{self.preset.name}] failed to save seen-cache: {ex}", "warning")

    def _refresh_blacklist(self, seen):
        """Blacklisted files never come back: their post ids join the seen list (skipped before any download)."""
        self._blocked = blacklist.names(self.blacklist_dir)
        if not self._blocked:
            return
        ids = blacklist.post_ids(self.media_root, self._blocked)
        with self._seen_lock:
            new = ids - seen
            seen.update(ids)
        if new:
            self.on_log(f"[{self.preset.name}] {len(new)} blacklisted post(s) will not be downloaded again")

    def stop(self):
        self.stop_event.set()

    def _fetch_one_source(self, source_entry, dest_dir, item_cb=None, skip_ids=None):
        source_type = source_entry.get("source_type")
        query = clean_query(source_type, source_entry.get("query", ""))
        limit = source_entry.get("limit") or self.preset.limit
        sort = self.preset.sort
        time_range = self.preset.time_range
        randomize = self.preset.randomize

        if source_type in AUDIO_SOURCE_TYPES:
            limit = min(limit, MAX_AUDIO_DOWNLOAD_LIMIT)
            randomize = True  # always shuffle which files get picked, not just the most recent uploads

        source_cls = self.source_registry.get(source_type)

        # Quality (Any / Good / Best), set per source row. The shared sources know what it means for each
        # site: a Top sort on Reddit/Redgifs, a minimum score tag on the booru sites. Any keeps the
        # random mix below, so nothing changes unless you pick Good or Best.
        chosen = {}
        if source_entry.get("quality") in ("Good", "Best") and quality_map.supported(source_type) and source_cls:
            chosen = quality_map.resolve(source_cls, source_entry["quality"]) or {}
        if chosen:
            sort = chosen.get("sort", sort)
            time_range = chosen.get("time_range", time_range)
            for token in chosen.get("query_suffix", "").split():     # add each part unless you typed that kind already
                if ":" not in token or (token.split(":")[0] + ":") not in query.lower():
                    query = f"{query} {token}".strip()
        else:
            if source_type == "reddit" and not sort:
                sort, time_range = random.choice(REDDIT_RANDOM_SORTS)

            if source_type in BOORU_SOURCE_TYPES and "sort:" not in query.lower():
                query = f"{query} {random.choice(BOORU_SORT_TAGS)}".strip()
        if source_cls is None:
            self.on_log(f"[{self.preset.name}] unknown source_type '{source_type}', skipped", "error")
            return []
        blocked = set()
        if self.caps:
            blocked = media_caps.blocked_kinds(media_caps.count_for_folder(dest_dir), self.caps)
            kinds = media_caps.site_kinds(getattr(source_cls, "category", ""))
            skip, wanted = media_caps.plan(blocked, kinds)
            if skip:
                self.on_log(f"[{self.preset.name}] {source_type}: reached its download cap "
                            f"({', '.join(sorted(blocked))}) - nothing more from it")
                return []
            if wanted:
                self.on_log(f"[{self.preset.name}] {source_type}: cap reached for {', '.join(sorted(blocked))}; "
                            f"only {', '.join(sorted(wanted))} from now on")
        self._blocked_by_site[source_type] = blocked
        try:
            source = source_cls(**self.source_kwargs.get(source_type, {}))
            if blocked and getattr(source_cls, "category", "") != "Audio":
                source.wanted_types = {"image", "video"} - blocked
            return source.fetch(
                query=query,
                limit=limit,
                sort=sort,
                time_range=time_range,
                dest_dir=dest_dir,
                log=self.on_log,
                progress=_NullProgress(),
                stop_event=self.stop_event,
                randomize=randomize,
                prioritize_images=self.preset.prioritize_images,
                item_cb=item_cb,
                skip_ids=skip_ids,
            )
        except Exception as ex:
            self.on_log(f"[{self.preset.name}] {source_type} ({query}) failed: {ex}", "error")
            return []

    def _write_manifest_entries(self, dest_dir, source_type, items):
        """Records which source each downloaded file came from, so
        LivePack can log that at popup-display time too (not just
        download time) - lets a "what got shown, from where" log line
        cover files popped much later than when they were fetched."""
        manifest_path = os.path.join(dest_dir, ".source_manifest.json")
        with self._seen_lock:
            manifest = {}
            if os.path.exists(manifest_path):
                try:
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        manifest = json.load(f)
                except Exception:
                    manifest = {}
            for item in items:
                manifest[os.path.basename(item.file_path)] = source_type
            try:
                _write_json_atomic(manifest_path, manifest)
            except Exception as ex:
                self.on_log(f"[{self.preset.name}] failed to save source manifest: {ex}", "warning")

    def _log_http_problems(self, source_type, calls):
        """One line per failed or retried request (status, redacted URL, ms, and the start of the
        site's reply) - what makes a silent "0 results" diagnosable from the log alone."""
        problems = [c for c in calls if c.get("error") or c.get("retry") or (c.get("status") or 0) >= 400]
        for c in problems[:8]:
            line = f"[{self.preset.name}] {source_type} http {c.get('status') or 'ERR'}: {c['url']} ({c['ms']} ms)"
            if c.get("retry"):
                line += f" [succeeded/failed after {c['retry']} retr{'y' if c['retry'] == 1 else 'ies'}]"
            if c.get("error"):
                line += f" {c['error']}"
            if c.get("body"):
                line += f" - reply: {c['body'][:120]!r}"
            self.on_log(line, "warning")
        if len(problems) > 8:
            self.on_log(f"[{self.preset.name}] {source_type}: ...and {len(problems) - 8} more failed requests", "warning")

    def _run_one_source_and_publish(self, source_entry, dest_dir, seen, got_anything):
        """Runs on its own thread, one per source in the cycle, so a
        slow source (Reddit, typically) doesn't hold up faster ones.

        `seen` is passed to the source as skip_ids: posts already
        collected are skipped BEFORE any download. Each file that lands
        is registered immediately (item_cb) - its post id joins `seen`
        and its source goes into the manifest - so a popup can name the
        source of a file that landed seconds ago, even though this
        source's fetch() is still running."""
        source_type = source_entry.get("source_type")
        registered, rejected = [], []

        def register(item):
            if looks_like_error_page(item.file_path):
                # A site answered HTTP 200 with an error page instead of a file. Delete it and do NOT
                # record the post as collected, so a later cycle can try it again.
                try:
                    os.remove(item.file_path)
                except OSError:
                    pass
                rejected.append(item)
                self.on_log(f"[{self.preset.name}] {source_type}: discarded a download that was an "
                            f"error page, not a real file ({os.path.basename(item.file_path)})", "warning")
                return
            if item.media_type in self._blocked_by_site.get(source_type, ()):
                try:                                 # a site that ignores the type filter: the cap still holds
                    os.remove(item.file_path)
                except OSError:
                    pass
                rejected.append(item)
                return
            if item.media_type == "image" and min_size.image_too_small(item.file_path, self.min_image_px):
                tiny = os.path.basename(item.file_path)
                try:
                    os.remove(item.file_path)
                except OSError:
                    pass
                with self._seen_lock:                # do not fetch the same tiny picture again next pass
                    if item.post_id:
                        seen.add(item.post_id)
                rejected.append(item)
                self.on_log(f"[{self.preset.name}] {source_type}: dropped a picture under {self.min_image_px}px ({tiny})")
                return
            if item.media_type == "video" and self.video_rules:
                video_tidy.tidy(item.file_path, self.video_rules,
                                lambda m: self.on_log(f"[{self.preset.name}] {source_type}: {m.strip()}"))
            old_name = os.path.basename(item.file_path)
            item.file_path = source_tag.tag_file(item.file_path, source_type)   # cat.jpg -> reddit__cat.jpg
            name = os.path.basename(item.file_path)
            if name in self._blocked or old_name in self._blocked:
                # Same file as one you blacklisted (Alt+click): drop it, and remember the post so it is not tried again.
                try:
                    os.remove(item.file_path)
                except OSError:
                    pass
                with self._seen_lock:
                    if item.post_id:
                        seen.add(item.post_id)
                rejected.append(item)
                self.on_log(f"[{self.preset.name}] {source_type}: skipped a blacklisted file ({name})")
                return
            with self._seen_lock:
                if item.post_id:
                    seen.add(item.post_id)
                try:
                    blacklist.record(dest_dir, name, item.post_id)
                except Exception:
                    pass
            self._write_manifest_entries(dest_dir, source_type, [item])
            registered.append(item)

        http_calls = []
        waited = lambda: self.on_log(f"[{self.preset.name}] {source_type}: another {source_type} fetch is running - "
                                     f"waiting for it to finish (other sites keep going)")
        with site_slots.slot(source_type, self.stop_event, on_wait=waited) as got_slot:
            if not got_slot:
                return                           # stopped while waiting
            netlog.begin(http_calls)             # per-thread: records this fetch's HTTP calls
            # Stop/Panic ends a download within about a second; a file over the size limit is skipped, not held in memory
            netlog.set_control(netlog.DownloadControl(self.stop_event, threading.Event(), download_cap_bytes(source_type)))
            try:
                items = self._fetch_one_source(source_entry, dest_dir, item_cb=register, skip_ids=seen)
            finally:
                netlog.clear_control()
                netlog.end()
        self._log_http_problems(source_type, http_calls)
        for item in items:                       # belt and braces: a source that returned an
            if item not in registered and item not in rejected:   # item without calling item_cb
                register(item)                   # still gets recorded
        with self._seen_lock:
            self._save_seen(seen)

        if registered:
            got_anything["flag"] = True
            self.on_log(f"[{self.preset.name}] {len(registered)} new item(s) from {source_type}"
                        f" - queued for random display")
            self.display_queue.add_many(self.preset, registered)
            if self.on_new_media:
                self.on_new_media(self.preset, registered)

    def run(self):
        dest_dir = self.preset.media_dir(self.media_root)
        seen = self._load_seen()

        while not self.stop_event.is_set():
            self._refresh_blacklist(seen)
            order = list(self.preset.sources)
            random.shuffle(order)
            order.sort(key=lambda entry: SLOW_FIRST_RANK.get(entry.get("source_type"), 1))   # stable: fast image sites start first
            self.on_log(f"[{self.preset.name}] scrape cycle starting "
                        f"({len(order)} source(s) in parallel, order: {', '.join(s.get('source_type', '?') for s in order)})")
            got_anything = {"flag": False}

            threads = [
                threading.Thread(target=self._run_one_source_and_publish,
                                  args=(source_entry, dest_dir, seen, got_anything), daemon=True)
                for source_entry in order
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            if not got_anything["flag"]:
                self.on_log(f"[{self.preset.name}] no new items this cycle")

            if self.run_once:
                self.on_log(f"[{self.preset.name}] pass complete (auto-stop mode) - not looping again")
                return

            waited = 0
            while waited < self.preset.interval_seconds and not self.stop_event.is_set():
                time.sleep(min(1, self.preset.interval_seconds - waited))
                waited += 1


class ScrapeScheduler:
    """Owns one PresetWorker per enabled preset, plus the single shared
    DisplayWorker that pops from all of their combined output."""

    def __init__(self, media_root, on_new_media=None, on_log=None, on_display=None,
                 display_interval_seconds=5, caps=None, min_image_px=0, video_rules=None):
        self.caps = caps
        self.min_image_px = min_image_px
        self.video_rules = video_rules
        self.media_root = media_root
        self.on_new_media = on_new_media
        self.on_log = on_log
        self.on_display = on_display
        self.display_interval_seconds = display_interval_seconds
        self.display_queue = DisplayQueue()
        self.workers = {}
        self.display_worker = None

    def start(self, presets, source_registry, source_kwargs=None, run_once=False, on_finished=None):
        netlog.install()   # idempotent: global retry of transient errors + request logging
        if self.on_log:
            from sources import SOURCES_VERSION
            self.on_log(f"Scrapers: shared set {SOURCES_VERSION} (see sources/CHANGELOG.md)")
        for preset in presets:
            if not preset.enabled:
                continue
            worker = PresetWorker(preset, source_registry, self.media_root, self.display_queue,
                                   on_new_media=self.on_new_media, on_log=self.on_log,
                                   source_kwargs=source_kwargs, run_once=run_once, caps=self.caps, min_image_px=self.min_image_px,
                                   video_rules=self.video_rules)
            self.workers[preset.name] = worker
            worker.start()

        if self.on_display and self.workers:
            self.display_worker = DisplayWorker(self.display_queue, self.on_display,
                                                 interval_seconds=self.display_interval_seconds,
                                                 on_log=self.on_log)
            self.display_worker.start()

        if run_once and self.workers:
            monitor = threading.Thread(target=self._wait_then_autostop, args=(on_finished,), daemon=True)
            monitor.start()

    def _wait_then_autostop(self, on_finished):
        for worker in list(self.workers.values()):
            worker.join()
        if self.on_log:
            self.on_log("All presets finished their pass - draining display queue before auto-stopping.")
        # Give the DisplayWorker a chance to pop whatever's left rather
        # than stopping mid-queue; capped so a stuck display callback
        # can't hang this forever.
        waited = 0
        while len(self.display_queue) > 0 and waited < 300:
            time.sleep(1)
            waited += 1
        self.stop_all()
        if on_finished:
            on_finished()

    def stop_all(self):
        for worker in self.workers.values():
            worker.stop()
        for worker in self.workers.values():
            worker.join(timeout=5)
        self.workers.clear()
        if self.display_worker:
            self.display_worker.stop()
            self.display_worker.join(timeout=5)
            self.display_worker = None
