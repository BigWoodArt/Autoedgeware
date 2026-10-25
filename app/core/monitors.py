"""Which monitors the popups use. No Tk here, so it can be tested on its own.

The engine skips any monitor whose name is in the 'disabled_monitors' list (see core/engine_overrides.py)."""


def list_monitors(get=None):
    """[(name, label, is_primary)] for every connected monitor, or [] when it cannot be read."""
    try:
        if get is None:
            from screeninfo import get_monitors as get
        found = list(get())
    except Exception:
        return []
    out = []
    for i, m in enumerate(found, 1):
        name = str(getattr(m, "name", "") or f"monitor{i}")
        primary = bool(getattr(m, "is_primary", False))
        label = f"Monitor {i}  {m.width}x{m.height}" + ("  (main)" if primary else "")
        out.append((name, label, primary))
    return out


def disabled_from(ticked, all_names):
    """Names to switch off, from the names the person left ticked. At least one monitor always stays on:
    if nothing is ticked, nothing is disabled."""
    ticked = set(ticked)
    if not (ticked & set(all_names)):
        return []
    return [n for n in all_names if n not in ticked]
