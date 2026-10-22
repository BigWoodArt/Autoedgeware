"""Hero mode: a beat bar along the bottom of the screen (rules in core/hero_logic.py).

- The bar is a click-through, always-on-top strip. Circles slide in from the right and meet a larger ring in the
  middle. The ring flashes green and a click plays. Nothing is recorded: the person just follows along.
- One clock drives the circles, the clicks and the popups. Popup delay follows the tempo, a popup is rolled on a beat,
  and during 'Hold' no new popups start (ones already open stay).
- Hypno mode (if on) takes its strength from the phase, so the spiral fades up and down with the beat.

Import only after edgeware_core/src is on sys.path (see run_engine.py)."""
import os
import time
import tkinter as tk

import utils
from os_utils import set_borderless, set_clickthrough

from core import engine_control, file_log, hero_assets, hero_logic

try:
    import winsound
except ImportError:                      # not Windows: the bar still runs, just silent
    winsound = None

BG = "#0b0b12"
TEXT = "#ffd6f2"
NEXT_TEXT = "#7d7d99"                  # the faint "Next:" line
CIRCLE = "#ff7ac8"
CIRCLE_NEAR = "#ffffff"
RING = "#d8d8e8"
GREEN = "#2bff7a"
GREEN_FILL = "#14803f"
TRAVEL_S = 2.0                           # how long a circle takes to cross from the edge to the ring
FRAME_MS = 30
BAR_H = 150
BOTTOM_MARGIN = 56                       # keeps the strip above the taskbar
FLASH_S = 0.16
POPUP_LEAD_S = 0.10                      # a popup takes about this long to appear after it is rolled


def _blend(a, b, f):
    f = max(0.0, min(1.0, f))
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * f) for x, y in zip(ca, cb))


class HeroBar(tk.Toplevel):
    def __init__(self, root, monitor, show_text):
        super().__init__(root)
        self.configure(bg=BG)
        set_borderless(self)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.85)
        self.w, self.h = monitor.width, BAR_H
        self.geometry(f"{self.w}x{self.h}+{monitor.x}+{monitor.y + monitor.height - BAR_H - BOTTOM_MARGIN}")
        self.canvas = tk.Canvas(self, width=self.w, height=self.h, bg=BG, highlightthickness=0)
        self.canvas.pack()
        self.cx, self.cy = self.w // 2, 100
        self.px_per_s = (self.w - self.cx) / TRAVEL_S
        self.canvas.create_line(0, self.cy, self.w, self.cy, fill="#3a3a52", width=4)
        self.ring = self.canvas.create_oval(self.cx - 36, self.cy - 36, self.cx + 36, self.cy + 36,
                                            outline=RING, width=3)
        self.show_text = show_text
        self.text_item = self.canvas.create_text(self.w // 2, 30, text="", fill=BG,
                                                 font=("Segoe UI", 22, "bold"))
        self.text, self.text_since = "", 0.0
        self.next_item = self.canvas.create_text(24, 68, text="", fill=NEXT_TEXT, anchor="w",
                                                 font=("Segoe UI", 13))
        self.next_text = ""
        self.circles = []                 # [hit time on the session clock, canvas item]
        self.flash_until = 0.0
        self._closed = False
        self.update_idletasks()
        self.wait_visibility()
        set_clickthrough(self)

    def set_text(self, text, now):
        if self.show_text and text != self.text:
            self.text, self.text_since = text, now
            self.canvas.itemconfigure(self.text_item, text=text)

    def set_next(self, text):
        if self.show_text and text != self.next_text:
            self.next_text = text
            self.canvas.itemconfigure(self.next_item, text=text)

    def add_circle(self, t_hit):
        item = self.canvas.create_oval(self.w, self.cy - 16, self.w + 32, self.cy + 16, fill=CIRCLE, outline="")
        self.circles.append([t_hit, item])

    def flash(self, until):
        self.flash_until = until

    def draw(self, now, hold):
        if self._closed:
            return
        keep = []
        for t_hit, item in self.circles:
            if t_hit < now - 0.06:
                self.canvas.delete(item)
                continue
            x = self.cx + (t_hit - now) * self.px_per_s
            near = abs(t_hit - now) < 0.12
            r = 20 if near else 16
            self.canvas.coords(item, x - r, self.cy - r, x + r, self.cy + r)
            self.canvas.itemconfigure(item, fill=CIRCLE_NEAR if near else CIRCLE)
            keep.append([t_hit, item])
        self.circles = keep
        lit = hold or now < self.flash_until
        self.canvas.itemconfigure(self.ring, outline=GREEN if lit else RING, width=8 if lit else 3,
                                  fill=GREEN_FILL if now < self.flash_until else "")
        if self.show_text and self.text:
            self.canvas.itemconfigure(self.text_item, fill=_blend(BG, TEXT, (now - self.text_since) / 0.6))

    def lift_up(self):
        """Back above everything, fullscreen video included (Win32 call; Tk fallback)."""
        try:
            self.attributes("-topmost", False)
            self.attributes("-topmost", True)
            self.lift()
        except tk.TclError:
            return
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id()) or self.winfo_id()
            # HWND_TOPMOST=-1; flags: NOSIZE|NOMOVE|NOACTIVATE|SHOWWINDOW
            ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010 | 0x0040)
        except Exception:
            pass

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self.destroy()
        except tk.TclError:
            pass


class HeroController:
    def __init__(self, root, settings, pack, state, base_dir, settings_fn):
        """settings_fn() -> Autoedgeware's saved settings dict (read each time Hero mode starts)."""
        self.root, self.settings, self.pack, self.state = root, settings, pack, state
        self.base = base_dir
        self.settings_fn = settings_fn
        self.enabled = False
        self.active = False
        self.bar = None
        self.seq = None
        self.t0 = 0.0
        self.gen = 0                       # bumps on every start/stop so old scheduled clicks do nothing
        self.level = 0.3
        self.upcoming = []                 # session-clock times of beats that should bring a popup
        self.base_delay = None
        self.pace_source = None          # set by the engine: () -> (delay_ms, interval_s, speedup_pct, corruption_on)
        self.click_path = None
        self._phase_idx = None
        self._delay_set = None
        self._last_lift = self._last_hypno = 0.0
        self._warned = False
        self._stopped = False
        self._fails = 0

    # ---- life cycle ----
    def start(self):
        self.root.after(FRAME_MS, self._frame)

    def set_enabled(self, flag):
        self.enabled = bool(flag)
        if not self.enabled:
            self.teardown()

    def teardown(self):
        """Stop / Panic / switched off: take the bar down and give the popup settings back."""
        self._deactivate()

    def shutdown(self):
        self.enabled = False
        self._stopped = True
        self._deactivate()

    # ---- the frame loop ----
    def _frame(self):
        if self._stopped:
            return
        try:
            self._step()
        except Exception as ex:
            file_log.write(self.base, f"hero: frame failed: {ex}", "error")
            self._deactivate()
            self._fails += 1
            if self._fails >= 3:                 # do not loop on an error forever
                self.enabled = False
                file_log.write(self.base, "hero: switched off after repeated errors", "error")
        self.root.after(FRAME_MS if self.active else 500, self._frame)

    def _step(self):
        wanted = self.enabled and not engine_control.is_paused()
        if wanted and not self.active:
            self._activate()
        elif not wanted and self.active:
            self._deactivate()
        if not self.active:
            return
        now = time.perf_counter() - self.t0
        for ev in self.seq.take_until(now + TRAVEL_S + 0.3):
            self.bar.add_circle(ev.time)
            self.root.after(max(0, int((ev.time - now) * 1000)), lambda e=ev, g=self.gen: self._hit(e, g))
            if ev.popup:
                self.upcoming.append(ev.time)
        idx, phase, offset = self.seq.phase_at(now)
        start_next, next_phase = self.seq.next_phase(now)
        self.bar.set_next(f"Next: {next_phase.text}  ({max(0, int(start_next - now + 0.5))}s)")
        if idx != self._phase_idx:
            self._phase_idx = idx
            engine_control.set_hold(phase.hold)
            self.bar.set_text(phase.text, now)
            file_log.write(self.base, f"hero: {phase.name} ({phase.seconds:.0f}s)", "info")
        delay = hero_logic.popup_delay_ms(phase, phase.bpm_at(offset))
        if delay != self._delay_set:
            self._delay_set = delay
            self.settings.delay = delay             # Hypno and the log read the popup pace from here
        target = phase.level_at(offset)
        step = FRAME_MS / 1000.0 * 0.35             # the spiral fades at most this much per second
        self.level += max(-step, min(step, target - self.level))
        if now - self._last_hypno > 0.4:
            self._last_hypno = now
            hypno = getattr(self.state, "ae_hypno", None)
            if hypno is not None:
                hypno.apply_level(self.level)
        if now - self._last_lift > 0.25:
            self._last_lift = now
            self.bar.lift_up()
        self.bar.draw(now, phase.hold)

    # ---- start / stop ----
    def _activate(self):
        cfg, show_text, volume = hero_logic.from_settings(self.settings_fn() or {})
        self.seq = hero_logic.Sequencer(cfg)           # the tempo climbs round by round (its own ramp)
        try:
            self.click_path = hero_assets.make_click(os.path.join(self.base, "hero_assets", "click.wav"), volume)
        except Exception as ex:
            self.click_path = None
            file_log.write(self.base, f"hero: could not make the click sound: {ex}", "error")
        monitor = utils.random_monitor(self.settings)
        self.bar = HeroBar(self.root, monitor, show_text)
        self.gen += 1
        self.t0 = time.perf_counter()
        self.base_delay = self.settings.delay
        self.upcoming = []
        self._phase_idx = self._delay_set = None
        self.level = 0.3
        self.active = True
        hypno = getattr(self.state, "ae_hypno", None)
        if hypno is not None:
            hypno.level_source = lambda: self.level
        file_log.write(self.base, f"hero: on ({cfg['bpm_min']}-{cfg['bpm_max']} bpm, "
                                  f"round {cfg['round_s']}s, full speed after {cfg['ramp_rounds']} rounds, hold {cfg['hold_s']}s, frenzy {cfg['frenzy_pct']}%)", "info")

    def _deactivate(self):
        if not self.active and self.bar is None:
            return
        self.active = False
        self.gen += 1
        bar, self.bar = self.bar, None
        if bar is not None:
            bar.close()
        engine_control.set_hold(False)
        if self.base_delay is not None:
            self.settings.delay = self.base_delay
            self.base_delay = None
        self.upcoming = []
        hypno = getattr(self.state, "ae_hypno", None)
        if hypno is not None:
            hypno.level_source = None
        file_log.write(self.base, "hero: off", "info")

    # ---- the beat ----
    def _hit(self, event, gen):
        if gen != self.gen or not self.active or self.bar is None:
            return
        now = time.perf_counter() - self.t0
        self.bar.flash(now + FLASH_S)
        if winsound is not None and self.click_path:
            try:
                winsound.PlaySound(self.click_path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            except Exception as ex:
                if not self._warned:
                    self._warned = True
                    file_log.write(self.base, f"hero: click failed: {ex}", "error")

    def raise_now(self):
        """For popups that cover the bar (fullscreen video): put the bar back on top."""
        if self.active and self.bar is not None:
            self.bar.lift_up()

    def next_popup_delay_ms(self, default_ms):
        """For the engine's main loop: how long until the next popup roll, so popups land on the beat."""
        if not self.active:
            return default_ms
        now = time.perf_counter() - self.t0
        self.upcoming = [t for t in self.upcoming if t - POPUP_LEAD_S > now + 0.02]
        if self.upcoming:
            return max(30, int((self.upcoming[0] - POPUP_LEAD_S - now) * 1000))
        return min(default_ms, 700)
