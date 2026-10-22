"""Visual theme + intensity presets, ported directly from Edgeware's own
config.pyw ("Crimson/Violet" theme and INTENSITY_PRESETS) so Autoedgeware's
GUI looks and behaves consistently with Edgeware itself."""
import os

CRIMSON = "#DC143C"

PALETTE = {
    "bg": "#0E0A14", "panel": "#161020", "panel2": "#1D1529", "panel3": "#2A1E38",
    "border": "#2E2240", "accent": "#C51F4A", "accent2": "#7B3FE4", "accent_dark": "#8E1637",
    "white": "#F8F5FA", "muted": "#A99FB3", "dim": "#7A6E85", "disabled": "#382544",
    "danger": "#FF667F", "entry": "#0B0810", "trough": "#2B1D35",
    "field": "#2F2840",  # text-entry background: lighter than the panels so fields stand out
}

# Ported verbatim (keys/values) from config.pyw's INTENSITY_PRESETS.
INTENSITY_PRESETS = [
    ("A slight annoyance", {
        "delay": 5000, "popupMod": 50, "vidMod": 5, "audioMod": 25, "webMod": 0, "promptMod": 0,
        "timeoutPopups": 1, "popupTimeout": 15, "singleMode": 1,
        "movingChance": 0, "movingSpeed": 0, "denialChance": 0,
        "capPopChance": 0, "capPopOpacity": 50, "capPopTimer": 3,
        "notificationChance": 5, "notificationImageChance": 20,
        "maxAudio": 1, "audioVolume": 40, "maxVideos": 1, "videoVolume": 40,
        "corruptionMode": 1, "corruptionTrigger": "Timed", "corruptionTime": 120,
        "mitosisMode": 0, "mitosisStrength": 0, "hibernateMode": 0, "buttonless": True,
    }),
    ("A bit of a problem", {
        "delay": 3000, "popupMod": 60, "vidMod": 10, "audioMod": 50, "webMod": 0, "promptMod": 0,
        "timeoutPopups": 1, "popupTimeout": 10, "singleMode": 1,
        "movingChance": 0, "movingSpeed": 0, "denialChance": 0,
        "capPopChance": 10, "capPopOpacity": 60, "capPopTimer": 3,
        "notificationChance": 10, "notificationImageChance": 40,
        "maxAudio": 1, "audioVolume": 55, "maxVideos": 2, "videoVolume": 55,
        "corruptionMode": 1, "corruptionTrigger": "Timed", "corruptionTime": 90,
        "mitosisMode": 0, "mitosisStrength": 0, "hibernateMode": 0, "buttonless": True,
    }),
    ("A real addiction", {
        "delay": 1750, "popupMod": 75, "vidMod": 20, "audioMod": 75, "webMod": 10, "promptMod": 5,
        "timeoutPopups": 0, "popupTimeout": 8, "singleMode": 0,
        "movingChance": 0, "movingSpeed": 1, "denialChance": 0,
        "capPopChance": 30, "capPopOpacity": 75, "capPopTimer": 2,
        "notificationChance": 15, "notificationImageChance": 60,
        "maxAudio": 2, "audioVolume": 70, "maxVideos": 3, "videoVolume": 70,
        "corruptionMode": 1, "corruptionTrigger": "Timed", "corruptionTime": 60,
        "mitosisMode": 0, "mitosisStrength": 0, "hibernateMode": 0, "buttonless": True,
    }),
    ("Life-ending slavery", {
        "delay": 1250, "popupMod": 90, "vidMod": 40, "audioMod": 100, "webMod": 20, "promptMod": 10,
        "timeoutPopups": 0, "popupTimeout": 5, "singleMode": 0,
        "movingChance": 0, "movingSpeed": 2, "denialChance": 0,
        "capPopChance": 60, "capPopOpacity": 90, "capPopTimer": 2,
        "notificationChance": 20, "notificationImageChance": 80,
        "maxAudio": 3, "audioVolume": 90, "maxVideos": 4, "videoVolume": 90,
        "corruptionMode": 1, "corruptionTrigger": "Timed", "corruptionTime": 30,
        "mitosisMode": 0, "mitosisStrength": 0, "hibernateMode": 0, "buttonless": True,
    }),
]


def read_version(base_dir):
    path = os.path.join(base_dir, "VERSION")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return "0.0.0"
