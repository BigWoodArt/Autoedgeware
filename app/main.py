"""Autoedgeware entrypoint. For now: loads presets.json, runs the
background scraper loop, and logs new media to the console. Display
hookup (popping media to Edgeware's screen) comes once the scraper
side is proven out."""
import os
import sys
import time

from ae_settings.preset import Preset, load_presets, save_presets
from ae_settings.settings import load_settings
from core.api_keys import build_source_kwargs
from core.scheduler import ScrapeScheduler
from core.display import pop_media
from core.source_registry import SOURCE_REGISTRY
from core import file_log

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PRESETS_PATH = os.path.join(BASE_DIR, "ae_settings", "presets.json")
SETTINGS_PATH = os.path.join(BASE_DIR, "ae_settings", "settings.json")
MEDIA_ROOT = os.path.join(os.path.dirname(BASE_DIR), "media")   # next to run.bat


def log(msg, level="info"):
    print(f"[{level.upper()}] {msg}")
    file_log.write(BASE_DIR, msg, level)


def on_new_media(preset, items):
    # Logging/notification only - the DisplayWorker (wired in main())
    # is what actually pops items, on its own random-pick timer.
    for item in items:
        print(f"  -> {preset.name} [{item.source_type}]: {os.path.basename(item.file_path)}  ({item.caption[:60]})")


def ensure_default_presets():
    """Presets saved so far. On a first run (no file) the app starts with the safe 'Nature' preset,
    so a new user can press Run right away. It is saved with the next Save/Run."""
    if os.path.exists(PRESETS_PATH):
        return load_presets(PRESETS_PATH)
    from ae_settings.preset import Preset
    from ae_settings.wizard_logic import nature_sources
    return [Preset(name="Nature", sources=nature_sources(), interval_seconds=300, limit=30)]


def main():
    presets = ensure_default_presets()
    if not presets:
        log("No presets yet. Open the Autoedgeware window (gui_main.py) and make one first.", "error")
        return 1
    settings = load_settings(SETTINGS_PATH)
    source_kwargs = build_source_kwargs(settings)

    run_once = settings.get("auto_stop_after_pass", True)
    scheduler = ScrapeScheduler(MEDIA_ROOT, on_new_media=on_new_media, on_log=log,
                                on_display=pop_media, display_interval_seconds=5)
    finished = {"flag": False}

    def on_finished():
        finished["flag"] = True

    scheduler.start(presets, SOURCE_REGISTRY, source_kwargs=source_kwargs,
                     run_once=run_once, on_finished=on_finished)
    log(f"Running {len(scheduler.workers)} preset worker(s)."
        + (" Will auto-stop after one pass." if run_once else " Ctrl+C to stop."))
    try:
        while not finished["flag"]:
            time.sleep(1)
        log("Finished - all presets completed one pass and auto-stopped.")
    except KeyboardInterrupt:
        log("Stopping...")
        scheduler.stop_all()


if __name__ == "__main__":
    sys.exit(main())
