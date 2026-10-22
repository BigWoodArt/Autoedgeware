"""The 'Custom' intensity: every popup setting that actually does something here, checked and turned
into the raw Edgeware keys. No Tk, so it can be tested.

Not offered on purpose (they are fixed by Autoedgeware, see core/engine_overrides.py): volumes, max
audio, and auto-close (that one lives in Settings > General)."""

# key, label, kind, minimum, maximum  (kind: 'sec' = seconds shown, milliseconds stored)
FIELDS = [
    ("delay", "Time between popups (seconds)", "sec", 0.6, 60),
    ("popupMod", "Image chance (%)", "int", 0, 100),
    ("vidMod", "Video chance (%)", "int", 0, 100),
    ("audioMod", "Audio chance (%)", "int", 0, 100),
    ("maxVideos", "Most videos at once", "int", 1, 10),
    ("singleMode", "One popup at a time", "bool", 0, 1),
    ("movingChance", "Moving popup chance (%)", "int", 0, 100),
    ("movingSpeed", "Moving popup speed (1 slow - 15 fast)", "int", 1, 15),
    ("corruptionMode", "Speed up over time", "bool", 0, 1),
    ("corruptionTime", "Speed up every (seconds)", "int", 5, 3600),
    ("speedup_percent", "Each speed-up shortens the delay by (%)", "int", 5, 50),
]

DEFAULTS = {
    "delay": 3000, "popupMod": 60, "vidMod": 10, "audioMod": 50, "maxVideos": 2,
    "singleMode": 1, "movingChance": 0, "movingSpeed": 3, "corruptionMode": 1, "corruptionTime": 90, "speedup_percent": 20,
}


def to_display(key, value):
    kind = next(f[2] for f in FIELDS if f[0] == key)
    if kind == "sec":
        return f"{value / 1000:g}"
    if kind == "bool":
        return bool(value)
    return str(value)


def parse(raw):
    """raw: {key: text-or-bool as typed}. Returns (values, errors). values hold stored units."""
    values, errors = {}, []
    for key, label, kind, lo, hi in FIELDS:
        text = raw.get(key, DEFAULTS[key] if kind != "sec" else DEFAULTS[key] / 1000)
        if kind == "bool":
            values[key] = 1 if text else 0
            continue
        try:
            number = float(str(text).strip()) if kind == "sec" else int(str(text).strip())
        except ValueError:
            errors.append(f"{label}: type a number.")
            continue
        if not lo <= number <= hi:
            errors.append(f"{label}: use a number from {lo:g} to {hi:g}.")
            continue
        values[key] = round(number * 1000) if kind == "sec" else number
    return values, errors


def build_cfg(base_cfg, values):
    """Raw Edgeware settings: the base bundle with the custom values on top. 'speedup_percent' is ours."""
    cfg = dict(base_cfg)
    cfg.update({k: v for k, v in values.items() if k != "speedup_percent"})
    cfg["corruptionTrigger"] = "Timed"
    return cfg
