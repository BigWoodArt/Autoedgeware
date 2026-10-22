"""Talks to an actual local Edgeware++ install (found at settings["edgeware_root"],
the folder containing that install's own src/ and data/ subfolders).

Mirrors config.pyw's own approach exactly rather than reinventing it:
  - config.json lives at <edgeware_root>/data/config.json (flat key/value dict)
  - real startup toggling goes through <edgeware_root>/src/os_utils, which is
    only importable once that src/ is on sys.path and its data/ dir is
    discoverable for libmpv's DLL (Windows) - config.pyw's apply_startup_toggle
    does the same PATH/dll-directory dance before importing it.
"""
import json
import os
import sys
from pathlib import Path


def _paths(edgeware_root):
    root = Path(edgeware_root)
    return root, root / "src", root / "data", root / "data" / "config.json"


def is_valid_root(edgeware_root):
    if not edgeware_root:
        return False
    _, src, data, _ = _paths(edgeware_root)
    return src.is_dir() and data.is_dir()


def apply_config(edgeware_root, updates):
    """Merge `updates` (e.g. an intensity preset bundle) into the real
    Edgeware config.json. Leaves every other existing key untouched."""
    if not updates:
        return
    _, _, data, config_path = _paths(edgeware_root)
    data.mkdir(parents=True, exist_ok=True)
    current = {}
    if config_path.is_file():
        with open(config_path, "r", encoding="utf-8") as f:
            current = json.load(f)
    current.update(updates)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)


def toggle_startup(edgeware_root, enabled):
    """Create/remove the real OS startup entry for Edgeware, via Edgeware's
    own os_utils module. Only works where that module's own dependencies
    (e.g. mpv/win32com on Windows) are already installed for that Edgeware
    install - same requirement config.pyw itself has."""
    root, src, data, _ = _paths(edgeware_root)
    src_path = str(src)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    if str(data) not in os.environ.get("PATH", ""):
        os.environ["PATH"] += os.pathsep + str(data)
    try:
        os.add_dll_directory(str(data))
    except (AttributeError, OSError):
        pass
    import os_utils
    os_utils.toggle_run_at_startup(bool(enabled))
