"""Autoedgeware's own global settings: hibernate toggle and its timing
sub-options, startup delay, and whichever intensity-preset bundle was
last applied (mirrors a slice of Edgeware's own config.json, for popup
behavior)."""
import json
import os

DEFAULTS = {
    "hibernate": False,
    # Our own run/sleep cycle (independent of Edgeware's built-in
    # hibernate_mode, which cycles burst patterns immediately rather
    # than "run normally, then go quiet, then resume"): minutes.
    "hibernate_run_min_minutes": 20,
    "hibernate_run_max_minutes": 40,
    "hibernate_sleep_min_minutes": 5,
    "hibernate_sleep_max_minutes": 15,
    "startup_delay_seconds": 0,
    "auto_stop_after_pass": True,  # pre-popup testing convenience: stop once every preset finishes one pass
    "popup_timeout_enabled": False,  # auto-close popups after a set time - real Edgeware setting, just exposed here
    "popup_timeout_seconds": 10,
    "edgeware_cfg": {},   # last-applied intensity preset's key/value bundle
    "gelbooru_api_key": "",
    "gelbooru_user_id": "",
    "hypno_mode": False,          # faint spiral + binaural beats, strength follows the image popup speed
    "freesound_api_key": "",
    "first_run_done": False,
    "disabled_monitors": [],            # monitor names the popups skip; empty = all monitors
    "skip_certificate_checks": False,   # opt-in: off by default
    "check_for_updates": True,
    "rule34_api_key": "",
    "rule34_user_id": "",
    "wallhaven_api_key": "",      # more API keys: add a line to core/api_keys.py and one here
    "wallpaper_changer_on": True,   # swap the desktop wallpaper for wide images from the preset while running
    "wallpaper_minutes": 2,       # at most one change per this many minutes
    "fullscreen_video_chance": 15,    # % of wide videos that fill a whole monitor
    "fullscreen_video_volume_pct": 70,   # fullscreen videos play at this % of the normal video volume
    "fullscreen_video_click_close": True,             # False: a fullscreen video cannot be closed by clicking; it plays to the end
    "fullscreen_video_min_height": 1080,   # only videos taller than this go fullscreen (so 1080p or less stays a popup)
    "audio_volume": 50,   # standalone audio popups, 0-100
    "video_volume": 20,   # a video's own sound, 0-100
    "max_audio": 1,   # audio tracks playing at once
    "hero_mode": False,
    "hero_text": True,             # show the instruction line ("Stroke.", "Hold." ...)
    "hero_click_volume": 40,       # 0-100
    "hero_round_seconds": 120,     # "speed up every" X seconds = the length of one whole round
    "hero_rounds_to_full": 8,      # rounds the tempo takes to climb to the top of its range
    "hero_frenzy_percent": 50,     # chance that a round includes a Frenzy
    "hero_hold_seconds": 10,       # how long a Hold lasts
    "hero_bpm_min": 50,
    "hero_bpm_max": 140,
    "hypno_beat_volume": 20,   # binaural beats volume, 0-100
    "fullscreen_video_max_seconds": 600,   # a fullscreen video plays to its end, but never longer than this
    "max_images_per_preset": 500,   # a preset stops downloading images once its folder holds this many (0 = no limit)
    "max_videos_per_preset": 500,
    "max_audio_per_preset": 50,
    "video_max_seconds": 120,      # new videos longer than this are cut to it (0 = off)
    "video_shrink_to_px": 720,     # popup-only videos taller than this are shrunk to it (0 = off)
    "min_image_px": 300,           # pictures with a shorter side under this are dropped (0 = keep all)
    "last_preset": "",            # picked again next launch
    "custom_cfg": {},             # the Custom intensity's own values
    "corruption_speedup_percent": 20,   # how much each timed speed-up shortens the popup delay
}


def load_settings(path):
    if not os.path.exists(path):
        return dict(DEFAULTS)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(DEFAULTS)
        merged.update(data)
        return merged
    except Exception:
        return dict(DEFAULTS)


def save_settings(path, settings):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
