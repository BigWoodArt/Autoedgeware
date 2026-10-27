"""Engine settings that are always forced, whatever intensity preset is applied.
Kept here (not inside run_engine.py) so they can be tested without starting the engine."""

POPUP_BEHAVIOR = {"timer_only": False, "rmb_drag": False}
_installed = False


def _number(settings, key, default, lo, hi):
    try:
        return max(lo, min(hi, int(float(settings.get(key, default)))))
    except (TypeError, ValueError):
        return default


def effective_cfg(ae_settings, presets):
    """The intensity values to run with. A built-in preset is always taken fresh from the program (a bundle saved
    by an older version kept its old values, e.g. moving popups at 5%). Anything without a moving-popup value
    gets 0%, so a stale value in the engine's own config file can never make popups move."""
    name = ae_settings.get("edgeware_cfg_name")
    cfg = next((dict(bundle) for preset_name, bundle in presets if preset_name == name), None)
    if cfg is None:
        cfg = dict(ae_settings.get("edgeware_cfg") or {})
    cfg.setdefault("movingChance", 0)
    cfg.setdefault("movingSpeed", 3)
    return cfg


def apply_forced(current, ae_settings):
    current["booru_download"] = 0      # our scrapers already feed the engine; its own booru fetch is redundant
    current["buttonless"] = True       # popups close on click/timeout, no button needed
    # Sound comes from Settings > Session (defaults: one audio track at a time, which keeps stacked audio from
    # hogging the single-popup slot; audio at 50%, a video's own sound quieter at 20%).
    current["maxAudio"] = _number(ae_settings, "max_audio", 1, 1, 10)
    current["audioVolume"] = _number(ae_settings, "audio_volume", 50, 0, 100)
    current["videoVolume"] = _number(ae_settings, "video_volume", 20, 0, 100)
    # Mitosis mode switches the timed image/video popups OFF and relies on one popup at engine start.
    # With an empty folder (any new preset) that start-up popup finds nothing, and no popup ever
    # appears. The maximum preset used to turn it on, so it showed nothing at all.
    disabled = ae_settings.get("disabled_monitors") or []
    current["disabledMonitors"] = [str(n) for n in disabled] if isinstance(disabled, (list, tuple)) else []
    current["mitosisMode"] = 0
    current["mitosisStrength"] = 0
    timeout_on = bool(ae_settings.get("popup_timeout_enabled"))  # the Options checkbox decides, not the preset
    if timeout_on:
        current["timeoutPopups"] = 1
        current["popupTimeout"] = ae_settings.get("popup_timeout_seconds", 10)
    else:
        current["timeoutPopups"] = 0
    POPUP_BEHAVIOR["timer_only"] = bool(timeout_on and ae_settings.get("popup_close_by_timer_only"))
    POPUP_BEHAVIOR["rmb_drag"] = bool(ae_settings.get("popup_drag_right_button"))
    return current


def click_close_blocked(popup):
    """True when a click must not close this popup: timer-only is on, and it is not a fullscreen video."""
    return bool(POPUP_BEHAVIOR["timer_only"] and not getattr(popup, "_ae_full", False))


def install_popup_behavior():
    """Wraps Edgeware Popup once: skip click-to-close when timer-only, right-drag when that option is on."""
    global _installed
    if _installed:
        return
    _installed = True
    from features.popup import Popup

    orig_try_button = Popup.try_button
    orig_init_finish = Popup.init_finish

    def try_button(self):
        if click_close_blocked(self):
            return
        orig_try_button(self)

    def init_finish(self):
        orig_init_finish(self)
        if not POPUP_BEHAVIOR["rmb_drag"] or getattr(self, "_ae_full", False):
            return

        def press(event):
            self._ae_drag = (event.x_root - self.winfo_x(), event.y_root - self.winfo_y())

        def motion(event):
            start = getattr(self, "_ae_drag", None)
            if not start:
                return
            x, y = event.x_root - start[0], event.y_root - start[1]
            self.x, self.y = x, y
            self.geometry(f"{self.width}x{self.height}+{x}+{y}")

        for widget in (self, *self.winfo_children()):
            widget.bind("<ButtonPress-3>", press, add="+")
            widget.bind("<B3-Motion>", motion, add="+")

    Popup.try_button = try_button
    Popup.init_finish = init_finish
