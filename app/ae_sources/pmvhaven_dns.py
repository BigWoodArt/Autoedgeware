"""PMV Haven's name does not resolve on some PCs (the system DNS answers
"no such address") even though the site is up. When that happens, look the
name up through public DNS and hand that address to the normal HTTPS client,
which still checks the certificate against pmvhaven.com.

Only pmvhaven.com and its subdomains are handled this way, and only after the
system lookup has already failed. Every other host is unchanged.
"""
import json
import socket
import threading
import time
import urllib.parse
import urllib.request

_system = socket.getaddrinfo
_lock = threading.Lock()
_cache = {}          # host -> (expiry, [ip, ...])
_notice = None
_installed = False
_OK_FOR = 300
_FAIL_FOR = 30


def _is_site(host):
    if not isinstance(host, str):
        return False
    name = host.lower().rstrip(".")
    return name == "pmvhaven.com" or name.endswith(".pmvhaven.com")


def _ipv4(text):
    parts = str(text).split(".")
    if len(parts) != 4:
        return False
    try:
        return all(0 <= int(p) <= 255 and str(int(p)) == p for p in parts)
    except ValueError:
        return False


def _public(host):
    """A records from Cloudflare, then Google. Empty when both fail."""
    quoted = urllib.parse.quote(host)
    urls = (
        f"https://cloudflare-dns.com/dns-query?name={quoted}&type=A",
        f"https://dns.google/resolve?name={quoted}&type=A",
    )
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/dns-json"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8", "replace"))
        except Exception:
            continue
        ips = [a.get("data") for a in (data.get("Answer") or []) if a.get("type") == 1]
        ips = [ip for ip in ips if _ipv4(ip)]
        if ips:
            return ips
    return []


def _lookup(host):
    global _notice
    now = time.monotonic()
    with _lock:
        hit = _cache.get(host)
        if hit and hit[0] > now:
            return hit[1]
    ips = _public(host)
    with _lock:
        _cache[host] = (now + (_OK_FOR if ips else _FAIL_FOR), ips)
        if ips and _notice is None:
            _notice = "this computer's DNS has no address for the site; using public DNS instead"
    return ips


def take_notice():
    """The one-line explanation, once. None if public DNS was not needed."""
    global _notice
    with _lock:
        msg, _notice = _notice, None
        return msg


def _pack(ips, port, family, socktype, proto):
    if isinstance(port, str):
        try:
            port = socket.getservbyname(port)
        except OSError:
            port = 0
    elif port is None:
        port = 0
    if family not in (0, socket.AF_UNSPEC, socket.AF_INET):
        return []
    socktype = socktype or socket.SOCK_STREAM
    proto = proto or socket.IPPROTO_TCP
    return [(socket.AF_INET, socktype, proto, "", (ip, port)) for ip in ips]


def _getaddrinfo(host, port, family=0, socktype=0, proto=0, flags=0):
    try:
        return _system(host, port, family, socktype, proto, flags)
    except socket.gaierror:
        if not _is_site(host):
            raise
        found = _pack(_lookup(host), port, family, socktype, proto)
        if not found:
            raise
        return found


def install():
    global _installed
    with _lock:
        if _installed:
            return
        socket.getaddrinfo = _getaddrinfo
        _installed = True
