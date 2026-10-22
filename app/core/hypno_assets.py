"""Makes the Hypno mode pictures and sounds. Pillow and the standard library; ffmpeg is used when it is there.

- Spirals: black-and-white loops that repeat seamlessly (turning by exactly one arm spacing). The first, small one
  is a GIF (nothing to wait for). The sharper sizes are 60 fps H.264 video when ffmpeg works (the graphics chip can
  decode it, and one file holds several turns so the jump back to the start is rare); a GIF otherwise.
- Binaural beats: stereo WAV loops; the left and right ears get tones a few Hz apart. Needs headphones.
Files are made once, the first time Hypno mode runs, and kept in a folder next to the program."""
import math
import os
import shutil
import struct
import subprocess
import wave

# Spirals are drawn in steps, quick and chunky first, sharp later, and every file is kept on disk:
#   s  640x360    about a second each: the first spiral is on screen within moments
#   m  1280x720   a few seconds each: clean on a 1080p screen
#   l  2560x1440  slow (about 13 s each): for screens wider than 1920 (4K)
# Each spiral plays at the best size it has so far, so the picture sharpens by itself while the rest is drawn,
# and the next launch starts at the best size straight away.
LEVELS = {"s": (640, 360), "m": (1280, 720), "l": (2560, 1440)}
LEVEL_ORDER = ["s", "m", "l"]
BIG_ABOVE_WIDTH = 1920
SPIRAL_REVISION = "6"     # bump when the spiral drawing changes: older files are redrawn (6: sharper sizes became video)
FRAMES = 36
FRAME_MS = 40
VIDEO_FPS = 60
VIDEO_CYCLE_FRAMES = 84       # frames for one turn of one arm gap (1.4 s, about the speed of the GIFs)
VIDEO_CYCLES = 7              # turns in one file: the jump back to the start happens about every 10 s
VIDEO_QUALITY = ["-crf", "20"]     # about 4 MB at 720p; a keyframe starts every turn (-g below)
VIDEO_LEVELS = ("m", "l")     # sizes made as video ('s' stays a GIF: it has to exist within a second or two)

# name, arms, shape ('arch' = even spacing, 'log' = tightens toward the middle), turns edge-to-centre,
# arm width (share of the gap, 0.5 = half black/half white), direction (+1 / -1)
SPIRALS = [
    ("tight2", 2, "arch", 3.0, 0.50, +1),
    ("loose2", 2, "arch", 1.5, 0.50, -1),
    ("tri3", 3, "arch", 2.0, 0.50, +1),
    ("quad4", 4, "arch", 2.5, 0.50, -1),
    ("six6", 6, "arch", 1.5, 0.50, +1),
    ("log2", 2, "log", 3.5, 0.50, -1),
    ("thin3", 3, "arch", 2.5, 0.30, -1),
    ("fat2", 2, "arch", 2.0, 0.70, +1),
]
SPIRAL_NAMES = [s[0] for s in SPIRALS]

BEAT_RATE = 22050
BEAT_SECONDS = 20          # whole numbers of cycles fit in 20 s, so the loop has no click
# name, carrier Hz (left ear), beat Hz (right ear is carrier + beat)
BEATS = [
    ("delta3", 150, 3), ("theta4", 180, 4), ("theta5", 130, 5),
    ("theta6", 200, 6), ("alpha8", 240, 8), ("alpha10", 220, 10),
]
BEAT_NAMES = [b[0] for b in BEATS]


def pick_tier(monitor_widths):
    """The sharpest size worth drawing: 'l' when any screen is wider than 1920, else 'm'."""
    return "l" if any(w > BIG_ABOVE_WIDTH for w in monitor_widths) else "m"


def levels_up_to(target):
    return LEVEL_ORDER[:LEVEL_ORDER.index(target if target in LEVELS else "m") + 1]


def tier_of(path):
    """The size level a spiral file was drawn at, from its name."""
    parts = os.path.splitext(os.path.basename(str(path)))[0].split("_")      # spiral_<name>_<level>_v<revision>
    level = parts[-2] if len(parts) >= 2 else ""
    return level if level in LEVELS else "m"


def spiral_path(folder, name, level="m", ext=".gif"):
    return os.path.join(folder, f"spiral_{name}_{level}_v{SPIRAL_REVISION}{ext}")   # revision in the name: never overwritten


def _good(path):
    try:
        return os.path.isfile(path) and os.path.getsize(path) > 0
    except OSError:
        return False


def level_file(folder, name, level):
    """The finished file for this spiral at this size (video first, then GIF), or None."""
    for ext in (".mp4", ".gif"):
        path = spiral_path(folder, name, level, ext)
        if _good(path):
            return path
    return None


def best_spiral(folder, name, target="m"):
    """Path of the sharpest finished file for this spiral (up to `target`), or None."""
    for level in reversed(levels_up_to(target)):
        path = level_file(folder, name, level)
        if path:
            return path
    return None


def beat_path(folder, name):
    return os.path.join(folder, f"beat_{name}.wav")


def _phase(shape, turns, r, radius):
    if shape == "log":
        s = 25.0
        return 2 * math.pi * turns * math.log(1 + r / s) / math.log(1 + radius / s)
    return 2 * math.pi * turns * r / radius


def _draw_base(arms, shape, turns, width, direction, out_w, out_h):
    """(base picture, left, top): a big square spiral that can be turned and cropped to the screen size."""
    from PIL import Image, ImageDraw
    half_diag = math.hypot(out_w, out_h) / 2
    size = int(math.ceil(half_diag * 2)) + 2           # a circle that covers every corner of the frame
    centre = size / 2
    radius = size / 2
    ss = 2                                             # drawn at double size, then shrunk: smooth (antialiased) edges
    base = Image.new("L", (size * ss, size * ss), 0)
    draw = ImageDraw.Draw(base)
    gap = 2 * math.pi / arms
    # Each arm is a polygon whose far end is closed by a straight chord. Run the arm out far enough that the chord
    # lies completely outside the picture (otherwise arms seem to stop short of the screen edge).
    reach = 1.1 / math.cos(min(gap * width / 2, 1.2))
    steps = int(0.4 * size * reach)       # enough points that curves stay smooth at this size
    for k in range(arms):
        outer, inner = [], []
        for i in range(1, steps + 1):
            r = radius * reach * i / steps
            theta = k * gap + direction * _phase(shape, turns, r, radius)
            outer.append(((centre + r * math.cos(theta + gap * width / 2)) * ss, (centre + r * math.sin(theta + gap * width / 2)) * ss))
            inner.append(((centre + r * math.cos(theta - gap * width / 2)) * ss, (centre + r * math.sin(theta - gap * width / 2)) * ss))
        draw.polygon(outer + inner[::-1], fill=255)
    base = base.resize((size, size), Image.LANCZOS)
    return base, (size - out_w) // 2, (size - out_h) // 2


def _frame(base, left, top, out_w, out_h, angle):
    from PIL import Image
    turned = base.rotate(angle, resample=Image.BICUBIC)
    frame = turned.crop((left, top, left + out_w, top + out_h))
    return frame.point(lambda v: (v // 16) * 17)       # 16 grey levels: smooth edges, small files


def make_spiral(path, arms, shape, turns, width, direction, size=None):
    """Animated GIF (36 frames, one arm gap per loop)."""
    out_w, out_h = size or LEVELS["m"]
    base, left, top = _draw_base(arms, shape, turns, width, direction, out_w, out_h)
    step_angle = 360.0 / arms                           # turning one arm gap gives the same picture: seamless
    frames = [_frame(base, left, top, out_w, out_h, -direction * step_angle * f / FRAMES) for f in range(FRAMES)]
    frames[0].save(path, format="GIF", save_all=True, append_images=frames[1:], duration=FRAME_MS, loop=0, disposal=1)


def ffmpeg_ok():
    return shutil.which("ffmpeg") is not None


def _quiet():
    try:
        from core.winproc import quiet
        return quiet()
    except Exception:
        return {}


def make_spiral_video(path, arms, shape, turns, width, direction, size=None, fps=None,
                      cycle_frames=None, cycles=None):
    """H.264 .mp4 of the same spiral. One turn of one arm gap is drawn and encoded (a keyframe starts the turn, so the
    jump back is instant), then repeated `cycles` times by copying: no extra drawing, and the turns join exactly.
    Raises on any problem (the caller falls back to the GIF)."""
    fps, cycle_frames, cycles = fps or VIDEO_FPS, cycle_frames or VIDEO_CYCLE_FRAMES, cycles or VIDEO_CYCLES
    out_w, out_h = size or LEVELS["m"]
    out_w, out_h = out_w - out_w % 2, out_h - out_h % 2         # H.264 wants even sizes
    base, left, top = _draw_base(arms, shape, turns, width, direction, out_w, out_h)
    step_angle = 360.0 / arms
    one = path + ".turn.mp4"
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
           "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{out_w}x{out_h}", "-r", str(fps), "-i", "-",
           "-an", "-vf", "format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", *VIDEO_QUALITY, "-g", str(cycle_frames),
           "-threads", "2", "-movflags", "+faststart", one]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, **_quiet())
    try:
        for f in range(cycle_frames):
            frame = _frame(base, left, top, out_w, out_h, -direction * step_angle * f / cycle_frames)
            proc.stdin.write(frame.tobytes())
        proc.stdin.close()
        err = proc.stderr.read().decode("utf-8", "replace")
        if proc.wait(timeout=300) != 0:
            raise RuntimeError("ffmpeg: " + err.strip()[-300:])
        subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-stream_loop",
                        str(cycles - 1), "-i", one, "-c", "copy", "-movflags", "+faststart", "-f", "mp4", path],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300, check=True, **_quiet())
        if not _good(path):
            raise RuntimeError("ffmpeg made an empty file")
    finally:
        try:
            proc.kill()
        except Exception:
            pass
        try:
            os.remove(one)
        except OSError:
            pass


def make_beat(path, carrier, beat, seconds=BEAT_SECONDS, rate=BEAT_RATE, amplitude=0.6):
    n = int(seconds * rate)
    two_pi = 2 * math.pi
    data = bytearray()
    peak = int(32767 * amplitude)
    for i in range(n):
        t = i / rate
        data += struct.pack("<hh", int(peak * math.sin(two_pi * carrier * t)),
                            int(peak * math.sin(two_pi * (carrier + beat) * t)))
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(data))


def ensure_beats(folder):
    os.makedirs(folder, exist_ok=True)
    for name, carrier, beat in BEATS:
        path = beat_path(folder, name)
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            tmp = path + ".part"
            make_beat(tmp, carrier, beat)
            os.replace(tmp, path)


def ensure_level(folder, level, names=None, log=None):
    """Make this size of the given spirals (all by default) where no file exists yet. A finished file is never
    touched again (on Windows a spiral that is playing cannot be replaced). Written to a .part file first, so a
    half-made spiral is never picked up. Sharper sizes are video when ffmpeg works, a GIF otherwise."""
    os.makedirs(folder, exist_ok=True)
    for name, arms, shape, turns, width, direction in SPIRALS:
        if names is not None and name not in names:
            continue
        if level_file(folder, name, level):
            continue
        w, h = LEVELS[level]
        kind = "gif"
        if level in VIDEO_LEVELS and ffmpeg_ok():
            tmp = spiral_path(folder, name, level, ".mp4") + ".part"
            try:
                make_spiral_video(tmp, arms, shape, turns, width, direction, LEVELS[level])
                os.replace(tmp, spiral_path(folder, name, level, ".mp4"))
                kind = "video"
            except Exception as ex:
                if log:
                    log(f"hypno: video for {name} at {level} failed, using a GIF instead ({ex})")
                try:
                    os.remove(tmp)
                except OSError:
                    pass
        if kind == "gif":
            tmp = spiral_path(folder, name, level, ".gif") + ".part"
            make_spiral(tmp, arms, shape, turns, width, direction, LEVELS[level])
            os.replace(tmp, spiral_path(folder, name, level, ".gif"))
        if log:
            log(f"hypno: made spiral {name} at {level} ({w}x{h}, {kind})")


def ensure_first(folder, log=None):
    """The quickest thing that can play: the beats and one small spiral (about a second of work)."""
    ensure_beats(folder)
    if best_spiral(folder, SPIRAL_NAMES[0], "l") is None:      # nothing to play yet, at any size
        ensure_level(folder, "s", names=[SPIRAL_NAMES[0]], log=log)


def ensure_assets(folder, log=None, target="m"):
    """Everything up to the `target` size, smallest size first, so something is playable at once and the
    rest sharpens as it finishes. Safe to call again (finished, current files are left alone)."""
    ensure_beats(folder)
    for level in levels_up_to(target):
        ensure_level(folder, level, log=log)
    keep = {os.path.basename(spiral_path(folder, n, lv, ext)) for n in SPIRAL_NAMES for lv in LEVELS
            for ext in (".gif", ".mp4")}
    try:                                                   # spirals from older versions: removed (skipped if in use)
        for fname in os.listdir(folder):
            if fname.startswith("spiral_") and fname not in keep and fname.endswith((".gif", ".mp4", ".txt", ".part")):
                try:
                    os.remove(os.path.join(folder, fname))
                except OSError:
                    pass
    except OSError:
        pass
    if log:
        try:
            ver = open(os.path.join(os.path.dirname(os.path.abspath(folder)), "VERSION"), encoding="utf-8").read().strip()
        except Exception:
            ver = "?"
        log(f"hypno: pictures and sounds ready in {folder} (Autoedgeware {ver})")


def available(folder, target="m"):
    """(spiral names, beat names) with a playable file right now (any size up to `target`)."""
    spirals = [n for n in SPIRAL_NAMES if best_spiral(folder, n, target)]
    beats = [n for n in BEAT_NAMES if os.path.isfile(beat_path(folder, n))]
    return spirals, beats
