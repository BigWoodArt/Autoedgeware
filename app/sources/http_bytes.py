"""HTTP helpers for gallery scrapers (ranged downloads when CDNs reject full GET)."""
import re
import urllib.error
import urllib.request

RANGE_CHUNK = 2 * 1048576


def content_range_total(headers):
    cr = headers.get("Content-Range") or ""
    m = re.search(r"/(\d+)\s*$", cr)
    return int(m.group(1)) if m else 0


def probe_byte_size(url, headers, timeout=15):
    try:
        req = urllib.request.Request(url, headers={**headers, "Range": "bytes=0-0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return content_range_total(resp.headers)
    except Exception:
        return 0


def download_ranged(url, total, headers, wait=None, chunk=RANGE_CHUNK, timeout=60):
    """Download a file with HTTP Range when a single GET is refused."""
    if total <= 0:
        raise ValueError("unknown file size for ranged download")
    parts, start = [], 0
    while start < total:
        if wait:
            wait()
        end = min(start + chunk - 1, total - 1)
        req = urllib.request.Request(url, headers={**headers, "Range": f"bytes={start}-{end}"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            block = resp.read()
            if not block:
                break
            parts.append(block)
        start = end + 1
    body = b"".join(parts)
    if len(body) < total * 0.95:
        raise urllib.error.HTTPError(url, 502, "incomplete ranged download", None, None)
    return body
