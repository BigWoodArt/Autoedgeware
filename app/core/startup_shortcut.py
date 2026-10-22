"""Adds/removes a shortcut in the Windows Startup Apps folder that
launches run_engine.py windowlessly (via the pyw launcher, same as
run.bat uses for the same reason - no lingering console window)."""
import os
from pathlib import Path

STARTUP_BAT_NAME = "Autoedgeware.bat"


def _startup_folder():
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def _shortcut_path(base_dir):
    folder = _startup_folder()
    if not folder:
        return None
    return folder / STARTUP_BAT_NAME


def is_added(base_dir):
    path = _shortcut_path(base_dir)
    return bool(path and path.is_file())


def add_to_startup(base_dir):
    """Writes a small .bat into the Windows Startup folder that
    launches run_engine.py with pyw (no console window). Raises on
    failure (e.g. not on Windows, no APPDATA) rather than failing
    silently - the caller shows this to the user."""
    path = _shortcut_path(base_dir)
    if not path:
        raise RuntimeError("Could not find the Windows Startup folder (no APPDATA) - is this Windows?")
    run_engine_path = Path(base_dir) / "run_engine.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'@echo off\r\ncd /D "{base_dir}"\r\nstart "" pyw "{run_engine_path}"\r\n',
        encoding="utf-8",
    )
    return path


def remove_from_startup(base_dir):
    path = _shortcut_path(base_dir)
    if path and path.is_file():
        path.unlink()
        return True
    return False
