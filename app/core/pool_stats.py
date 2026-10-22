"""Counts what is ready to pop in a preset's folder, and builds the plain-language status line.
No Edgeware or Tk imports, so it can be tested on its own."""
import os

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
VIDEO_EXTS = {".mp4", ".webm", ".mkv", ".mov", ".avi", ".m4v"}
AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".ogg", ".flac", ".aac", ".opus"}


def count_media(folder):
    """(images, videos, audio) found directly in folder. Hidden/temp files are ignored."""
    images = videos = audio = 0
    try:
        names = os.listdir(folder)
    except OSError:
        return 0, 0, 0
    for name in names:
        if name.startswith(".") or name.endswith(".tmp"):
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext in IMAGE_EXTS:
            images += 1
        elif ext in VIDEO_EXTS:
            videos += 1
        elif ext in AUDIO_EXTS:
            audio += 1
    return images, videos, audio


def _plural(n, word):
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def status_line(counts, scraping, engine_on, paused_seconds=None):
    """One short sentence for the status bar."""
    if paused_seconds is not None:
        m, s = divmod(max(0, int(paused_seconds)), 60)
        return f"Paused. Popups come back in {m}:{s:02d}."
    if not engine_on and not scraping:
        return "Ready."
    images, videos, audio = counts
    if images + videos + audio == 0:
        return "Downloading your first files... popups start as soon as one is ready."
    ready = f"{_plural(images, 'image')}, {_plural(videos, 'video')}, {audio} audio"
    if scraping:
        return f"Running. Ready to pop: {ready}. Still downloading."
    return f"Running. Ready to pop: {ready}. Downloading is finished; popups continue."


def count_text(counts):
    """'11 images, 200 videos, 5 audio already downloaded' for the Main tab."""
    images, videos, audio = counts
    if images + videos + audio == 0:
        return "Nothing downloaded yet for this preset."
    return f"{_plural(images, 'image')}, {_plural(videos, 'video')}, {audio} audio already downloaded"
