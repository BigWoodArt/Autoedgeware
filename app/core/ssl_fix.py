"""Trust the certifi certificate bundle as well as the computer's own.

Some Windows PCs have an out-of-date certificate store, which makes downloads fail with
"CERTIFICATE_VERIFY_FAILED ... certificate has expired" (the site's chain uses a newer root than the PC knows).
Python's `requests` ships certifi, so it is already installed. Verification stays ON: this only adds trusted roots,
it never switches checking off by itself (only the opt-in setting does). A wrong clock or a network that swaps certificates (some VPNs, filters) is not
fixed by this."""
import ssl

_ORIGINAL = ssl._create_default_https_context      # what Python does by default; used to switch checks back on


def install(skip_checks=False):
    """Returns True when the extra bundle was added (or checks were skipped).

    skip_checks=True turns certificate checking OFF for downloads. It is an opt-in setting (Advanced tab) for
    networks that swap certificates; it makes downloads unsafe on any untrusted network."""
    if skip_checks:
        ssl._create_default_https_context = ssl._create_unverified_context
        return True
    ssl._create_default_https_context = _ORIGINAL        # checks back on (undoes an earlier skip)
    try:
        import certifi
        cafile = certifi.where()
    except Exception:
        return False

    def make_context(*args, **kwargs):
        ctx = ssl.create_default_context(*args, **kwargs)
        try:
            ctx.load_verify_locations(cafile=cafile)
        except Exception:
            pass
        return ctx
    ssl._create_default_https_context = make_context
    return True


def install_from_file(settings_path):
    """Entry points call this: reads only the 'skip_certificate_checks' flag from settings.json."""
    import json
    skip = False
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            skip = bool(json.load(f).get("skip_certificate_checks", False))
    except Exception:
        pass
    return install(skip_checks=skip)
