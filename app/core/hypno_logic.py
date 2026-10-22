"""Hypno mode rules, with no Tk, mpv or sound code so they can be tested on their own.

Hypno mode = a faint black-and-white spiral over the screen plus binaural beats. How strong it is follows how
fast image popups are coming: more popups per minute -> faster, more visible spiral (never above 25% opacity)."""
import math
import random

MAX_OPACITY = 0.20
MIN_OPACITY = 0.05
MIN_SPEED, MAX_SPEED = 0.5, 2.0          # mpv playback speed of the looping spiral
FULL_RATE = 40.0                         # image popups per minute that count as 'full strength'
CHANGE_MIN_S, CHANGE_MAX_S = 240, 600    # the spiral and beats are swapped for a new pair this often
TICK_MS = 5000


def image_rate(delay_ms, image_chance_percent):
    """Image popups per minute. delay_ms = time between popup rolls; chance = % of rolls that show an image."""
    if not delay_ms or delay_ms <= 0 or image_chance_percent <= 0:
        return 0.0
    return 60000.0 / delay_ms * min(100, image_chance_percent) / 100.0


def level(rate):
    """0..1 strength from the popup rate (log scale: 1/min is barely there, 40/min is full). 0 = off."""
    if rate < 0.5:
        return 0.0
    return max(0.05, min(1.0, math.log(rate, 2) / math.log(FULL_RATE, 2)))


def opacity(lvl):
    return round(MIN_OPACITY + (MAX_OPACITY - MIN_OPACITY) * max(0.0, min(1.0, lvl)), 3)


def speed(lvl):
    return round(MIN_SPEED + (MAX_SPEED - MIN_SPEED) * max(0.0, min(1.0, lvl)), 2)


def decide(enabled, paused, lvl, now, next_change, have_spiral):
    """What the controller does on a tick: 'off' (tear down), 'new' (start a fresh spiral + beats) or 'update'."""
    if not enabled or paused or lvl <= 0:
        return "off"
    if not have_spiral or now >= next_change:
        return "new"
    return "update"


def next_change_time(now, rng=random):
    return now + rng.uniform(CHANGE_MIN_S, CHANGE_MAX_S)


def pick(names, last=None, rng=random):
    """Random choice that avoids repeating the previous one when there is a choice."""
    options = [n for n in names if n != last] or list(names)
    return rng.choice(options) if options else None
