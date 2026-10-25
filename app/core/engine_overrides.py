"""Engine settings that are always forced, whatever intensity preset is applied.
Kept here (not inside run_engine.py) so they can be tested without starting the engine."""


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
    if ae_settings.get("popup_timeout_enabled"):     # the Options checkbox decides, not the preset
        current["timeoutPopups"] = 1
        current["popupTimeout"] = ae_settings.get("popup_timeout_seconds", 10)
    else:
        current["timeoutPopups"] = 0
    return current
