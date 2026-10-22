"""LivePack: makes Edgeware's real, vendored, unmodified feature code
(under edgeware_core/) read straight from Autoedgeware's own
media/<preset>/ folders instead of a static compiled pack.

Import this only after edgeware_core/src is on sys.path (see
run_engine.py) - it imports directly from Edgeware's own `pack`
package.
"""
import json
import re
import time
from collections import deque
from pathlib import Path

from pack import Pack
from pack.data import Discord, Index, Info, MoodSet
from paths import CustomAssets

from core import file_log
from core.video_bag import bag_eligible, watchlist_size

BASE_DIR = Path(__file__).resolve().parent
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
VIDEO_EXTS = {".mp4", ".webm", ".mov", ".mkv"}
AUDIO_EXTS = {".m4a", ".mp3", ".wav", ".ogg", ".flac"}

_HASH_SUFFIX = re.compile(r"_[0-9a-f]{8}$")


class LivePack(Pack):
    """Deliberately does NOT call Pack.__init__ - there's no real pack
    directory to read from. Every attribute a static Pack normally
    loads from disk is set to a safe empty default instead; the three
    random_* methods re-scan the live media folders on every call
    (via Pack's own random_media(), reused as-is for its "don't repeat
    the same one back to back" weighting) so newly-downloaded files -
    and anything left over from a previous session, since this just
    scans whatever's sitting in the folder - both show up
    automatically, no reload needed.

    Mood/caption/corruption/subliminal/prompt data is intentionally
    empty (our scraped media has none of that): filter_media() passes
    everything through unfiltered (an empty index.media_moods means
    every file matches the default/no-mood bucket), and anything that
    depends on captions or moods (subliminals, prompts, notification
    text) will simply have nothing to say. Only image/video/audio
    popups have real content to show for now.
    """

    def __init__(self, media_roots, state=None, settings=None):
        self.media_roots = [Path(p) for p in media_roots]
        # Peeked before doing anything in random_audio() - audio.py
        # calls pack.random_audio() unconditionally, THEN checks
        # len(state.audio_players) >= settings.max_audio and bails if
        # it's already full, meaning that pick never actually plays.
        # Without checking this ourselves first, we'd log "shown" and
        # burn a recent-history slot on a pick nobody ever saw.
        self._state = state
        self._empty_logged = {}
        self._settings = settings

        self.image_ranks = {}
        self.video_ranks = {}
        self.audio_ranks = {}
        # Pure sliding window: once a file's been shown, it's excluded
        # until 20 OTHER shows (of the same type) have happened since -
        # not a fixed rotation that resets. A small pool that hasn't
        # grown to 20 unique yet will mostly skip rather than repeat
        # early, since the background scraper is expected to keep
        # adding genuinely new files over time; if it doesn't, missing
        # a popup beats forcing a duplicate. No fallback tier - once
        # every currently-available file is inside the window, that
        # type stays silent until either the window naturally advances
        # (enough shows to evict someone) or a new file appears.
        self._recent = {"image": deque(maxlen=20), "video": deque(maxlen=20), "audio": deque(maxlen=20)}
        # Videos also use a shuffle bag: every video plays once before any repeats (core/video_bag.py).
        self._played_videos = set()

        self.corruption_levels = []
        self.discord = Discord()
        self.index = Index()
        self.info = Info()
        self.config = {}

        self.allowed_moods = MoodSet()
        self.active_moods = MoodSet()
        self.get_active_moods = lambda: self.active_moods

        self.images = []
        self.videos = []
        self.audio = []
        self.hypnos = [CustomAssets.hypno()]

        self.icon = CustomAssets.icon()
        self.wallpaper = None
        self.startup_splash = CustomAssets.startup_splash()

    def _source_for(self, media_path):
        """Looks up which source (reddit/gelbooru/etc) downloaded this
        file, from the manifest core/scheduler.py writes alongside each
        preset's media folder. Re-read fresh each call (small JSON
        file, cheap) rather than cached, so it always reflects the
        latest downloads without needing an explicit reload hook."""
        manifest_path = media_path.parent / ".source_manifest.json"
        if not manifest_path.is_file():
            return "unknown"
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            return manifest.get(media_path.name, "unknown")
        except Exception:
            return "unknown"

    def _log_shown(self, kind, media_path, total, eligible):
        source = self._source_for(media_path)
        file_log.write(BASE_DIR, f"POPUP: {kind} shown: {media_path.name} "
                                  f"(source: {source}, preset folder: {media_path.parent.name}, "
                                  f"pool: {total} total / {eligible} eligible)", "info")

    def _log_empty(self, kind):
        """A popup was asked for but nothing of that kind is downloaded yet. Before, this was silent,
        so a new preset's log showed no attempts at all. Throttled to once a minute per kind."""
        now = time.monotonic()
        if now - self._empty_logged.get(kind, -1e9) >= 60:
            self._empty_logged[kind] = now
            file_log.write(BASE_DIR, f"POPUP: an {kind} was wanted but none are downloaded yet "
                                      f"(pool: 0) - waiting for the scraper", "info")

    def _log_skipped(self, kind, total):
        file_log.write(BASE_DIR, f"POPUP: {kind} SKIPPED - no eligible candidates "
                                  f"(pool: {total} total, all within the recent-shown watchlist)", "info")

    def _scan(self, extensions):
        found = []
        for root in self.media_roots:
            if not root.is_dir():
                continue
            for path in root.iterdir():
                if path.is_file() and path.suffix.lower() in extensions:
                    found.append(path)
        return found

    def _scan_excluding_recent(self, extensions, kind):
        """No fallback tier - excludes everything in this type's
        20-item sliding window, full stop. If that empties the pool,
        returns empty (the caller's random_media() correctly returns
        None), rather than relaxing to allow an early repeat. Returns
        (total_pool_size, eligible_list) so callers can log both -
        total tells you whether there's genuinely enough content
        downloaded; eligible tells you whether the anti-repeat window
        is what's holding a popup back right now."""
        found = self._scan(extensions)
        size = watchlist_size(len(found))          # 50 once the pool passes 100, else 20
        if self._recent[kind].maxlen != size:
            self._recent[kind] = deque(self._recent[kind], maxlen=size)
        if kind == "video":
            eligible, self._played_videos = bag_eligible(found, self._recent[kind], self._played_videos)
        else:
            eligible = [f for f in found if f not in self._recent[kind]]
        return len(found), eligible

    def has_eligible(self, kind):
        """True when a popup of this kind could be shown right now (does not pick or record anything)."""
        exts = {"image": IMAGE_EXTS, "video": VIDEO_EXTS, "audio": AUDIO_EXTS}[kind]
        return bool(self._scan_excluding_recent(exts, kind)[1])

    def random_image(self, unweighted=False):
        total, eligible = self._scan_excluding_recent(IMAGE_EXTS, "image")
        self.images = eligible
        picked = super().random_image(unweighted=unweighted)
        if picked is not None:
            self._recent["image"].append(picked)
            self._log_shown("image", picked, total, len(eligible))
        elif total:
            self._log_skipped("image", total)
        else:
            self._log_empty("image")
        return picked

    def random_video(self):
        total, eligible = self._scan_excluding_recent(VIDEO_EXTS, "video")
        self.videos = eligible
        picked = super().random_video()
        if picked is not None:
            self._recent["video"].append(picked)
            self._played_videos.add(picked)
            self._log_shown("video", picked, total, len(eligible))
        elif total:
            self._log_skipped("video", total)
        else:
            self._log_empty("video")
        return picked

    def random_audio(self):
        if self._state is not None and self._settings is not None:
            if len(self._state.audio_players) >= self._settings.max_audio:
                return None  # would bail in audio.py anyway - skip before it ever counts as "shown"
        total, eligible = self._scan_excluding_recent(AUDIO_EXTS, "audio")
        self.audio = eligible
        picked = super().random_audio()
        if picked is not None:
            self._recent["audio"].append(picked)
            self._log_shown("audio", picked, total, len(eligible))
        elif total:
            self._log_skipped("audio", total)
        else:
            self._log_empty("audio")
        return picked

    def random_caption(self, media=None):
        """Overridden entirely (not calling super()) - derives a rough
        caption from the filename instead, since we have no mood-based
        caption data. Strips the trailing _<8-hex-hash> our own
        downloaders append."""
        if not media:
            return None
        stem = _HASH_SUFFIX.sub("", Path(media).stem)
        caption = stem.replace("_", " ").strip()
        return caption[:200] or None
