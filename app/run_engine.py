"""Launches the full, real Autoedgeware experience in one process:

  - Real Edgeware feature code (vendored, unmodified, under
    edgeware_core/) does the actual popping - images, video, audio,
    tray icon, hibernate, startup splash - timed by whichever
    intensity preset was applied (same delay/popupMod/vidMod/audioMod/
    etc. fields the GUI's Options already writes).
  - A LivePack (live_pack.py) feeds it media straight from
    Autoedgeware's own media/<preset>/ folders instead of a static
    compiled pack, so freshly-downloaded files AND anything left over
    from a previous session both show up, no reload needed.
  - The background scraper (core/scheduler.py) keeps running
    continuously alongside it (NOT the auto-stop-after-one-pass mode
    the GUI's own quick "Run" preview uses - that setting was
    explicitly for testing before real popups existed), refilling
    those same folders every preset's own interval.

This replaces config.pyw entirely - Edgeware's own settings come from
edgeware_core/data/config.json, written here from Autoedgeware's own
settings.json (the same intensity bundle the GUI already manages).
"""
# Edgeware expects to run DPI-unaware (its own launchers do this). Must happen
# before any Tk window exists, or 4K/scaled screens misplace video popups.
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(0)
except Exception:
    pass

import atexit
import json
import os
import random
import sys
from pathlib import Path
from tkinter import Tk

BASE_DIR = Path(__file__).resolve().parent
ENGINE_ROOT = BASE_DIR / "edgeware_core"
ENGINE_SRC = ENGINE_ROOT / "src"
ENGINE_DATA = ENGINE_ROOT / "data"
MEDIA_ROOT = BASE_DIR.parent / "media"   # next to run.bat
PRESETS_PATH = BASE_DIR / "ae_settings" / "presets.json"
SETTINGS_PATH = BASE_DIR / "ae_settings" / "settings.json"

# Autoedgeware's own packages first. This works regardless of import
# order since ae_settings was specifically renamed away from "config"
# to avoid colliding with the vendored Edgeware source's own "config"
# package once edgeware_core/src goes on sys.path below.
from ae_settings.preset import load_presets
from ae_settings.settings import load_settings
from core.scheduler import ScrapeScheduler
from core.source_registry import SOURCE_REGISTRY
from core import engine_control, file_log, media_caps, min_size, quiet_children, video_tidy
from core import ssl_fix
ssl_fix.install_from_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ae_settings", "settings.json"))
from core.api_keys import build_source_kwargs
from core.panic_users import PANIC_USERS
from core.wallpaper_changer import WallpaperChanger
from core.popup_fallback import make_popup_chooser
from core.preset_pick import pick_preset
from core.splash_pick import choose_splash
from core.engine_overrides import apply_forced, effective_cfg
from gui.theme import INTENSITY_PRESETS

sys.path.insert(0, str(ENGINE_SRC))
if str(ENGINE_DATA) not in os.environ.get("PATH", ""):
    os.environ["PATH"] += os.pathsep + str(ENGINE_DATA)
try:
    os.add_dll_directory(str(ENGINE_DATA))
except (AttributeError, OSError):
    pass

import utils  # Edgeware's own logging init
import features.misc as _misc_module
from config import load_config as load_engine_config
from config.settings import Settings
from features.audio import play_audio
from features.corruption import handle_corruption
from features.drive import fill_drive, replace_images
from features.hibernate import main_hibernate, start_main_hibernate
from features.image_popup import ImagePopup
from features.misc import (
    handle_discord,
    handle_keyboard,
    handle_mitosis_mode,
    handle_panic_lockout,
    handle_wallpaper,
    make_desktop_icons,
    make_tray_icon,
    open_web,
    send_notification,
)
from features.prompt import Prompt
from features.startup_splash import StartupSplash
from features.subliminal_popup import SubliminalPopup
from features.video_popup import VideoPopup
import features.popup as _popup_module
import panic as _panic_module
import scripting.modules as _script_modules
from panic import ensure_panic_wallpaper, panic as _original_panic, start_panic_listener
from roll import RollTarget, roll_targets
from scripting import run_script
from state import State
from threading import Thread

from live_pack import LivePack
import ae_video_popup
from hero import HeroController
from hypno import HypnoController
from ae_video_popup import AEVideoPopup


def log(msg, level="info"):
    print(f"[SCRAPER {level.upper()}] {msg}")
    file_log.write(BASE_DIR, msg, level)


def _write_config_overrides():
    """Merge the currently-applied intensity bundle into the vendored
    copy's own data/config.json - same idea as core/edgeware_bridge.py's
    apply_config, just pointed at ourselves instead of an external
    install."""
    settings = load_settings(str(SETTINGS_PATH))
    cfg = effective_cfg(settings, INTENSITY_PRESETS)
    ENGINE_DATA.mkdir(parents=True, exist_ok=True)
    config_path = ENGINE_DATA / "config.json"
    current = {}
    if config_path.is_file():
        try:
            current = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            current = {}
    current.update(cfg)
    apply_forced(current, settings)   # see core/engine_overrides.py
    config_path.write_text(json.dumps(current, indent=2), encoding="utf-8")


def _start_scraper(presets):
    """Continuous background scraping (NOT auto-stop mode) alongside
    the popup engine - refills the same folders LivePack reads from."""
    settings = load_settings(str(SETTINGS_PATH))
    source_kwargs = build_source_kwargs(settings)

    scheduler = ScrapeScheduler(str(MEDIA_ROOT), on_new_media=None, on_log=log,
                                on_display=None, caps=media_caps.caps_from_settings(settings),
                                min_image_px=min_size.from_settings(settings),
                                video_rules=video_tidy.rules_from_settings(settings))  # real popups come from LivePack now, not our own display queue
    scheduler.start(presets, SOURCE_REGISTRY, source_kwargs=source_kwargs, run_once=False)
    return scheduler


# Every module that did `from panic import panic` holds its OWN copy of the function, so patching one
# place is not enough: a popup's panic key (features.popup), the tray menu and global hotkey
# (features.misc), the script commands (scripting.modules) and Edgeware's own listener (panic) each
# call their own. tests/test_panic_patch.py checks this list against the source.


def _panic_modules():
    assert set(PANIC_USERS) == {"panic", "features.misc", "features.popup", "scripting.modules"}
    return {"panic": _panic_module, "features.misc": _misc_module,
            "features.popup": _popup_module, "scripting.modules": _script_modules}


def panic(root, settings, state, condition=True, disable=True):
    """Wraps Edgeware's real panic() to also stop every playing audio
    track first - the real one only closes state.popups (the visual
    Tkinter windows), never touches state.audio_players at all, so
    playing audio otherwise just kept going after a panic. Patched
    into features.misc's own namespace too (see build_and_start) so
    the tray icon's Panic button gets this fix as well, not just our
    own Stop button's call into this module."""
    for player in list(state.audio_players):
        try:
            player.pause()
        except Exception:
            pass
    state.audio_players.clear()
    changer = getattr(state, "ae_wallpaper", None)
    if changer is not None and condition:
        changer.stop()
    if condition:
        engine_control.set_tray_visible(state, False)    # gone before the process ends: no ghost icon
        engine_control.stop_hypno(state, final=True)
        engine_control.stop_hero(state, final=True)
    _original_panic(root, settings, state, condition=condition, disable=disable)


def _start_with_splash(root, settings, pack, media_roots, start_main):
    """Splash = a random picture from this run's own folder. On a fresh run it waits up to 10 s for the
    first image to land, then falls back to the default splash."""
    default = pack.startup_splash

    def go(path, from_pool):
        pack.startup_splash = Path(path)
        file_log.write(BASE_DIR, f"splash: {'from the media pool' if from_pool else 'default (no image arrived in time)'}"
                       f" - {Path(path).name}", "info")
        StartupSplash(settings, pack, start_main)

    choose_splash(root, media_roots, default, go, timeout_ms=10000)


def build_and_start(root, presets, on_log=None, embedded=False, on_stop=None):
    """Sets up Settings/LivePack/State/tray/startup-splash and kicks
    off the real popup loop against the given Tk root. Does NOT call
    root.mainloop() itself, so it works either standalone (main(),
    below, builds its own hidden root) or attached to an
    already-running one - e.g. the GUI's own visible window, for its
    Run button (real popups during debugging, not just a stub print).
    Safe to call only once per root/process - starting the tray icon
    twice would spawn a second one."""
    quiet_children.install()   # no console-window flashes from ffprobe / the mpv helper (Windows)
    _write_config_overrides()
    utils.init_logging("autoedgeware_engine")

    media_roots = [MEDIA_ROOT / p.name for p in presets]   # the caller decides which presets run

    settings = Settings()
    ensure_panic_wallpaper()

    state = State()
    atexit.register(lambda: engine_control.stop_tray(state))    # whatever way the program ends
    atexit.register(lambda: engine_control.stop_hypno(state, final=True))
    atexit.register(lambda: engine_control.stop_hero(state, final=True))
    chosen_panic = engine_control.make_embedded_panic(on_stop) if embedded else panic
    for module in _panic_modules().values():
        module.panic = chosen_panic       # see PANIC_USERS above
    pack = LivePack(media_roots, state=state, settings=settings)

    settings.corruption_mode = settings.corruption_mode and bool(pack.corruption_levels)  # always False - LivePack has none

    # An image roll with no image eligible shows a video instead (and the reverse), so popups keep
    # flowing while downloads and chances disagree. See core/popup_fallback.py.
    image_roll, video_roll = make_popup_chooser(
        pack, state, settings,
        lambda: ImagePopup(root, settings, pack, state),
        lambda: AEVideoPopup(root, settings, pack, state),
        log=lambda msg: file_log.write(BASE_DIR, msg, "info"))

    targets = [
        RollTarget(image_roll, engine_control.gated(lambda: settings.image_chance if not settings.mitosis_mode else 0)),
        RollTarget(video_roll, engine_control.gated(lambda: settings.video_chance if not settings.mitosis_mode else 0)),
        RollTarget(lambda: SubliminalPopup(settings, pack), engine_control.gated(lambda: settings.subliminal_chance)),
        RollTarget(lambda: Prompt(settings, pack, state), engine_control.gated(lambda: settings.prompt_chance)),
        RollTarget(lambda: play_audio(root, settings, pack, state), engine_control.gated(lambda: settings.audio_chance)),
        RollTarget(lambda: open_web(pack), engine_control.gated(lambda: settings.web_chance)),
        RollTarget(lambda: send_notification(settings, pack), engine_control.gated(lambda: settings.notification_chance)),
    ]

    # --- Our own corruption escalation + hibernate run/sleep cycle ---
    # Edgeware's real corruption_mode is deliberately left off above
    # (LivePack has no mood-tier data for it to escalate through), and
    # its real hibernate_mode cycles burst patterns immediately rather
    # than "run normally, then go quiet, then resume" - so both of
    # those user-facing ideas are implemented natively here instead,
    # driven by the applied intensity preset's raw corruptionMode/
    # corruptionTime and Autoedgeware's own hibernate settings.
    ae_settings = load_settings(str(SETTINGS_PATH))
    raw_cfg = effective_cfg(ae_settings, INTENSITY_PRESETS)
    ae_video_popup.configure(ae_settings.get("fullscreen_video_chance", 15),
                             ae_settings.get("fullscreen_video_max_seconds", 600), BASE_DIR,
                             ae_settings.get("fullscreen_video_volume_pct", 70),
                             ae_settings.get("fullscreen_video_min_height", 1080),
                             click_close=ae_settings.get("fullscreen_video_click_close", True))
    import hypno as _hypno_mod
    _hypno_mod.configure(ae_settings.get("hypno_beat_volume", 20))

    # Wallpaper: wide images from this run's own folders, original restored on Stop / Panic / exit.
    changer = None
    if ae_settings.get("wallpaper_changer_on", True):
        from os_utils import get_wallpaper, set_wallpaper
        changer = WallpaperChanger(lambda: list(pack.media_roots), str(BASE_DIR / "ae_settings"),
                                   get_wallpaper, set_wallpaper,
                                   interval_s=max(1, int(ae_settings.get("wallpaper_minutes", 2))) * 60,
                                   log=lambda msg: file_log.write(BASE_DIR, msg, "info"))
        # Edgeware's own panic would set ITS saved wallpaper right after ours: use ours instead.
        _panic_module.restore_panic_wallpaper = changer.stop
    state.ae_wallpaper = changer

    # Hypno mode: always created (so the checkbox can switch it on while running); does nothing until enabled.
    hypno = HypnoController(root, settings, pack, state, BASE_DIR)
    state.ae_hypno = hypno
    hypno.set_enabled(ae_settings.get("hypno_mode", False))
    # Hero mode: a beat bar along the bottom; popups follow its rhythm. Reads its settings each time it starts.
    hero = HeroController(root, settings, pack, state, BASE_DIR, lambda: load_settings(str(SETTINGS_PATH)))
    state.ae_hero = hero
    hero.pace_source = lambda: (settings.delay, progression["corruption_interval"] / 1000.0,
                                ae_settings.get("corruption_speedup_percent", 20), bool(raw_cfg.get("corruptionMode")))
    hero.set_enabled(ae_settings.get("hero_mode", False))
    file_log.write(BASE_DIR, "wallpaper changer: " + ("on" if changer else "off (Settings > General)"), "info")
    base_delay = settings.delay
    base_corruption_interval = settings.corruption_time  # already ms (s_to_ms conversion)
    progression = {"corruption_interval": base_corruption_interval, "hibernating": False, "chances_backup": None}

    def escalate_corruption():
        if hero.active:                       # Hero mode sets the pace: wait, and keep the timer going
            root.after(progression["corruption_interval"], escalate_corruption)
            return
        if progression["hibernating"] or settings.delay <= 600:
            return  # paused during hibernation, or already at the floor - stop escalating
        factor = 1 - max(5, min(50, int(ae_settings.get("corruption_speedup_percent", 20)))) / 100
        settings.delay = max(600, round(settings.delay * factor))
        progression["corruption_interval"] = max(2000, round(progression["corruption_interval"] * factor))
        file_log.write(BASE_DIR, f"corruption: popup delay now {settings.delay}ms", "info")
        if settings.delay > 600:
            root.after(progression["corruption_interval"], escalate_corruption)

    def reset_corruption():
        settings.delay = base_delay
        progression["corruption_interval"] = base_corruption_interval
        if raw_cfg.get("corruptionMode"):
            root.after(progression["corruption_interval"], escalate_corruption)

    def enter_hibernate():
        if hero.active:                       # no hibernating while Hero mode runs; try again later
            schedule_next_hibernate()
            return
        progression["hibernating"] = True
        progression["chances_backup"] = (settings.image_chance, settings.video_chance, settings.audio_chance)
        settings.image_chance = 0
        settings.video_chance = 0
        settings.audio_chance = 0
        quieted = engine_control.duck_audio(state, root)      # long audio tracks fade out and pause too
        file_log.write(BASE_DIR, "hibernate: going quiet" + (f" ({quieted} audio track(s) fading out)" if quieted else ""),
                       "info")
        sleep_minutes = random.uniform(ae_settings.get("hibernate_sleep_min_minutes", 5),
                                        ae_settings.get("hibernate_sleep_max_minutes", 15))
        root.after(int(sleep_minutes * 60000), exit_hibernate)

    def exit_hibernate():
        progression["hibernating"] = False
        settings.image_chance, settings.video_chance, settings.audio_chance = progression["chances_backup"]
        reset_corruption()  # resume at base corruption level, per the user's request
        back = engine_control.unduck_audio(state, root, settings.audio_volume)
        file_log.write(BASE_DIR, "hibernate: resuming at base corruption level"
                       + (f" ({back} audio track(s) fading back in)" if back else ""), "info")
        schedule_next_hibernate()

    def schedule_next_hibernate():
        run_minutes = random.uniform(ae_settings.get("hibernate_run_min_minutes", 20),
                                      ae_settings.get("hibernate_run_max_minutes", 40))
        root.after(int(run_minutes * 60000), enter_hibernate)

    def reload_settings():
        """Save while running: take the new values at once (popup timing, auto-close, chances, volumes, fullscreen
        video). Popups already on screen keep their old values. Hibernate and corruption timers keep running."""
        nonlocal base_delay, base_corruption_interval
        _write_config_overrides()
        settings.config = load_engine_config()
        settings.load_settings()
        settings.corruption_mode = False
        fresh = load_settings(str(SETTINGS_PATH))
        ae_settings.clear()
        ae_settings.update(fresh)
        raw_cfg.clear()
        raw_cfg.update(effective_cfg(fresh, INTENSITY_PRESETS))
        base_delay = settings.delay
        base_corruption_interval = settings.corruption_time
        progression["corruption_interval"] = base_corruption_interval
        if progression["hibernating"]:        # stay quiet until the sleep ends, then use the new chances
            progression["chances_backup"] = (settings.image_chance, settings.video_chance, settings.audio_chance)
            settings.image_chance = settings.video_chance = settings.audio_chance = 0
        ae_video_popup.configure(fresh.get("fullscreen_video_chance", 15), fresh.get("fullscreen_video_max_seconds", 600),
                                 BASE_DIR, fresh.get("fullscreen_video_volume_pct", 70),
                                 fresh.get("fullscreen_video_min_height", 1080),
                                 click_close=fresh.get("fullscreen_video_click_close", True))
        _hypno_mod.configure(fresh.get("hypno_beat_volume", 20))
        file_log.write(BASE_DIR, f"settings reloaded: popup every {settings.delay} ms, "
                                 f"auto-close {'on, ' + str(settings.timeout) + ' ms' if settings.timeout_enabled else 'off'}",
                       "info")

    state.ae_reload = reload_settings

    if raw_cfg.get("corruptionMode"):
        root.after(progression["corruption_interval"], escalate_corruption)
    if ae_settings.get("hibernate"):
        schedule_next_hibernate()

    def main_loop():
        try:
            roll_targets(settings, targets)
        except Exception:
            import traceback
            file_log.write(BASE_DIR, "popup roll failed:\n" + traceback.format_exc(), "error")
        root.after(hero.next_popup_delay_ms(settings.delay), main_loop)

    def _safe(label, fn):
        """Runs one start_main() step in isolation - if it throws, the
        error goes to our own log file (visible even with no console
        window) and every LATER step - including main_loop() itself -
        still runs. Without this, one failing step silently prevents
        everything after it, tray icon and popups included, since
        start_main() runs from a Tkinter callback chain that swallows
        exceptions to stderr and just stops."""
        try:
            fn()
        except Exception:
            import traceback
            file_log.write(BASE_DIR, f"'{label}' failed during startup:\n" + traceback.format_exc(), "error")

    def wallpaper_loop():
        try:
            changer.tick()
        except Exception:
            import traceback
            file_log.write(BASE_DIR, "wallpaper tick failed:\n" + traceback.format_exc(), "error")
        root.after(15000, wallpaper_loop)

    def start_main():
        _safe("hypno mode", hypno.start)
        _safe("hero mode", hero.start)
        if changer is not None:
            _safe("wallpaper changer", lambda: (changer.start(), wallpaper_loop()))
        _safe("tray icon", lambda: make_tray_icon(root, settings, pack, state, lambda: main_hibernate(root, settings, pack, state, targets)))
        _safe("desktop icons", lambda: make_desktop_icons(settings))
        _safe("keyboard handler", lambda: handle_keyboard(root, settings, state))
        _safe("panic listener", lambda: start_panic_listener(root, settings, state))
        _safe("fill drive", lambda: Thread(target=lambda: fill_drive(root, settings, pack, state), daemon=True).start())
        _safe("replace images", lambda: Thread(target=lambda: replace_images(settings, pack), daemon=True).start())
        _safe("corruption", lambda: handle_corruption(root, settings, pack, state))
        _safe("discord", lambda: handle_discord(settings, pack))
        _safe("panic lockout", lambda: handle_panic_lockout(root, settings, state))
        _safe("mitosis mode", lambda: handle_mitosis_mode(root, settings, pack, state))
        # Autoedgeware has no pack script (LivePack has no paths): skip it instead of logging an error each start.
        if getattr(pack, "paths", None) is not None:
            _safe("script", lambda: run_script(root, settings, pack, state))

        if settings.hibernate_mode:
            _safe("hibernate", lambda: start_main_hibernate(root, settings, pack, state, targets))
        else:
            _safe("wallpaper", lambda: handle_wallpaper(root, settings, pack, state))
            main_loop()  # deliberately NOT wrapped in _safe - this one must always run

    def begin():
        if settings.startup_splash:
            _start_with_splash(root, settings, pack, media_roots, start_main)
        else:
            start_main()

    try:
        wait_s = max(0, min(3600, int(ae_settings.get("startup_delay_seconds", 0) or 0)))
    except (TypeError, ValueError):
        wait_s = 0
    if wait_s:
        file_log.write(BASE_DIR, f"startup: waiting {wait_s} s before anything starts", "info")
        root.after(wait_s * 1000, begin)
    else:
        begin()

    return pack, state, settings


def main():
    presets = load_presets(str(PRESETS_PATH))
    chosen = pick_preset(presets, load_settings(str(SETTINGS_PATH)), sys.argv)
    if chosen is None:
        log("No presets yet. Open the Autoedgeware window and make one first.", "error")
        return
    chosen.enabled = True
    presets = [chosen]
    scraper_scheduler = _start_scraper(presets)

    root = Tk()
    root.withdraw()
    _pack, state, _settings = build_and_start(root, presets)

    try:
        root.mainloop()
    finally:
        scraper_scheduler.stop_all()
        engine_control.restore_wallpaper(state)
        engine_control.stop_tray(state)
        engine_control.stop_hypno(state, final=True)
        engine_control.stop_hero(state, final=True)


if __name__ == "__main__":
    main()
