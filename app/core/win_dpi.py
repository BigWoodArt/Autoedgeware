"""Windows display scaling for the settings window.

The process used to tell Windows it was not DPI-aware. Windows then stretched
the whole window like a bitmap, so on a 2K laptop at 125% or 150% the text
looked soft. Per-monitor v2 draws at the real pixel size (a video player
embedded in a popup stays aligned), and Tk is given the same scale Windows uses.

Call enable() before any Tk window exists. Windows ignores a later change.
"""
import sys

# DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2. Child windows (the embedded
# video player) use the same pixels as the parent, so they are not shifted.
_PER_MONITOR_V2 = -4
_TK_AT_100 = 96 / 72   # Tk's "tk scaling" at 96 DPI: pixels per point


def scale_for_dpi(dpi):
    """Size multiplier against a 96 DPI (100%) display. 144 DPI -> 1.5. Never below 1."""
    try:
        dpi = int(dpi)
    except (TypeError, ValueError):
        return 1.0
    if dpi < 96:
        return 1.0
    return dpi / 96.0


def tk_scaling_for_dpi(dpi):
    """Value for `tk scaling` (pixels per point) at this DPI."""
    return scale_for_dpi(dpi) * _TK_AT_100


def scale_px(n, scale):
    """A length written for a 100% display, in real pixels at `scale`."""
    try:
        return max(1, int(round(float(n) * float(scale))))
    except (TypeError, ValueError):
        try:
            return max(1, int(n))
        except (TypeError, ValueError):
            return 1


def ui_scale(widget):
    """Scale already applied to this Tk app. 1.0 at 100%."""
    try:
        return max(1.0, float(widget.tk.call("tk", "scaling")) / _TK_AT_100)
    except Exception:
        return 1.0


def read_dpi():
    """System DPI (the primary monitor). 96 when it cannot be read, or off Windows."""
    if sys.platform != "win32":
        return 96
    try:
        import ctypes
        return max(96, int(ctypes.windll.user32.GetDpiForSystem()))
    except Exception:
        return 96


def enable():
    """Draw sharply. Safe to call more than once. No-op off Windows."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        fn = ctypes.windll.user32.SetProcessDpiAwarenessContext
        fn.argtypes = [ctypes.c_void_p]
        fn.restype = ctypes.c_int
        fn(ctypes.c_void_p(_PER_MONITOR_V2))
        return
    except Exception:
        pass
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)   # per-monitor, when v2 is missing
    except Exception:
        pass


def apply_tk(root, dpi=None):
    """Point-sized text follows the Windows scale. Call once, before building widgets.

    Returns the scale (1.0 at 100%). Off Windows the existing Tk scaling is left alone.
    """
    if sys.platform != "win32":
        return 1.0
    scale = scale_for_dpi(read_dpi() if dpi is None else dpi)
    try:
        root.tk.call("tk", "scaling", tk_scaling_for_dpi(dpi if dpi is not None else read_dpi()))
    except Exception:
        return ui_scale(root)
    return scale
