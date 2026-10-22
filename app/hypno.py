"""Hypno mode: a faint black-and-white spiral over the screen plus binaural beats (core/hypno_logic.py has the
rules, core/hypno_assets.py makes the files).

- The spiral is a click-through, fullscreen, looping picture at most 20% opaque. It does not use a video slot
  and is kept out of state.popups, so other popups still place themselves normally.
- The beats play on their own player, not in state.audio_players, so they never count against the number
  of sounds playing.
- How strong it is follows the image popup rate. No image popups (hibernating, Stop, Pause) = nothing shown.
- Every so often the spiral and beats are swapped for a new random pair.

Import only after edgeware_core/src is on sys.path (see run_engine.py)."""
import os
import subprocess
import sys
import threading
import traceback
import time

import mpv
import utils
from features.popup import Popup
from features.video_player import VideoPlayer
from features.video_popup import VideoPopup
from os_utils import close_mpv, set_clickthrough

from core import engine_control, file_log, hypno_assets, hypno_logic

CONFIG = {"beat_volume": 20}      # percent, 0-100; set from Settings by configure()
FADE_IN_MS = 6000


def configure(beat_volume=20):
    CONFIG["beat_volume"] = max(0, min(100, int(beat_volume)))


WATCH_MS = 1000


class HypnoSpiral(VideoPopup):
    """Edgeware's video popup, minus everything that makes a popup a popup (timeouts, buttons, moving, a video slot)."""

    def __init__(self, root, settings, pack, state, media, speed, opacity):
        self._ae_speed, self._ae_opacity, self._ae_closed = speed, opacity, False
        super().__init__(root, settings, pack, state, media=media)

    def should_init(self, settings, state) -> bool:
        return bool(self.media)                     # no video slot used

    def _probe(self) -> None:
        # We made the picture ourselves, so no ffprobe: its size is known.
        w, h = hypno_assets.LEVELS[hypno_assets.tier_of(self.media)]
        self._pending_root.after(0, lambda: self._finish_init({"width": w, "height": h}))

    def _finish_init(self, properties: dict) -> None:
        if self._ae_closed:                         # closed while the window was still being set up
            return
        Popup.__init__(self, self._pending_root, self._pending_settings, self._pending_pack, self._pending_state, None)
        self.state.popups.remove(self)              # keep out of the lists other popups use to find free space
        self.state.popup_number -= 1
        self.attributes("-alpha", self._ae_opacity)

        monitor = utils.random_monitor(self.settings)
        self.width, self.height, self.x, self.y = monitor.width, monitor.height, monitor.x, monitor.y
        self.geometry(f"{self.width}x{self.height}+{self.x}+{self.y}")

        self.player = VideoPlayer(self, self.settings, self.width, self.height)
        self.player.properties["volume"] = 0
        self.player.properties["speed"] = self._ae_speed
        self.player.play(self.media)
        for key in ("input-default-bindings", "input-vo-keyboard", "input-cursor"):
            try:
                self.player.mpv[key] = "no"             # the spiral never reacts to the mouse or keys
            except Exception:
                pass
        self.after(WATCH_MS, self._watch)

        self.wait_visibility()
        set_clickthrough(self)
        self.after(400, self._lift_others)

    def _watch(self):
        """Once a second: if the picture stopped or paused (a click elsewhere must never do that), start it again."""
        if self._ae_closed:
            return
        try:
            mp = getattr(self.player, "mpv", None)
            if mp is not None:
                if mp.idle_active:
                    mp.play(self.media)
                    self._note("hypno: spiral picture had stopped; started again")
                elif mp.pause:
                    mp.pause = False
                    self._note("hypno: spiral picture had paused; resumed")
        except Exception:
            pass
        try:
            if any(getattr(p, "_ae_full", False) for p in list(self.state.popups)):
                self.attributes("-topmost", False)      # a fullscreen video keeps claiming the top: take it back
                self.attributes("-topmost", True)
                self.lift()
                self._lift_others()
        except Exception:
            pass
        try:
            self.after(WATCH_MS, self._watch)
        except Exception:
            pass

    def _note(self, text):
        try:
            file_log.write(self.state.ae_hypno.base, text, "info")
        except Exception:
            pass

    def _lift_others(self):
        # Normal popups sit over the spiral. A fullscreen video sits under it.
        try:
            for popup in list(self.state.popups):
                if not getattr(popup, "_ae_full", False):
                    popup.lift()
        except Exception:
            pass

    def set_opacity(self, value):
        try:
            self.attributes("-alpha", value)
        except Exception:
            pass

    def close(self) -> None:
        if self._ae_closed:
            return
        self._ae_closed = True
        self._note("hypno: spiral closed (" + "/".join(f.name for f in traceback.extract_stack(limit=4)[:-1]) + ")")
        try:
            self.player.close()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass


class HypnoController:
    def __init__(self, root, settings, pack, state, base_dir):
        self.root, self.settings, self.pack, self.state = root, settings, pack, state
        self.base = base_dir                                      # where the log lives
        self.folder = os.path.join(base_dir, "hypno_assets")      # the generated spirals and beats
        self.spiral = None
        self.beat_file = None
        self.beat_player = None
        self.next_change = 0.0
        self.last_spiral = self.last_beat = None
        self.enabled = False
        self.level_source = None       # Hero mode sets this: a function giving the strength (0-1) to use
        self.tier = "m"          # the sharpest spiral size worth drawing for these screens
        self._ready = False
        self._making = False
        self._stopped = False

    # ---- life cycle ----
    def start(self):
        """Begin ticking (it only does anything while enabled)."""
        try:
            self.tier = hypno_assets.pick_tier([m.width for m in utils.get_monitors()])
        except Exception:
            self.tier = "m"
        self.root.after(hypno_logic.TICK_MS, self._tick)

    def set_enabled(self, flag):
        self.enabled = bool(flag)
        if self.enabled and not self._ready and not self._making:
            self._making = True
            threading.Thread(target=self._make_files, daemon=True).start()
        if not self.enabled:
            self.teardown()

    def files_ready(self):
        """True as soon as one spiral exists: the rest keep being drawn while it already plays."""
        try:
            return bool(hypno_assets.available(self.folder, self.tier)[0])
        except Exception:
            return False

    def _make_files(self):
        log = lambda m: file_log.write(self.base, m, "info")
        try:
            hypno_assets.ensure_first(self.folder, log)        # beats + one small spiral: playable within a second or two
            log("hypno: first spiral ready; drawing the sharper sizes in the background")
            if not self._generate_in_background():
                hypno_assets.ensure_assets(self.folder, log, self.tier)     # fallback: same work, in this process
            log(f"hypno: pictures and sounds ready in {self.folder} ({self.tier} size)")
            self._ready = True
        except Exception as ex:
            file_log.write(self.base, f"hypno: could not make the spiral and beat files: {ex}", "error")
        self._making = False

    def _generate_in_background(self):
        """Draw the files in a separate low-priority process: it can take a minute, and doing it here made
        the whole program stutter. True when that worked."""
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "core", "hypno_gen.py")
        flags = 0x00004000 if sys.platform.startswith("win") else 0          # BELOW_NORMAL_PRIORITY_CLASS
        try:
            done = subprocess.run([sys.executable, script, self.folder, self.tier], creationflags=flags,
                                  timeout=900, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            if done.returncode != 0:
                file_log.write(self.base, "hypno: the background drawing failed, drawing here instead: "
                                          + (done.stderr or b"")[-300:].decode("utf-8", "replace"), "warning")
            return done.returncode == 0
        except Exception as ex:
            file_log.write(self.base, f"hypno: could not start the background drawing ({ex})", "warning")
            return False

    def shutdown(self):
        """Program is ending: stop for good."""
        self.enabled = False
        self._stopped = True
        self.teardown()

    # ---- ticking ----
    def _tick(self):
        if self._stopped:
            return
        try:
            self._step()
        except Exception as ex:
            file_log.write(self.base, f"hypno: tick failed: {ex}", "error")
        self.root.after(hypno_logic.TICK_MS, self._tick)

    def _step(self):
        rate = hypno_logic.image_rate(self.settings.delay, self.settings.image_chance)
        ready = self._ready or self.files_ready()
        lvl = hypno_logic.level(rate) if ready else 0.0
        if self.level_source is not None and ready:
            try:
                lvl = max(0.05, float(self.level_source()))     # Hero mode steers it (never fully off)
            except Exception:
                pass
        action = hypno_logic.decide(self.enabled, engine_control.is_paused(), lvl, time.time(),
                                    self.next_change, self.spiral is not None)
        if action == "off":
            self.teardown()
        elif action == "new":
            self._begin(lvl)
        elif self.spiral is not None:
            self.spiral.set_opacity(hypno_logic.opacity(lvl))
            self.keep_alive()

    def apply_level(self, lvl):
        """Set the spiral's opacity now (Hero mode fades it up and down between the 5 s ticks)."""
        spiral = self.spiral
        if spiral is not None:
            spiral.set_opacity(hypno_logic.opacity(max(0.05, lvl)))

    def keep_alive(self):
        """A fullscreen video can bury the spiral and stall the beats: put both back."""
        spiral = self.spiral
        if spiral is not None:
            try:
                if not spiral.winfo_exists():
                    self.spiral = None
                    self.next_change = 0          # next tick starts a fresh one
                else:
                    spiral.attributes("-topmost", False)
                    spiral.attributes("-topmost", True)
                    spiral.lift()
                    spiral._lift_others()
            except Exception:
                pass
        player = self.beat_player
        if player is not None:
            try:
                if player.idle_active:             # mpv ended or was reset: start the same file again
                    player.play(self.beat_file)
                    file_log.write(self.base, "hypno: beats resumed", "info")
            except Exception:
                pass

    def _begin(self, lvl):
        self.teardown()
        spirals, beats = hypno_assets.available(self.folder, self.tier)
        if not spirals:
            return
        name = hypno_logic.pick(spirals, self.last_spiral)
        beat = hypno_logic.pick(beats, self.last_beat) if beats else None
        self.last_spiral, self.last_beat = name, beat
        self.spiral = HypnoSpiral(self.root, self.settings, self.pack, self.state,
                                  hypno_assets.best_spiral(self.folder, name, self.tier),
                                  hypno_logic.speed(lvl), hypno_logic.opacity(lvl))
        if beat:
            self._play_beat(hypno_assets.beat_path(self.folder, beat))
        self.next_change = hypno_logic.next_change_time(time.time())
        file_log.write(self.base, f"hypno: spiral {name}, beats {beat} (strength {lvl:.2f}, "
                                    f"opacity {hypno_logic.opacity(lvl):.2f})", "info")

    def _play_beat(self, path):
        # mpv (the same player the videos use) loops a file reliably; pyglet stopped partway through.
        try:
            player = mpv.MPV(vid="no", loop_file="inf", volume=0)
            player.play(path)
            self.beat_player, self.beat_file = player, path
            target = CONFIG["beat_volume"]
            steps = max(1, FADE_IN_MS // 100)

            def fade(i=1):
                if self.beat_player is not player:
                    return
                try:
                    player.volume = target * min(1.0, i / steps)
                except Exception:
                    return
                if i < steps:
                    self.root.after(100, lambda: fade(i + 1))
            fade()
        except Exception as ex:
            file_log.write(self.base, f"hypno: could not play the beats: {ex}", "error")

    # ---- tearing down ----
    def teardown(self):
        spiral, self.spiral = self.spiral, None
        if spiral is not None:
            spiral.close()
        player, self.beat_player = self.beat_player, None
        if player is not None:
            try:
                close_mpv(player)
            except Exception:
                pass
        self.next_change = 0.0
