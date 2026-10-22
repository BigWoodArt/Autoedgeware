"""Keeps new videos light: a long video is cut to its first MAX seconds (no re-encode, no quality loss), and a
video that can only ever be a popup is shrunk. Needs ffmpeg/ffprobe; without them (or if any step fails) the
video is kept exactly as downloaded. No Tk, so it can be tested.

"Popup-only" = not taller than the fullscreen limit (Settings > "Only taller than"), so it is never shown
fullscreen and does not need its full size. A taller video is a fullscreen candidate and keeps its quality."""
import json
import os
import shutil
import subprocess

from core.winproc import quiet

DEFAULT_MAX_SECONDS = 120
DEFAULT_SHRINK_TO = 720
SETTING_KEYS = {"max_seconds": "video_max_seconds", "shrink_to": "video_shrink_to_px"}
SHRINKABLE = {".mp4", ".m4v", ".mov", ".mkv"}      # x264 + the original audio fit in these containers
CUTTABLE = SHRINKABLE | {".webm"}


def ffmpeg_ready():
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def rules_from_settings(settings):
    def num(key, default, hi):
        try:
            return max(0, min(hi, int(float(settings.get(key, default)))))
        except (TypeError, ValueError):
            return default
    return {"max_seconds": num(SETTING_KEYS["max_seconds"], DEFAULT_MAX_SECONDS, 36000),
            "shrink_to": num(SETTING_KEYS["shrink_to"], DEFAULT_SHRINK_TO, 4320),
            "fs_min_height": num("fullscreen_video_min_height", 1080, 4320)}


def probe(path):
    """(height, seconds) of the first video stream, or None."""
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                              "stream=height:format=duration", "-of", "json", path],
                             capture_output=True, text=True, timeout=30, check=True, **quiet()).stdout
        data = json.loads(out)
        return int(data["streams"][0]["height"]), float(data["format"]["duration"])
    except Exception:
        return None


def plan(height, seconds, ext, rules):
    """(cut_to_seconds or 0, shrink_to_height or 0) for a video; (0, 0) = leave it alone."""
    ext = ext.lower()
    cut = rules.get("max_seconds", 0)
    cut = cut if (cut and seconds > cut + 1 and ext in CUTTABLE) else 0
    shrink = rules.get("shrink_to", 0)
    popup_only = height <= rules.get("fs_min_height", 1080)
    shrink = shrink if (shrink and popup_only and height > shrink + 8 and ext in SHRINKABLE) else 0
    return cut, shrink


def tidy(path, rules, log=None):
    """Cut and/or shrink `path` in place. True if the file was changed. Never raises; keeps the original on any
    problem."""
    if not rules or not (rules.get("max_seconds") or rules.get("shrink_to")) or not ffmpeg_ready():
        return False
    try:
        info = probe(path)
        if not info:
            return False
        ext = os.path.splitext(path)[1]
        cut, shrink = plan(info[0], info[1], ext, rules)
        if not cut and not shrink:
            return False
        tmp = path + ".tidy" + ext
        cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", path]
        if cut:
            cmd += ["-t", str(cut)]
        if shrink:
            cmd += ["-vf", f"scale=-2:{shrink}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                    "-pix_fmt", "yuv420p", "-threads", "2", "-c:a", "copy", "-movflags", "+faststart"]
        else:
            cmd += ["-c", "copy"]
        cmd.append(tmp)
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=900, check=True,
                           **quiet())
            if not os.path.isfile(tmp) or os.path.getsize(tmp) == 0:
                raise OSError("empty result")
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
        if log:
            what = []
            if cut:
                what.append(f"cut to {cut}s")
            if shrink:
                what.append(f"shrunk {info[0]}p -> {shrink}p")
            log(f"   -> {os.path.basename(path)}: " + ", ".join(what))
        return True
    except Exception:
        return False
