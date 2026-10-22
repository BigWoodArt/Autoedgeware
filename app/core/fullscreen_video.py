"""When does a video go fullscreen? Pure rules, no Tk. Only wide videos (about 16:10 up to a bit past 2:1),
only one at a time, and only at the chance set in Settings."""
import random

RATIO_MIN, RATIO_MAX = 1.55, 2.5
MIN_HEIGHT = 1080      # a video must be taller than this (so 1080p or less stays a normal popup)


def is_wide(width, height):
    if not width or not height:
        return False
    return RATIO_MIN <= width / height <= RATIO_MAX


def play_seconds(duration, max_seconds, margin=2.0):
    """How long a fullscreen video stays up: its whole length (plus a little for mpv to start), but never more
    than max_seconds. Unknown length -> max_seconds."""
    try:
        duration = float(duration)
    except (TypeError, ValueError):
        return max_seconds
    if duration <= 0:
        return max_seconds
    return min(duration + margin, max_seconds)


def fullscreen_decision(width, height, chance_percent, already_open, rng=random, min_height=MIN_HEIGHT):
    """(yes/no, reason). The reason goes in the log so a video that stayed a popup can be explained."""
    if already_open:
        return False, "another fullscreen video is still playing"
    if chance_percent <= 0:
        return False, "chance is 0"
    if not width or not height:
        return False, "size unknown"
    if not is_wide(width, height):
        return False, f"not wide enough (ratio {width / height:.2f}, needs {RATIO_MIN}-{RATIO_MAX})"
    if int(height) <= min_height:
        return False, f"height {height} is not over {min_height}"
    if rng.random() * 100 >= chance_percent:
        return False, "chance roll missed"
    return True, "ok"


def should_fullscreen(width, height, chance_percent, already_open, rng=random, min_height=MIN_HEIGHT):
    return fullscreen_decision(width, height, chance_percent, already_open, rng, min_height)[0]
