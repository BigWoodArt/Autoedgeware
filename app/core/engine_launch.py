"""How Autoedgeware starts its own popup engine (a separate Python process).

Uses the shared quiet() so no console window appears - but WITHOUT its 'hide the first window' part
(startupinfo/SW_HIDE). That part suits console tools like ffmpeg; applied to the engine, which is a
window app, Windows could hide the engine's own first window as well."""
import subprocess
import sys

from core.winproc import quiet


def engine_launch_kwargs():
    kw = dict(quiet())
    kw.pop("startupinfo", None)
    return kw


def start_engine(run_engine_py, cwd, preset_name=None):
    args = [sys.executable, run_engine_py]
    if preset_name:
        args += ["--preset", preset_name]
    return subprocess.Popen(args, cwd=cwd, **engine_launch_kwargs())
