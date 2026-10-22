"""Stop console windows flashing up on Windows when the engine starts a console program.

Edgeware's video code runs ffprobe (twice per video, via the 'videoprops' package) and starts a helper
Python for mpv. Neither is code we edit, so every program this process starts defaults to
CREATE_NO_WINDOW. Only that flag, never SW_HIDE: it affects console windows only, so windowed
programs (explorer, mpv's helper) are not hidden."""
import subprocess
import sys

CREATE_NO_WINDOW = 0x08000000
_installed = False


def install(platform=None):
    global _installed
    if _installed or not (platform or sys.platform).startswith("win"):
        return
    original = subprocess.Popen.__init__

    def patched(self, *args, **kwargs):
        if len(args) < 14:          # creationflags is the 14th positional; leave such calls alone
            kwargs["creationflags"] = kwargs.get("creationflags", 0) | CREATE_NO_WINDOW
        original(self, *args, **kwargs)

    subprocess.Popen.__init__ = patched
    _installed = True
