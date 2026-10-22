"""Hero mode rules, with no Tk and no sound so they can be tested on their own.

Hero mode = a beat bar along the bottom of the screen. Circles slide along it and meet a larger ring in the middle;
the ring flashes green and a click plays. Nothing is recorded: the person follows along if they like.
One clock drives everything: the circles, the clicks and the popups (a popup lands on a beat).

A session is a repeating arc of phases:  Warm-up > Steady > Build > (Frenzy) > Hold > Ease.
A pattern is a list of one-beat tokens: 'x' = a hit on that beat, '.' = a rest, 'xx' = two quick hits, 'xxx' = three."""
import bisect
from fractions import Fraction
import math
import random
from dataclasses import dataclass, field

MAX_HITS_PER_SECOND = 7.0        # nothing faster than this, whatever the tempo says
MIN_BOUNDARY_GAP_S = 0.3        # a phase's last hit is dropped if the next phase's first hit would follow this soon
BOUNDARY_BEAT_FRACTION = 0.6     # ...or sooner than this share of a beat
MIN_POPUP_GAP_S = 0.5            # popups never come closer together than this
POPUP_DELAY_MIN_MS, POPUP_DELAY_MAX_MS = 500, 8000

# name: (tokens, instruction shown while it plays)
# Only rhythms that really feel different are here. Each is "N strokes, then a pause", or an even stream:
#   steady            even beats (a slower or faster tempo is the same rhythm, so there is no separate "half speed"
#                     or "triple speed" pattern)
#   two / three / seven   that many evenly spaced strokes, then a pause (two: 3 beats long, the others 2)
# Dropped as copies: "one slow, two quick" and "two quick, one slow" are the same loop as "three, pause", and
# "triplets" is just steady at triple tempo.
PATTERNS = {
    "steady": (["x"], "Stroke."),
    "two": (["x", "x", ".", "."], "Two strokes, then a long pause."),
    "three": (["x", "x", "x", "."], "Three strokes, then a pause."),
    "seven": (["x"] * 7 + ["."], "Seven strokes, then a short pause."),
}
POOLS = {
    "warmup": ["steady"],
    "steady": ["steady", "two", "three", "seven"],
    "build": ["steady", "two", "three"],
    "ease": ["steady"],
}

# round_s = "speed up every" X seconds: one whole round (Warm-up ... Ease, Hold included) lasts exactly this long.
# ramp_rounds = how many rounds the tempo takes to climb from 30% of the range to the full range.
DEFAULTS = {"bpm_min": 50, "bpm_max": 140, "round_s": 120, "hold_s": 10, "frenzy_pct": 50, "ramp_rounds": 8}
LIMITS = {"bpm_min": (30, 200), "bpm_max": (40, 240), "round_s": (40, 900), "hold_s": (3, 120), "frenzy_pct": (0, 100),
          "ramp_rounds": (1, 50)}
# Each phase's share of a round (Hold is fixed length; the rest share what is left in these proportions).
WEIGHTS = {"warmup": 1.0, "steady": 0.75, "build": 0.75, "frenzy": 0.75, "ease": 1.0}


def clean_config(raw):
    """raw: any dict with the keys above (numbers or text). Returns a safe config."""
    cfg = {}
    for key, default in DEFAULTS.items():
        lo, hi = LIMITS[key]
        try:
            value = int(float(raw.get(key, default)))
        except (TypeError, ValueError):
            value = default
        cfg[key] = max(lo, min(hi, value))
    cfg["hold_s"] = min(cfg["hold_s"], cfg["round_s"] // 3)            # a Hold never eats the round
    if cfg["bpm_max"] < cfg["bpm_min"] + 10:
        cfg["bpm_max"] = min(LIMITS["bpm_max"][1], cfg["bpm_min"] + 10)
    return cfg


@dataclass
class Phase:
    name: str
    text: str
    seconds: float
    bpm0: float = 0.0
    bpm1: float = 0.0
    tokens: list = field(default_factory=list)
    beats_per_popup: int = 2
    hold: bool = False
    level0: float = 0.3       # Hypno strength this phase aims for (start / end)
    level1: float = 0.3

    def bpm_at(self, t):
        frac = 0.0 if self.seconds <= 0 else max(0.0, min(1.0, t / self.seconds))
        return self.bpm0 + (self.bpm1 - self.bpm0) * frac

    def level_at(self, t):
        frac = 0.0 if self.seconds <= 0 else max(0.0, min(1.0, t / self.seconds))
        return self.level0 + (self.level1 - self.level0) * frac


@dataclass
class Event:
    time: float               # seconds on the session clock: the moment a circle meets the ring
    popup: bool               # a popup should appear on this hit


def make_arc(cfg, rng=random, frenzy=None):
    """frenzy: True/False to decide this round's Frenzy (the Sequencer deals them out fairly); None = roll the dice."""
    lo, hi = cfg["bpm_min"], cfg["bpm_max"]
    do_frenzy = frenzy if frenzy is not None else rng.random() * 100 < cfg["frenzy_pct"]
    parts = ["warmup", "steady", "steady", "build", "build"] + (["frenzy"] if do_frenzy else []) + ["ease"]
    unit = (cfg["round_s"] - cfg["hold_s"]) / sum(WEIGHTS[n] for n in parts)    # the round always adds up to round_s

    def secs(name):
        return unit * WEIGHTS[name]
    used = []                                    # patterns picked so far: a neighbour never repeats one

    def bpm(frac):
        return (lo + (hi - lo) * frac) * rng.uniform(0.95, 1.05)

    def pattern(pool):
        options = [n for n in POOLS[pool] if n != (used[-1] if used else None)] or POOLS[pool]
        name = rng.choice(options)
        used.append(name)
        return PATTERNS[name]

    arc = [Phase("warmup", "Stroke.", secs("warmup"), lo, lo * 1.1, PATTERNS["steady"][0], 4, level0=0.2, level1=0.3)]
    used.append("steady")
    for frac0, frac1, lvl0, lvl1 in ((0.35, 0.45, 0.4, 0.45), (0.45, 0.55, 0.45, 0.5)):
        tokens, text = pattern("steady")
        arc.append(Phase("steady", text, secs("steady"), bpm(frac0), bpm(frac1), tokens, 2, level0=lvl0, level1=lvl1))
    for frac0, frac1, lvl0, lvl1 in ((0.55, 0.7, 0.5, 0.65), (0.7, 0.9, 0.65, 0.85)):
        tokens, text = pattern("build")
        arc.append(Phase("build", "Speed up. " + text, secs("build"), bpm(frac0), bpm(frac1), tokens, 2, level0=lvl0, level1=lvl1))
    if do_frenzy:
        # Frenzy is non-stop: one even beat after another, no rests, as fast as the tempo setting goes.
        arc.append(Phase("frenzy", "Frenzy! Non-stop, stroke fast!", secs("frenzy"), hi, hi, PATTERNS["steady"][0], 1,
                         level0=1.0, level1=1.0))
    arc.append(Phase("hold", "Hold.", cfg["hold_s"], hold=True, level0=0.08, level1=0.08))
    arc.append(Phase("ease", "Slow down. Stroke.", secs("ease"), bpm(0.5), lo, PATTERNS["steady"][0], 3,
                     level0=0.4, level1=0.15))
    return arc


DELAY_SLOW_MS, DELAY_FLOOR_MS = 5000, 600       # the engine's slowest preset delay and its speed-up floor


def pace_curve(delay_ms, interval_s, speedup_pct=20, corruption=True):
    """t (seconds) -> pace 0..1, following the engine's own speed-up: every interval the popup delay shrinks
    by speedup_pct (and so does the interval, 2 s floor); the delay stops at 600 ms.
    0 = the slowest preset delay (5 s), 1 = the floor."""
    factor = 1 - max(5, min(50, int(speedup_pct))) / 100.0
    span = math.log(DELAY_SLOW_MS / float(DELAY_FLOOR_MS))
    delay0 = max(DELAY_FLOOR_MS, float(delay_ms))

    def pace(t):
        delay, interval, clock = delay0, max(2.0, float(interval_s)), 0.0
        while corruption and delay > DELAY_FLOOR_MS and clock + interval <= t:
            clock += interval
            delay = max(DELAY_FLOOR_MS, delay * factor)
            interval = max(2.0, interval * factor)
        return max(0.0, min(1.0, math.log(DELAY_SLOW_MS / delay) / span))
    return pace


def scale_phase(phase, lo, pace):
    """Pull a phase's tempo toward the slowest setting when the pace is low. Hold and Frenzy stay as they are."""
    if phase.hold or phase.name == "frenzy":
        return phase
    k = 0.3 + 0.7 * pace
    phase.bpm0 = lo + (phase.bpm0 - lo) * k
    phase.bpm1 = lo + (phase.bpm1 - lo) * k
    return phase


def popup_delay_ms(phase, bpm):
    """About how far apart popups come in this phase (the engine's delay setting; Hypno reads it for its strength)."""
    if phase.hold or bpm <= 0:
        return 1000
    return int(max(POPUP_DELAY_MIN_MS, min(POPUP_DELAY_MAX_MS, 60000.0 / bpm * phase.beats_per_popup)))


class Sequencer:
    """Builds the beat timeline phase by phase. Times are seconds from the start of the session."""

    def __init__(self, cfg, rng=random, start=2.5, pace_fn=None):
        # start: the first hit comes this many seconds in, so its circle has time to travel across first
        self.cfg, self.rng = cfg, rng
        self.pace_fn = pace_fn         # t -> 0..1, how far the preset has sped up; None = full tempo range
        self.arc = []
        self.phases = []              # (start, end, Phase)
        self.events = []              # every hit made so far, in time order
        self._taken = 0               # events handed out already
        self.end = float(start)
        self._hits = 0
        self._last_popup = -99.0
        self._round = 0                # rounds made so far (the tempo climbs with it)
        self._round_pace = 0.0
        self._round = 0                # rounds made so far (the tempo climbs with it)
        self._round_pace = 0.0
        self._bag = []                 # Frenzy rounds still to deal out (fair share, see _next_frenzy)

    def _next_frenzy(self):
        """True/False for the next round. A shuffled bag, not a coin flip, so 50% really is every other round
        on average and a long run without a Frenzy cannot happen (50% -> never two rounds in a row without)."""
        if not self._bag:
            frac = Fraction(max(0, min(100, self.cfg["frenzy_pct"])), 100).limit_denominator(10)
            self._bag = [True] * frac.numerator + [False] * (frac.denominator - frac.numerator)
            self.rng.shuffle(self._bag)
        return self._bag.pop()

    def _add_phase(self):
        if not self.arc:
            self.arc = make_arc(self.cfg, self.rng, frenzy=self._next_frenzy())
            self._round_pace = min(1.0, self._round / float(self.cfg["ramp_rounds"]))   # 0 in round 1, 1 after ramp_rounds
            self._round += 1
        phase = self.arc.pop(0)
        start = self.end
        pace = self.pace_fn(start) if self.pace_fn is not None else self._round_pace
        scale_phase(phase, self.cfg["bpm_min"], pace)
        self.phases.append((start, start + phase.seconds, phase))
        self._make_events(start, phase)
        self.end = start + phase.seconds

    def _make_events(self, start, phase):
        if phase.hold or not phase.tokens:
            return
        # The next phase opens with a hit on its very first instant (every pattern starts with 'x'). A last hit
        # that lands almost on top of it would play as a double dot, so it is skipped (a Hold is silent: no clash).
        next_hits = not (self.arc and self.arc[0].hold)
        t, i = 0.0, 0
        while t < phase.seconds:
            token = phase.tokens[i % len(phase.tokens)]
            i += 1
            n = len(token)
            bpm = min(phase.bpm_at(t), MAX_HITS_PER_SECOND * 60.0 / n)
            beat = 60.0 / max(1.0, bpm)
            for k, ch in enumerate(token):
                when = t + k * beat / n
                if ch != "x" or when >= phase.seconds:
                    continue
                if next_hits and phase.seconds - when < max(MIN_BOUNDARY_GAP_S, BOUNDARY_BEAT_FRACTION * beat):
                    continue
                self._hits += 1
                abs_t = start + when
                popup = self._hits % phase.beats_per_popup == 0 and abs_t - self._last_popup >= MIN_POPUP_GAP_S
                if popup:
                    self._last_popup = abs_t
                self.events.append(Event(abs_t, popup))
            t += beat

    def ensure(self, until):
        while self.end < until:
            self._add_phase()

    def take_until(self, until):
        """The hits that have not been handed out yet and happen before `until`."""
        self.ensure(until)
        out = []
        while self._taken < len(self.events) and self.events[self._taken].time <= until:
            out.append(self.events[self._taken])
            self._taken += 1
        if self._taken > 400:                       # forget the old ones
            del self.events[:self._taken]
            self._taken = 0
        return out

    def _locate(self, t):
        if not self.phases:
            self._add_phase()
        self.ensure(t + 0.001)
        starts = [p[0] for p in self.phases]
        return max(0, bisect.bisect_right(starts, t) - 1)

    def phase_at(self, t):
        """(index in the order the phases were made, Phase, seconds into it)."""
        idx = self._locate(t)
        start, _end, phase = self.phases[idx]
        offset = t - start
        if len(self.phases) > 12 and idx > 6:       # forget old phases
            drop = idx - 3
            del self.phases[:drop]
            idx -= drop
            self._dropped = getattr(self, "_dropped", 0) + drop
        return idx + getattr(self, "_dropped", 0), phase, offset

    def next_phase(self, t):
        """(start time, Phase) of the phase after the one playing at time t."""
        idx = self._locate(t)
        if idx + 1 >= len(self.phases):
            self._add_phase()
        start, _end, phase = self.phases[idx + 1]
        return start, phase


def from_settings(ae):
    """(config, instructions on?, click volume 0-100) from Autoedgeware's saved settings."""
    cfg = clean_config({"bpm_min": ae.get("hero_bpm_min"), "bpm_max": ae.get("hero_bpm_max"),
                        "round_s": ae.get("hero_round_seconds"), "ramp_rounds": ae.get("hero_rounds_to_full"), "hold_s": ae.get("hero_hold_seconds"),
                        "frenzy_pct": ae.get("hero_frenzy_percent")})
    try:
        volume = max(0, min(100, int(float(ae.get("hero_click_volume", 40)))))
    except (TypeError, ValueError):
        volume = 40
    return cfg, bool(ae.get("hero_text", True)), volume
