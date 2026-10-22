"""Appends every log line to a file, in addition to wherever else it's
shown (console, GUI log panel). One timestamped file per run, under
logs/ - named the moment the first line is written."""
import datetime
import os
import threading

_lock = threading.Lock()
_run_filename = None  # set once, on first write of this process


def _log_path(base_dir):
    global _run_filename
    log_dir = os.path.join(base_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    if _run_filename is None:
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        _run_filename = f"autoedgeware_{stamp}.log"
    return os.path.join(log_dir, _run_filename)


def write(base_dir, msg, level="info"):
    line = f"{datetime.datetime.now().isoformat(timespec='seconds')} [{level.upper()}] {msg}\n"
    try:
        with _lock:
            with open(_log_path(base_dir), "a", encoding="utf-8") as f:
                f.write(line)
    except Exception:
        pass  # logging to disk is best-effort; never crash the app over it
