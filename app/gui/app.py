"""Autoedgeware's window. Three tabs: Main (pick a preset and an intensity), Settings (custom
intensity, general options, advanced) and Log. The status line and the action buttons stay visible
under every tab.

Two kinds of 'preset' live here on purpose:
  - Scrape presets (ae_settings/preset.py): a name plus one or more site/query sources.
  - Intensity presets (gui/theme.py): the built-in popup bundles from Edgeware, plus Custom.
"""
import os
import sys
import time
from threading import Thread
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ae_settings.preset import Preset, load_presets, save_presets
from ae_settings.preset_io import export_preset, import_presets
from ae_settings.settings import load_settings, save_settings
from core import custom_intensity, updater, engine_control, file_log, media_caps, min_size, startup_shortcut, video_tidy
from core.api_keys import API_KEYS, build_source_kwargs
from core.engine_launch import start_engine
from core.friendly import friendly
from core.pool_stats import count_media, count_text, status_line
from core.scheduler import ScrapeScheduler
from core.source_registry import SOURCE_REGISTRY
from gui import theme
from gui.first_run_dialog import FirstRunDialog
from gui.preset_editor import PresetEditorDialog
from gui.style import ColumnList, DropMenu, FlatButton, FlatEntry, TabBar, Toggle, mix, style_scrollbar
from gui.widgets import ScrollFrame

HERO_FIELDS_DEFAULTS = {"hero_click_volume": 40, "hero_round_seconds": 120, "hero_rounds_to_full": 8, "hero_frenzy_percent": 50,
                        "hero_hold_seconds": 10, "hero_bpm_min": 50, "hero_bpm_max": 140}
from main import ensure_default_presets

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRESETS_PATH = os.path.join(BASE_DIR, "ae_settings", "presets.json")
SETTINGS_PATH = os.path.join(BASE_DIR, "ae_settings", "settings.json")
MEDIA_ROOT = os.path.join(os.path.dirname(BASE_DIR), "media")   # next to run.bat
RUN_ENGINE_PY = os.path.join(BASE_DIR, "run_engine.py")
PAUSE_SECONDS = 300
CUSTOM = "Custom"


class AutoedgewareGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.pal = theme.PALETTE
        self.title(f"Autoedgeware v{theme.read_version(BASE_DIR).lstrip('vV')}")
        self.configure(bg=self.pal["bg"])
        self.geometry("700x860")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.presets = ensure_default_presets()
        self.settings = load_settings(SETTINGS_PATH)
        self.scheduler = None
        self._engine_started = False   # whether the real popup engine is attached to this window yet
        self._stopped = False          # Stop pressed (or panic) and Run not pressed since
        self._live_pack = None
        self._live_state = None
        self._live_settings = None
        self._pause_until = None
        self._pause_job = None
        self._notice = ("", 0.0)       # (plain-language message, show until)

        s = self.settings
        self.selected_name = tk.StringVar()
        self.interval_var = tk.StringVar()
        self.limit_var = tk.StringVar()
        self.hibernate_var = tk.BooleanVar(value=s.get("hibernate", False))
        self.hib_run_min_var = tk.StringVar(value=str(s.get("hibernate_run_min_minutes", 20)))
        self.hib_run_max_var = tk.StringVar(value=str(s.get("hibernate_run_max_minutes", 40)))
        self.hib_sleep_min_var = tk.StringVar(value=str(s.get("hibernate_sleep_min_minutes", 5)))
        self.hib_sleep_max_var = tk.StringVar(value=str(s.get("hibernate_sleep_max_minutes", 15)))
        self.popup_timeout_var = tk.BooleanVar(value=s.get("popup_timeout_enabled", False))
        self.popup_timeout_seconds_var = tk.StringVar(value=str(s.get("popup_timeout_seconds", 10)))
        self.update_check_var = tk.BooleanVar(value=bool(s.get("check_for_updates", True)))
        self.delay_var = tk.StringVar(value=str(s.get("startup_delay_seconds", 0)))
        self.auto_stop_var = tk.BooleanVar(value=s.get("auto_stop_after_pass", True))
        self.gelbooru_key_var = tk.StringVar(value=s.get("gelbooru_api_key", ""))
        self.gelbooru_uid_var = tk.StringVar(value=s.get("gelbooru_user_id", ""))
        self.api_key_vars = {setting_key: tk.StringVar(value=s.get(setting_key, ""))
                             for _src, setting_key, _label, _hint in API_KEYS}
        self.hypno_var = tk.BooleanVar(value=s.get("hypno_mode", False))
        self.hero_var = tk.BooleanVar(value=s.get("hero_mode", False))
        self.hero_text_var = tk.BooleanVar(value=s.get("hero_text", True))
        self.hero_vars = {key: tk.StringVar(value=str(s.get(key, default))) for key, default in HERO_FIELDS_DEFAULTS.items()}
        self.wallpaper_var = tk.BooleanVar(value=s.get("wallpaper_changer_on", True))
        self.wallpaper_minutes_var = tk.StringVar(value=str(s.get("wallpaper_minutes", 2)))
        self.fs_chance_var = tk.StringVar(value=str(s.get("fullscreen_video_chance", 15)))
        self.fs_seconds_var = tk.StringVar(value=str(s.get("fullscreen_video_max_seconds", 600)))
        self.cap_vars = {key: tk.StringVar(value=str(s.get(key, media_caps.DEFAULT_CAPS[kind])))
                         for kind, key in media_caps.SETTING_KEYS.items()}
        self.min_px_var = tk.StringVar(value=str(s.get(min_size.SETTING_KEY, min_size.DEFAULT_MIN_IMAGE_PX)))
        self.video_click_var = tk.BooleanVar(value=bool(s.get("fullscreen_video_click_close", True)))
        self.vid_max_var = tk.StringVar(value=str(s.get("video_max_seconds", video_tidy.DEFAULT_MAX_SECONDS)))
        self.vid_shrink_var = tk.StringVar(value=str(s.get("video_shrink_to_px", video_tidy.DEFAULT_SHRINK_TO)))
        self.fs_volume_var = tk.StringVar(value=str(s.get("fullscreen_video_volume_pct", 70)))
        self.fs_minh_var = tk.StringVar(value=str(s.get("fullscreen_video_min_height", 1080)))
        self.beat_volume_var = tk.StringVar(value=str(s.get("hypno_beat_volume", 20)))
        self.audio_volume_var = tk.StringVar(value=str(s.get("audio_volume", 50)))
        self.video_volume_var = tk.StringVar(value=str(s.get("video_volume", 20)))
        self.max_audio_var = tk.StringVar(value=str(s.get("max_audio", 1)))
        self.status_var = tk.StringVar(value="Ready.")

        saved_custom = dict(custom_intensity.DEFAULTS)
        saved_custom.update(s.get("custom_cfg") or {})
        saved_custom["speedup_percent"] = s.get("corruption_speedup_percent", saved_custom["speedup_percent"])
        self.custom_vars = {}
        for key, _label, kind, _lo, _hi in custom_intensity.FIELDS:
            shown = custom_intensity.to_display(key, saved_custom[key])
            self.custom_vars[key] = tk.BooleanVar(value=shown) if kind == "bool" else tk.StringVar(value=shown)

        style_scrollbar(self)
        self._build_ui()

        names = [p.name for p in self.presets]
        wanted = s.get("last_preset")
        if names:
            self.selected_name.set(wanted if wanted in names else names[0])
            self._load_preset_into_fields(self._find_preset(self.selected_name.get()))

        applied = s.get("edgeware_cfg_name")
        fresh = next((dict(b) for n, b in theme.INTENSITY_PRESETS if n == applied), None)
        if fresh is not None:
            s["edgeware_cfg"] = fresh      # a bundle saved by an older version may hold old values (moving popups)
        if applied in self._intensity_buttons:
            self._highlight_intensity_button(applied)
        elif not s.get("edgeware_cfg"):
            default_name, default_values = theme.INTENSITY_PRESETS[0]
            self._apply_intensity(default_name, default_values)

        self._refresh_buttons()
        self.after(80, self._fit_height)
        self.after(1500, self._tick)
        self.after(300, self._maybe_first_run)
        self._update_found = None
        self._update_polls = 0
        if self.settings.get("check_for_updates", True):
            self.after(2500, self._start_update_check)

    def _fit_height(self):
        """Grow the window just enough that the Main tab needs no scroll bar (never taller than the screen)."""
        self.update_idletasks()
        canvas = self.main_scroll.canvas
        extra = self.main_scroll.body.winfo_reqheight() - canvas.winfo_height()
        if extra > 0:
            height = min(self.winfo_height() + extra + 6, self.winfo_screenheight() - 90)
            self.geometry(f"700x{height}")

    # ---------- style helpers ----------

    def _btn(self, parent, text, command, primary=False, danger=False):
        if danger:
            return FlatButton(parent, text=text, command=command, bg=self.pal["panel3"], fg=self.pal["danger"],
                              hover=mix(self.pal["panel3"], self.pal["danger"], 0.35), activeforeground=self.pal["white"])
        return FlatButton(parent, text=text, command=command,
                          bg=self.pal["accent"] if primary else self.pal["panel3"], fg=self.pal["white"],
                          activeforeground=self.pal["white"])

    def _label(self, parent, text, **kw):
        return tk.Label(parent, text=text, bg=kw.pop("bg", self.pal["panel"]),
                        fg=kw.pop("fg", self.pal["white"]), font=("Segoe UI", 9, "bold"), **kw)

    def _hint(self, parent, text, wrap=560):
        return tk.Label(parent, text=text, bg=self.pal["panel"], fg=self.pal["muted"],
                        font=("Segoe UI", 8), wraplength=wrap, justify="left")

    def _entry(self, parent, var, width=None):
        e = FlatEntry(parent, textvariable=var)
        if width:
            e.configure(width=width)
        return e

    def _check(self, parent, text, var):
        return Toggle(parent, text=text, variable=var, bg=self.pal["panel"], fg=self.pal["white"],
                      font=("Segoe UI", 9))

    def _option_menu(self, parent, var, choices, command=None):
        return DropMenu(parent, var, choices, command=command, bg=self.pal["panel3"], fg=self.pal["white"])

    def _card(self, parent, title):
        card = tk.Frame(parent, bg=self.pal["panel"], highlightthickness=1, highlightbackground=self.pal["border"])
        card.pack(fill="x", padx=2, pady=(0, 10))
        tk.Label(card, text=title, bg=self.pal["panel"], fg=self.pal["accent2"],
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=16, pady=(14, 2))
        tk.Frame(card, bg=self.pal["border"], height=1).pack(fill="x", padx=16, pady=(4, 8))
        body = tk.Frame(card, bg=self.pal["panel"])
        body.pack(fill="x", padx=16, pady=(0, 14))
        return body

    # ---------- UI construction ----------

    def _build_ui(self):
        pal = self.pal
        header = tk.Frame(self, bg=pal["bg"])
        header.pack(fill="x", padx=20, pady=(16, 10))
        self._header = header
        tk.Label(header, text="AUTOEDGEWARE", bg=pal["bg"], fg=pal["white"],
                 font=("Segoe UI", 17, "bold")).pack(side="left")
        tk.Label(header, text=f"v{theme.read_version(BASE_DIR).lstrip('vV')}", bg=pal["panel3"], fg=pal["accent2"],
                 font=("Segoe UI", 8, "bold"), padx=8, pady=2).pack(side="left", padx=(10, 0), pady=(5, 0))

        self.update_btn = None            # appears in the header when GitHub has a newer version

        # Bottom bar first, so it always keeps its space.
        bottom = tk.Frame(self, bg=pal["panel"])
        bottom.pack(side="bottom", fill="x")
        self._bottom = bottom
        tk.Frame(bottom, bg=pal["border"], height=1).pack(fill="x")
        inner = tk.Frame(bottom, bg=pal["panel"])
        inner.pack(fill="x", padx=20, pady=(10, 14))
        tk.Label(inner, textvariable=self.status_var, bg=pal["panel"], fg=pal["muted"], font=("Segoe UI", 9),
                 anchor="w", justify="left", wraplength=660).pack(fill="x", pady=(0, 10))
        brow = tk.Frame(inner, bg=pal["panel"])
        brow.pack(fill="x")
        self.run_btn = self._btn(brow, "Run", self.run_now, primary=True)
        self.run_btn.pack(side="left")
        self.pause_btn = self._btn(brow, "Pause 5 min", self.pause_now)
        self.pause_btn.pack(side="left", padx=(8, 0))
        self.stop_btn = self._btn(brow, "Stop", self.stop_now, danger=True)
        self.stop_btn.pack(side="left", padx=(8, 0))
        self._btn(brow, "Save, Exit and Run", self.save_exit_and_run).pack(side="right")
        self._btn(brow, "Save & Exit", self.save_and_exit).pack(side="right", padx=(0, 8))
        self._btn(brow, "Save", self.save).pack(side="right", padx=(0, 8))

        self.notebook = TabBar(self, bg=pal["bg"], accent=pal["accent"])
        self.notebook.pack(fill="both", expand=True, padx=20, pady=(0, 8))
        stage = self.notebook.stage
        self.main_scroll = ScrollFrame(stage, pal["bg"])
        self.main_tab = self.main_scroll
        self.popups_scroll = ScrollFrame(stage, pal["bg"])
        self.modes_scroll = ScrollFrame(stage, pal["bg"])
        self.downloads_scroll = ScrollFrame(stage, pal["bg"])
        self.advanced_scroll = ScrollFrame(stage, pal["bg"])
        self.log_tab = tk.Frame(stage, bg=pal["bg"])
        self.notebook.add(self.main_tab, "Main")
        self.notebook.add(self.popups_scroll, "Popups")
        self.notebook.add(self.modes_scroll, "Modes")
        self.notebook.add(self.downloads_scroll, "Downloads")
        self.notebook.add(self.advanced_scroll, "Advanced")
        self.notebook.add(self.log_tab, "Log")

        self._build_main_tab(self.main_scroll.body)
        self._build_popups_tab(self.popups_scroll.body)
        self._build_modes_tab(self.modes_scroll.body)
        self._build_downloads_tab(self.downloads_scroll.body)
        self._build_advanced_tab(self.advanced_scroll.body)
        self._build_log_tab(self.log_tab)

    def _build_main_tab(self, tab):
        pal = self.pal
        body = self._card(tab, "SCRAPE PRESET")
        row = tk.Frame(body, bg=pal["panel"])
        row.pack(fill="x")
        names = [p.name for p in self.presets] or ["(none yet)"]
        self.preset_menu = self._option_menu(row, self.selected_name, names, command=self._on_select_preset)
        self.preset_menu.configure(width=14)
        self.preset_menu.pack(side="left")
        self._btn(row, "Delete", self._delete_preset, danger=True).pack(side="right")
        for text, cmd in (("Export", self._export_preset), ("Import", self._import_presets),
                          ("Edit", self._edit_preset), ("Create", self._create_preset), ("Find", self._open_finder)):
            self._btn(row, text, cmd).pack(side="right", padx=(0, 6))
        self.description_label = ColumnList(body, rows=5, bg=pal["panel2"], fg=pal["muted"])
        self.description_label.pack(fill="x", pady=(12, 0))
        self.media_count_label = tk.Label(body, text="", bg=pal["panel"], fg=pal["accent2"],
                                          font=("Segoe UI", 9, "bold"), anchor="w")
        self.media_count_label.pack(fill="x", pady=(6, 0))
        Toggle(body, text="Hypno mode", variable=self.hypno_var, command=self._on_hypno_toggle,
               bg=pal["panel"], fg=pal["white"], font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(12, 0))
        self._hint(body, "A faint black-and-white spiral covers the screen and binaural beats play (use headphones). "
                         "Faster popups make it stronger.", wrap=540).pack(anchor="w", padx=(43, 0), pady=(2, 0))
        Toggle(body, text="Hero mode", variable=self.hero_var, command=self._on_hero_toggle,
               bg=pal["panel"], fg=pal["white"], font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(12, 0))
        self._hint(body, "A beat bar runs along the bottom of the screen: circles meet a ring, it flashes green and "
                         "clicks. Popups follow the rhythm, speeding up, slowing down and holding. "
                         "Nothing is recorded. Save first, then switch it on.", wrap=540).pack(anchor="w", padx=(43, 0), pady=(2, 0))

        ibody = self._card(tab, "INTENSITY")
        grid = tk.Frame(ibody, bg=pal["panel"])
        grid.pack(fill="x")
        self._intensity_buttons = {}
        entries = [(name, lambda n=name, v=values: self._apply_intensity(n, v))
                   for name, values in theme.INTENSITY_PRESETS]
        entries.append((CUSTOM, self._use_custom))
        for idx, (name, cmd) in enumerate(entries):
            label = "Custom..." if name == CUSTOM else name
            b = self._btn(grid, label, cmd)
            b.configure(pady=12)
            b.grid(row=idx // 2, column=idx % 2, sticky="we", padx=(0 if idx % 2 else 0, 6 if idx % 2 == 0 else 0),
                   pady=(0, 6))
            self._intensity_buttons[name] = b
        grid.grid_columnconfigure(0, weight=1)
        grid.grid_columnconfigure(1, weight=1)
        self._hint(ibody, "Custom... opens the Popups tab, where you set every value yourself.").pack(anchor="w")

    # ---------- small layout helpers for the settings tabs ----------

    def _rows(self, parent):
        """A two-column grid: label on the left, small entry on the right."""
        grid = tk.Frame(parent, bg=self.pal["panel"])
        grid.pack(fill="x")
        grid.grid_columnconfigure(0, weight=1)
        grid._next_row = 0
        return grid

    def _add_field(self, grid, label, var, width=8):
        r = grid._next_row
        grid._next_row += 1
        self._label(grid, label).grid(row=r, column=0, sticky="w", pady=2)
        self._entry(grid, var, width=width).grid(row=r, column=1, sticky="e", padx=(10, 0))

    def _add_pair(self, grid, label, var_a, var_b, width=6):
        """Two entries on one line (from / to)."""
        r = grid._next_row
        grid._next_row += 1
        self._label(grid, label).grid(row=r, column=0, sticky="w", pady=2)
        pair = tk.Frame(grid, bg=self.pal["panel"])
        pair.grid(row=r, column=1, sticky="e", padx=(10, 0))
        self._entry(pair, var_a, width=width).pack(side="left")
        self._label(pair, "to").pack(side="left", padx=6)
        self._entry(pair, var_b, width=width).pack(side="left")

    def _add_check(self, grid, label, var):
        r = grid._next_row
        grid._next_row += 1
        self._check(grid, label, var).grid(row=r, column=0, columnspan=2, sticky="w", pady=2)

    # ---------- Popups tab ----------

    def _build_popups_tab(self, body):
        pal = self.pal
        c = self._card(body, "CUSTOM INTENSITY")
        self._hint(c, "Used when you pick Custom on the Main tab.").pack(anchor="w", pady=(0, 4))
        grid = self._rows(c)
        for key, label, kind, lo, hi in custom_intensity.FIELDS:
            if kind == "bool":
                self._add_check(grid, label, self.custom_vars[key])
            else:
                self._add_field(grid, label, self.custom_vars[key], width=10)
        self._btn(c, "Use these values", self._apply_custom_clicked, primary=True).pack(anchor="w", pady=(8, 0))

        snd = self._card(body, "SOUND")
        grid2 = self._rows(snd)
        for label, var in (("Audio volume (0-100)", self.audio_volume_var),
                           ("Video volume (0-100)", self.video_volume_var),
                           ("Audio tracks at once", self.max_audio_var),
                           ("Fullscreen video volume (%)", self.fs_volume_var),
                           ("Hypno beats volume (0-100)", self.beat_volume_var)):
            self._add_field(grid2, label, var)
        self._hint(snd, "Save, then Run to apply.").pack(anchor="w", pady=(6, 0))

        ac = self._card(body, "AUTO-CLOSE")
        self._check(ac, "Close popups by themselves after (sec):", self.popup_timeout_var).pack(anchor="w")
        self._entry(ac, self.popup_timeout_seconds_var, width=8).pack(anchor="w", pady=(2, 0))

        fs = self._card(body, "FULLSCREEN VIDEO")
        self._hint(fs, "Wide videos can fill a monitor, with other popups on top.").pack(anchor="w", pady=(0, 4))
        g3 = self._rows(fs)
        self._add_field(g3, "Chance (%)", self.fs_chance_var)
        self._add_field(g3, "Longest video (sec)", self.fs_seconds_var)
        self._add_field(g3, "Only videos taller than (px)", self.fs_minh_var)
        self._add_check(g3, "Clicking a fullscreen video closes it", self.video_click_var)

    # ---------- Modes tab ----------

    def _build_modes_tab(self, body):
        hero = self._card(body, "HERO MODE")
        self._hint(hero, "Switch it on from the Main tab. Each round lasts \"Speed up every\" seconds, "
                         "and the tempo climbs every round.").pack(anchor="w", pady=(0, 4))
        hg = self._rows(hero)
        self._add_check(hg, "Show the instruction line (Stroke, Hold...)", self.hero_text_var)
        for label, key in (("Click volume (0-100)", "hero_click_volume"),
                           ("Slowest tempo (beats/min)", "hero_bpm_min"),
                           ("Fastest tempo (beats/min)", "hero_bpm_max"),
                           ("Speed up every (sec)", "hero_round_seconds"),
                           ("Rounds to full speed", "hero_rounds_to_full"),
                           ("Hold length (sec)", "hero_hold_seconds"),
                           ("Frenzy rounds (%)", "hero_frenzy_percent")):
            self._add_field(hg, label, self.hero_vars[key])

        hib = self._card(body, "HIBERNATE")
        self._hint(hib, "Run for a while, go quiet, then start again.").pack(anchor="w", pady=(0, 4))
        hg2 = self._rows(hib)
        self._add_check(hg2, "Hibernate", self.hibernate_var)
        self._add_pair(hg2, "Run for (min)", self.hib_run_min_var, self.hib_run_max_var)
        self._add_pair(hg2, "Sleep for (min)", self.hib_sleep_min_var, self.hib_sleep_max_var)

        wp = self._card(body, "WALLPAPER")
        self._hint(wp, "Uses wide pictures from the running preset. Your own wallpaper returns on Stop.").pack(anchor="w", pady=(0, 4))
        wg = self._rows(wp)
        self._add_check(wg, "Change my wallpaper while running", self.wallpaper_var)
        self._add_field(wg, "Change every (min)", self.wallpaper_minutes_var, width=6)

    # ---------- Downloads tab ----------

    def _build_downloads_tab(self, body):
        lim = self._card(body, "LIMITS")
        self._hint(lim, "Files kept per preset. A kind stops downloading once full. 0 = no limit.").pack(anchor="w", pady=(0, 4))
        lg = self._rows(lim)
        for kind, label in (("images", "Images"), ("videos", "Videos"), ("audio", "Audio")):
            self._add_field(lg, label, self.cap_vars[media_caps.SETTING_KEYS[kind]], width=6)
        self._hint(lim, "Delete pictures smaller than this (px, shorter side). 0 = keep all.").pack(anchor="w", pady=(10, 4))
        mg = self._rows(lim)
        self._add_field(mg, "Smallest picture (px)", self.min_px_var, width=6)

        vid = self._card(body, "VIDEOS")
        self._hint(vid, "Keeps new videos light. Needs ffmpeg. 0 = off.").pack(anchor="w", pady=(0, 4))
        vg = self._rows(vid)
        self._add_field(vg, "Cut videos longer than (sec)", self.vid_max_var, width=6)
        self._add_field(vg, "Shrink small videos to (px tall)", self.vid_shrink_var, width=6)

        sc = self._card(body, "SCRAPING")
        sg = self._rows(sc)
        self._add_check(sg, "Stop downloading after one pass (popups keep going)", self.auto_stop_var)
        self._hint(sc, "The next two apply to the selected preset.").pack(anchor="w", pady=(8, 4))
        sg2 = self._rows(sc)
        self._add_field(sg2, "Re-scrape every (sec)", self.interval_var)
        self._add_field(sg2, "Items per source per cycle", self.limit_var)

    # ---------- Advanced tab ----------

    def _build_advanced_tab(self, body):
        st = self._card(body, "STARTUP")
        sg = self._rows(st)
        self._add_field(sg, "Wait before popups start (sec)", self.delay_var)
        self._add_check(sg, "Check for updates at startup", self.update_check_var)
        srow = tk.Frame(st, bg=self.pal["panel"])
        srow.pack(fill="x", pady=(8, 0))
        self._label(srow, "Windows startup").pack(side="left")
        self._btn(srow, "Add to Startup Apps", self._add_to_startup).pack(side="left", padx=(10, 0))
        self._btn(srow, "Remove", self._remove_from_startup).pack(side="left", padx=(6, 0))
        self.startup_status_label = self._hint(st, "")
        self.startup_status_label.pack(anchor="w", pady=(4, 0))
        self._update_startup_label()

        keys = self._card(body, "SITE KEYS (OPTIONAL)")
        self._hint(keys, "Only needed for Gelbooru and Wallhaven.").pack(anchor="w")
        box = tk.Frame(keys, bg=self.pal["panel"])
        self._keys_box, self._keys_open = box, False
        self._keys_btn = self._btn(keys, "Show keys", self._toggle_keys)
        self._keys_btn.pack(anchor="w", pady=(6, 0))
        self._label(box, "Gelbooru API key").pack(anchor="w", pady=(8, 0))
        self._hint(box, "Gelbooru asks for a key now. Without one, pages are read directly.").pack(anchor="w")
        self._entry(box, self.gelbooru_key_var).pack(fill="x", pady=(2, 6))
        self._label(box, "Gelbooru user ID").pack(anchor="w")
        self._entry(box, self.gelbooru_uid_var).pack(fill="x", pady=(2, 6))
        for _src, setting_key, label, hint in API_KEYS:
            self._label(box, label).pack(anchor="w")
            self._hint(box, hint).pack(anchor="w")
            self._entry(box, self.api_key_vars[setting_key]).pack(fill="x", pady=(2, 6))

    def _toggle_keys(self):
        self._keys_open = not self._keys_open
        if self._keys_open:
            self._keys_box.pack(fill="x", after=self._keys_btn)
            self._keys_btn.configure(text="Hide keys")
        else:
            self._keys_box.pack_forget()
            self._keys_btn.configure(text="Show keys")

    def _build_log_tab(self, tab):
        pal = self.pal
        card = tk.Frame(tab, bg=pal["entry"], highlightthickness=1, highlightbackground=pal["border"])
        card.pack(fill="both", expand=True, padx=2, pady=(0, 6))
        scrollbar = ttk.Scrollbar(card, orient="vertical", style="AE.Vertical.TScrollbar")
        scrollbar.pack(side="right", fill="y")
        self.log_text = tk.Text(card, bg=pal["entry"], fg=pal["muted"], relief="flat", font=("Consolas", 9),
                                wrap="word", yscrollcommand=scrollbar.set, state="disabled", padx=8, pady=6,
                                highlightthickness=0, bd=0)
        self.log_text.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        scrollbar.config(command=self.log_text.yview)

    # ---------- log + status ----------

    def _log(self, msg, level="info"):
        file_log.write(BASE_DIR, msg, level)
        try:
            self.after(0, self._append_log, msg, level)
        except (tk.TclError, RuntimeError):
            pass   # window already closed

    def _append_log(self, msg, level):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{level.upper()}] {msg}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        plain = friendly(msg, level)
        if plain and not self._stopped:
            self._notify(plain, 20)

    def _notify(self, text, seconds=8):
        self._notice = (text, time.time() + seconds)
        self.status_var.set(text)

    def _update_media_count(self):
        name = self.selected_name.get()
        counts = count_media(os.path.join(MEDIA_ROOT, name)) if name else (0, 0, 0)
        self.media_count_label.configure(text=count_text(counts) if name else "")

    def _tick(self):
        try:
            self._update_media_count()
            self._update_status()
        except Exception:
            pass
        self.after(1500, self._tick)

    def _selected_folder(self):
        return os.path.join(MEDIA_ROOT, self.selected_name.get())

    def _update_status(self):
        text, until = self._notice
        if text and time.time() < until:
            return
        if self._stopped:
            self.status_var.set("Stopped.")
            return
        scraping = bool(self.scheduler and self.scheduler.workers)
        paused = max(0, self._pause_until - time.time()) if self._pause_until else None
        counts = count_media(self._selected_folder()) if (scraping or self._engine_started) else (0, 0, 0)
        self.status_var.set(status_line(counts, scraping, self._engine_started, paused))

    def _refresh_buttons(self):
        scraping = bool(self.scheduler and self.scheduler.workers)
        live = self._engine_started and not self._stopped
        self.run_btn.configure(state="disabled" if scraping else "normal")
        self.stop_btn.configure(state="normal" if (scraping or live) else "disabled")
        self.pause_btn.configure(state="normal" if live else "disabled",
                                 text="Resume now" if self._pause_until else "Pause 5 min")

    # ---------- data plumbing ----------

    def _find_preset(self, name):
        return next((p for p in self.presets if p.name == name), None)

    def _load_preset_into_fields(self, preset):
        self.interval_var.set(str(preset.interval_seconds))
        self.limit_var.set(str(preset.limit))
        self.description_label.configure(text=preset.description())
        self._update_media_count()

    def _on_select_preset(self, name):
        preset = self._find_preset(name)
        if preset:
            self._load_preset_into_fields(preset)

    def _rebuild_preset_menu(self):
        menu = self.preset_menu["menu"]
        menu.delete(0, "end")
        for p in self.presets:
            menu.add_command(label=p.name,
                             command=lambda n=p.name: (self.selected_name.set(n), self._on_select_preset(n)))

    def _sync_fields_into_selected(self):
        preset = self._find_preset(self.selected_name.get())
        if not preset:
            return
        try:
            preset.interval_seconds = int(self.interval_var.get())
        except ValueError:
            pass
        try:
            preset.limit = int(self.limit_var.get())
        except ValueError:
            pass

    def _add_preset(self, preset):
        self.presets.append(preset)
        self._rebuild_preset_menu()
        self.selected_name.set(preset.name)
        self._load_preset_into_fields(preset)

    # ---------- presets: first run, create, edit, import, export ----------

    def _only_default_preset(self):
        """True while the only preset is the untouched starter 'Nature'."""
        return len(self.presets) == 1 and self.presets[0].name == "Nature"

    def _maybe_first_run(self):
        if not self.presets:
            FirstRunDialog(self, self.pal, self._on_first_run_submit)
        elif self._only_default_preset() and not self.settings.get("first_run_done"):
            self.settings["first_run_done"] = True      # ask once; saved with the next Save/Run
            FirstRunDialog(self, self.pal, self._on_first_run_submit)

    def _on_first_run_submit(self, name, sources, start_now):
        if self._only_default_preset():                  # the starter is replaced by what they asked for
            self.presets.clear()
        name = self._unique_name(name)
        self._add_preset(Preset(name=name, sources=sources, interval_seconds=300, limit=30))
        self.save()
        self._notify(f"Made '{name}'.")
        if start_now:
            self.run_now()

    def _open_finder(self):
        from gui.preset_finder_dialog import PresetFinderDialog

        def done(name, sources, start_now):
            name = self._unique_name(name)
            self._add_preset(Preset(name=name, sources=sources, interval_seconds=300, limit=30))
            self.save()
            self._notify(f"Made '{name}' with {len(sources)} source(s).")
            if start_now:
                self.run_now()
        PresetFinderDialog(self, self.pal, done, mode="new")

    def _unique_name(self, name):
        taken = {p.name.lower() for p in self.presets}
        if name.lower() not in taken:
            return name
        n = 2
        while f"{name} ({n})".lower() in taken:
            n += 1
        return f"{name} ({n})"

    def _create_preset(self):
        def on_submit(name, sources, _enabled):
            if self._find_preset(name):
                messagebox.showerror("Autoedgeware", f"A preset named '{name}' already exists.", parent=self)
                return
            self._add_preset(Preset(name=name, sources=sources, interval_seconds=300, limit=30))
            self._notify(f"Created preset '{name}'. Save to keep it.")

        PresetEditorDialog(self, self.pal, on_submit)

    def _edit_preset(self):
        preset = self._find_preset(self.selected_name.get())
        if not preset:
            messagebox.showinfo("Autoedgeware", "No preset selected.", parent=self)
            return

        def on_submit(name, sources, _enabled):
            if name != preset.name and self._find_preset(name):
                messagebox.showerror("Autoedgeware", f"A preset named '{name}' already exists.", parent=self)
                return
            preset.name = name
            preset.sources = sources
            self._rebuild_preset_menu()
            self.selected_name.set(name)
            self._load_preset_into_fields(preset)
            self._notify(f"Updated preset '{name}'. Save to keep it.")

        PresetEditorDialog(self, self.pal, on_submit, initial_name=preset.name,
                           initial_sources=preset.sources, initial_enabled=True)

    def _delete_preset(self):
        preset = self._find_preset(self.selected_name.get())
        if not preset:
            messagebox.showinfo("Autoedgeware", "No preset selected.", parent=self)
            return
        if (self.scheduler and self.scheduler.workers) or (self._engine_started and not self._stopped):
            messagebox.showinfo("Autoedgeware", "Press Stop first, then delete the preset.", parent=self)
            return
        if len(self.presets) <= 1:
            messagebox.showinfo("Autoedgeware", "Keep at least one preset. Create another one first.", parent=self)
            return
        if not messagebox.askyesno("Delete preset", f"Delete '{preset.name}'?\n\n"
                                   "The preset is removed. Files it already downloaded stay in the media folder.",
                                   icon="warning", parent=self):
            return
        self.presets.remove(preset)
        self._rebuild_preset_menu()
        nxt = self.presets[0]
        self.selected_name.set(nxt.name)
        self._load_preset_into_fields(nxt)
        self.save()
        self._notify(f"Deleted '{preset.name}'.")

    def _import_presets(self):
        path = filedialog.askopenfilename(parent=self, title="Import a preset",
                                          filetypes=[("Preset files", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            found, skipped = import_presets(path, [p.name for p in self.presets], set(SOURCE_REGISTRY))
        except (ValueError, OSError) as ex:
            messagebox.showerror("Autoedgeware", str(ex), parent=self)
            return
        for preset in found:
            self._add_preset(preset)
        self.save()
        note = f" ({skipped} unusable source(s) skipped)" if skipped else ""
        self._notify(f"Imported {len(found)} preset(s){note}.")

    def _export_preset(self):
        preset = self._find_preset(self.selected_name.get())
        if not preset:
            messagebox.showinfo("Autoedgeware", "No preset selected.", parent=self)
            return
        path = filedialog.asksaveasfilename(parent=self, title="Export this preset", defaultextension=".json",
                                            initialfile=f"{preset.name}.json",
                                            filetypes=[("Preset files", "*.json")])
        if not path:
            return
        self._sync_fields_into_selected()
        try:
            export_preset(preset, path)
        except OSError as ex:
            messagebox.showerror("Autoedgeware", f"Could not save the file: {ex}", parent=self)
            return
        self._notify(f"Exported '{preset.name}'.")

    # ---------- intensity ----------

    def _apply_intensity(self, name, values):
        self.settings["edgeware_cfg"] = dict(values)
        self.settings["edgeware_cfg_name"] = name
        self._highlight_intensity_button(name)
        self._notify(f"Intensity: {name}. Save to keep it.")

    def _highlight_intensity_button(self, name):
        for btn_name, btn in self._intensity_buttons.items():
            btn.configure(bg=self.pal["accent"] if btn_name == name else self.pal["panel3"])

    def _use_custom(self):
        if self._apply_custom():
            self.notebook.select(self.popups_scroll)
            self.popups_scroll.to_top()

    def _apply_custom_clicked(self):
        if self._apply_custom():
            self.notebook.select(self.main_tab)

    def _apply_custom(self):
        raw = {k: v.get() for k, v in self.custom_vars.items()}
        values, errors = custom_intensity.parse(raw)
        if errors:
            self.notebook.select(self.popups_scroll)
            messagebox.showinfo("Autoedgeware", "Please fix:\n\n" + "\n".join(errors), parent=self)
            return False
        base = dict(theme.INTENSITY_PRESETS[1][1])
        self.settings["edgeware_cfg"] = custom_intensity.build_cfg(base, values)
        self.settings["edgeware_cfg_name"] = CUSTOM
        self.settings["custom_cfg"] = values
        self.settings["corruption_speedup_percent"] = values["speedup_percent"]
        self._highlight_intensity_button(CUSTOM)
        self._notify("Intensity: Custom. Save to keep it.")
        return True

    # ---------- startup shortcut ----------

    def _update_startup_label(self):
        added = startup_shortcut.is_added(BASE_DIR)
        self.startup_status_label.configure(text="Currently added to Startup Apps." if added else "Not currently added.")

    def _add_to_startup(self):
        try:
            startup_shortcut.add_to_startup(BASE_DIR)
            self._update_startup_label()
            messagebox.showinfo("Autoedgeware", "Added to Windows Startup Apps.", parent=self)
        except Exception as ex:
            messagebox.showerror("Autoedgeware", f"Couldn't add to Startup Apps: {ex}", parent=self)

    def _remove_from_startup(self):
        try:
            removed = startup_shortcut.remove_from_startup(BASE_DIR)
            self._update_startup_label()
            if removed:
                messagebox.showinfo("Autoedgeware", "Removed from Windows Startup Apps.", parent=self)
        except Exception as ex:
            messagebox.showerror("Autoedgeware", f"Couldn't remove from Startup Apps: {ex}", parent=self)

    # ---------- settings ----------

    def _collect_settings(self):
        self.settings["hibernate"] = bool(self.hibernate_var.get())
        for key, var, default in [
            ("hibernate_run_min_minutes", self.hib_run_min_var, 20),
            ("hibernate_run_max_minutes", self.hib_run_max_var, 40),
            ("hibernate_sleep_min_minutes", self.hib_sleep_min_var, 5),
            ("hibernate_sleep_max_minutes", self.hib_sleep_max_var, 15),
        ]:
            try:
                self.settings[key] = float(var.get())
            except ValueError:
                self.settings[key] = default
        try:
            self.settings["startup_delay_seconds"] = int(self.delay_var.get())
        except ValueError:
            self.settings["startup_delay_seconds"] = 0
        self.settings["check_for_updates"] = bool(self.update_check_var.get())
        self.settings["auto_stop_after_pass"] = bool(self.auto_stop_var.get())
        self.settings["popup_timeout_enabled"] = bool(self.popup_timeout_var.get())
        try:
            self.settings["popup_timeout_seconds"] = int(self.popup_timeout_seconds_var.get())
        except ValueError:
            self.settings["popup_timeout_seconds"] = 10
        self.settings["gelbooru_api_key"] = self.gelbooru_key_var.get().strip()
        self.settings["gelbooru_user_id"] = self.gelbooru_uid_var.get().strip()
        for setting_key, var in self.api_key_vars.items():
            self.settings[setting_key] = var.get().strip()
        self.settings["hypno_mode"] = bool(self.hypno_var.get())
        self.settings["hero_mode"] = bool(self.hero_var.get())
        self.settings["hero_text"] = bool(self.hero_text_var.get())
        self.settings["wallpaper_changer_on"] = bool(self.wallpaper_var.get())
        for key, var, default, lo, hi in (("wallpaper_minutes", self.wallpaper_minutes_var, 2, 1, 120),
                                          ("fullscreen_video_chance", self.fs_chance_var, 15, 0, 100),
                                          ("fullscreen_video_max_seconds", self.fs_seconds_var, 600, 10, 7200),
                                          ("fullscreen_video_volume_pct", self.fs_volume_var, 70, 0, 100),
                                          ("fullscreen_video_min_height", self.fs_minh_var, 1080, 0, 4320),
                                          ("hypno_beat_volume", self.beat_volume_var, 20, 0, 100),
                                          ("audio_volume", self.audio_volume_var, 50, 0, 100),
                                          ("video_volume", self.video_volume_var, 20, 0, 100),
                                          ("max_audio", self.max_audio_var, 1, 1, 10),
                                          ("hero_click_volume", self.hero_vars["hero_click_volume"], 40, 0, 100),
                                          ("hero_round_seconds", self.hero_vars["hero_round_seconds"], 120, 40, 900),
                                          ("hero_rounds_to_full", self.hero_vars["hero_rounds_to_full"], 8, 1, 50),
                                          ("hero_frenzy_percent", self.hero_vars["hero_frenzy_percent"], 50, 0, 100),
                                          ("hero_hold_seconds", self.hero_vars["hero_hold_seconds"], 10, 3, 120),
                                          ("hero_bpm_min", self.hero_vars["hero_bpm_min"], 50, 30, 200),
                                          ("hero_bpm_max", self.hero_vars["hero_bpm_max"], 140, 40, 240)):
            try:
                self.settings[key] = max(lo, min(hi, int(float(var.get()))))
            except ValueError:
                self.settings[key] = default
        for key, var in self.cap_vars.items():
            try:
                self.settings[key] = max(0, min(100000, int(float(var.get()))))
            except ValueError:
                self.settings[key] = media_caps.DEFAULT_CAPS[next(k for k, v in media_caps.SETTING_KEYS.items() if v == key)]
        self.settings["fullscreen_video_click_close"] = bool(self.video_click_var.get())
        for key, var, default, hi in (("video_max_seconds", self.vid_max_var, video_tidy.DEFAULT_MAX_SECONDS, 36000),
                                      ("video_shrink_to_px", self.vid_shrink_var, video_tidy.DEFAULT_SHRINK_TO, 4320)):
            try:
                self.settings[key] = max(0, min(hi, int(float(var.get()))))
            except ValueError:
                self.settings[key] = default
        try:
            self.settings[min_size.SETTING_KEY] = max(0, min(10000, int(float(self.min_px_var.get()))))
        except ValueError:
            self.settings[min_size.SETTING_KEY] = min_size.DEFAULT_MIN_IMAGE_PX
        self.settings["last_preset"] = self.selected_name.get()
        return self.settings

    def _source_kwargs(self):
        return build_source_kwargs(self.settings)

    def _on_new_media_gui(self, preset, items):
        for item in items:
            self._log(f"{preset.name} [{item.source_type}]: downloaded {os.path.basename(item.file_path)}")

    # ---------- actions ----------

    def save(self):
        self._sync_fields_into_selected()
        save_presets(PRESETS_PATH, self.presets)
        save_settings(SETTINGS_PATH, self._collect_settings())
        self._log("Saved presets and settings.")
        reload_live = getattr(self._live_state, "ae_reload", None)
        if self._engine_started and reload_live:
            try:
                reload_live()          # running popups engine: use the new values now, no restart needed
            except Exception as ex:
                self._log(f"Saved, but the running popups could not use the new values ({ex}). Restart to apply.", "warning")
        self._notify("Saved.", 4)

    def save_and_exit(self):
        self.save()
        self._on_close()

    def run_now(self):
        if self.scheduler and self.scheduler.workers:
            self._log("Scraper is already running.", "warning")
            return
        selected = self._find_preset(self.selected_name.get())
        if not selected:
            self._maybe_first_run()
            if not self.presets:
                messagebox.showinfo("Autoedgeware", "Make a preset first (Main tab > Create).", parent=self)
            return
        selected.enabled = True
        self.save()   # lock in whatever is configured right now

        settings = self._collect_settings()
        self.scheduler = ScrapeScheduler(MEDIA_ROOT, on_new_media=self._on_new_media_gui, on_log=self._log,
                                         caps=media_caps.caps_from_settings(settings),
                                         min_image_px=min_size.from_settings(settings),
                                         video_rules=video_tidy.rules_from_settings(settings))
        self.scheduler.start([selected], SOURCE_REGISTRY, source_kwargs=self._source_kwargs(),
                             run_once=settings.get("auto_stop_after_pass", True),
                             on_finished=self._on_scheduler_finished)
        self._log(f"Running preset '{selected.name}'.")
        self._stopped = False
        self._cancel_pause()
        self._refresh_buttons()

        media_roots = [Path(MEDIA_ROOT) / selected.name]
        engine_control.resume_popups(self._live_state)   # undo an earlier Stop
        if not self._engine_started:
            try:
                import run_engine
                pack, state, live_settings = run_engine.build_and_start(
                    self, [selected], embedded=True,
                    on_stop=lambda: self.after(0, self._on_external_panic))
                self._live_pack = pack
                self._live_state = state
                self._live_settings = live_settings
                self._engine_started = True
                self._log(f"Popup engine started, showing only '{selected.name}'.")
            except Exception as ex:
                self._log(f"Could not start the popup engine: {ex}", "error")
        elif self._live_pack is not None:
            self._live_pack.media_roots = media_roots
            self._log(f"Popup engine now showing only '{selected.name}'.")
        self._refresh_buttons()

    def _on_hypno_toggle(self):
        """Switch Hypno mode on or off right away when the engine is already running."""
        hypno = getattr(self._live_state, "ae_hypno", None)
        if hypno is not None:
            hypno.set_enabled(self.hypno_var.get())

    def _on_hero_toggle(self):
        """Switch Hero mode on or off right away when the engine is already running (it reads the saved settings)."""
        hero = getattr(self._live_state, "ae_hero", None)
        if hero is not None:
            self.save()
            hero.set_enabled(self.hero_var.get())

    def _on_scheduler_finished(self):
        self.after(0, self._on_scheduler_finished_ui)

    def _on_scheduler_finished_ui(self):
        self.scheduler = None
        self._log("Finished - the preset completed one pass and auto-stopped downloading.")
        self._refresh_buttons()

    def _on_external_panic(self):
        """Tray Panic, panic hotkey or a popup's panic key: same as pressing Stop, window stays open."""
        self._log("Panic pressed.")
        self.stop_now()

    def _cancel_pause(self):
        if self._pause_job is not None:
            try:
                self.after_cancel(self._pause_job)
            except Exception:
                pass
        self._pause_job = None
        self._pause_until = None

    def pause_now(self):
        if not (self._engine_started and not self._stopped and self._live_state is not None):
            return
        if self._pause_until:
            self._end_pause()
            return
        closed = engine_control.stop_popups(self._live_state)
        self._pause_until = time.time() + PAUSE_SECONDS
        self._pause_job = self.after(PAUSE_SECONDS * 1000, self._end_pause)
        self._log(f"Paused for {PAUSE_SECONDS // 60} minutes. Closed {closed} open popup(s); downloading continues.")
        self._notice = ("", 0.0)
        self._refresh_buttons()

    def _end_pause(self):
        self._cancel_pause()
        if not self._stopped:
            engine_control.resume_popups(self._live_state)
            self._log("Pause over - popups are back.")
        self._notice = ("", 0.0)
        self._refresh_buttons()

    def stop_now(self):
        if not self.scheduler and not self._engine_started:
            return
        self._cancel_pause()
        if self.scheduler:
            self.scheduler.stop_all()
            self.scheduler = None
        if self._engine_started and self._live_state is not None:
            # NOT Edgeware's panic(): it destroys the main window, which here is this window.
            closed = engine_control.stop_popups(self._live_state)
            self._log(f"Stopped. Closed {closed} open popup(s); no new popups until you press Run.")
        else:
            self._log("Stopped.")
        self._stopped = True
        self._notice = ("", 0.0)
        self.status_var.set("Stopped.")
        self._refresh_buttons()

    def save_exit_and_run(self):
        self.save()
        start_engine(RUN_ENGINE_PY, BASE_DIR, preset_name=self.selected_name.get() or None)
        self._on_close()

    # ---------- updates ----------

    def _start_update_check(self):
        local = theme.read_version(BASE_DIR)

        def work():
            self._update_found = updater.check(local) or ""
        Thread(target=work, daemon=True).start()
        self.after(1000, self._poll_update)

    def _poll_update(self):
        self._update_polls += 1
        if self._update_found is None:
            if self._update_polls < 20:
                self.after(1000, self._poll_update)
            return
        if self._update_found:
            version = self._update_found
            self.update_btn = self._btn(self._header, f"Update to v{version.lstrip('vV')}", self._do_update, primary=True)
            self.update_btn.pack(side="right")
            self._log(f"A newer version is available: v{version.lstrip('vV')}.")

    def _do_update(self):
        """One click: save, download, close; the helper copies the files and reopens run.bat."""
        self.update_btn.configure(state="disabled")
        self._notify("Downloading the update...", 600)
        self.save()
        result = {}

        def work():
            try:
                result["ok"] = updater.download_and_prepare()
            except Exception as ex:
                result["err"] = str(ex)
        Thread(target=work, daemon=True).start()

        def poll():
            if "ok" in result:
                root, work_dir = result["ok"]
                try:
                    updater.launch_helper(root, os.path.dirname(BASE_DIR), work_dir)
                except Exception as ex:
                    self._notify(f"Update failed: {ex}", 30)
                    self.update_btn.configure(state="normal")
                    return
                self._on_close()
            elif "err" in result:
                self._log(f"Update failed: {result['err']}", "error")
                self._notify("Update failed (see the Log tab). Nothing was changed.", 30)
                self.update_btn.configure(state="normal")
            else:
                self.after(500, poll)
        self.after(500, poll)

    def _on_close(self):
        if self.scheduler:
            self.scheduler.stop_all()
        engine_control.restore_wallpaper(self._live_state)   # put the user's own wallpaper back
        engine_control.stop_hypno(self._live_state, final=True)
        engine_control.stop_hero(self._live_state, final=True)
        if self._live_state is not None:
            engine_control.shutdown(self._live_state)       # tray icon, video players, hotkey helper; then exit
        self.destroy()


if __name__ == "__main__":
    AutoedgewareGUI().mainloop()
