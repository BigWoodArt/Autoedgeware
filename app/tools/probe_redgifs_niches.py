"""Probe: how do Redgifs 'niches' work? Double-click "Run Redgifs Probe.bat" - it writes probe_redgifs.txt next to
this file. Send that file back. Read-only: it only asks Redgifs questions and downloads nothing."""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
API = "https://api.redgifs.com"
WORDS = ["hypnotic", "addict", "spiral"]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "probe_redgifs.txt")
_lines = []


def say(text=""):
    print(text)
    _lines.append(str(text))


def get(path, token=None, wait=1.2):
    time.sleep(wait)
    headers = {"User-Agent": UA, "Accept": "application/json", "Referer": "https://www.redgifs.com/",
               "Origin": "https://www.redgifs.com"}
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        with urllib.request.urlopen(urllib.request.Request(API + path, headers=headers), timeout=25) as r:
            return r.status, r.read().decode("utf-8", "ignore")
    except Exception as ex:
        body = ""
        try:
            body = ex.read().decode("utf-8", "ignore")
        except Exception:
            pass
        return getattr(ex, "code", 0), f"ERROR {ex} {body}"


def parse(text):
    try:
        return json.loads(text)
    except ValueError:
        return None


def shape(obj, depth=0):
    """Key names only, so the file shows what a reply contains without pages of data."""
    if isinstance(obj, dict):
        return {k: (shape(v, depth + 1) if depth < 2 else type(v).__name__) for k, v in list(obj.items())[:25]}
    if isinstance(obj, list):
        return [shape(obj[0], depth + 1)] if obj else []
    return type(obj).__name__


def try_path(title, path, token, note=""):
    status, text = get(path, token)
    data = parse(text)
    say(f"\n== {title}\n   GET {path}\n   HTTP {status}, {len(text)} bytes {note}")
    if data is None:
        say("   (not JSON) " + text[:300].replace("\n", " "))
        return None
    say("   keys: " + json.dumps(shape(data))[:700])
    return data


def niches_in(obj, found=None):
    """Any niche-looking records (id + name) anywhere in a reply."""
    found = {} if found is None else found
    if isinstance(obj, dict):
        if "id" in obj and "name" in obj and ("gifs" in obj or "subscribers" in obj):
            found[obj["id"]] = obj
        for v in obj.values():
            niches_in(v, found)
    elif isinstance(obj, list):
        for v in obj:
            niches_in(v, found)
    return found


def main():
    say(f"Redgifs niche probe {time.strftime('%Y-%m-%d %H:%M:%S')}  python {sys.version.split()[0]}")
    status, text = get("/v2/auth/temporary", None, 0)
    data = parse(text) or {}
    token = data.get("token")
    say(f"token: HTTP {status}, got token: {bool(token)}")
    if not token:
        say(text[:300])
        return
    all_niches = {}
    for word in WORDS:
        q = urllib.parse.quote(word)
        say(f"\n\n######## WORD: {word} ########")
        sugg = try_path("suggest (known to work)", f"/v2/search/suggest?query={q}", token)
        all_niches.update(niches_in(sugg))
        for title, path in (
            ("niche search A", f"/v2/niches/search?query={q}&order=best&count=10&page=1"),
            ("niche search B", f"/v2/search/niches?query={q}&order=best&count=10&page=1"),
            ("niche search C", f"/v2/niches?query={q}&count=10&page=1"),
            ("niche search D", f"/v2/search?query={q}&type=n&count=10&page=1"),
            ("free text, like the website", f"/v2/gifs/search?search_text={q}&type=g&order=best&count=10&page=1"),
            ("free text, order=score", f"/v2/gifs/search?search_text={q}&type=g&order=score&count=10&page=1"),
            ("free text, query=", f"/v2/gifs/search?query={q}&type=g&order=score&count=10&page=1"),
            ("tag filter (what the app uses)", f"/v2/gifs/search?tags={q}&type=g&order=score&count=10&page=1"),
        ):
            reply = try_path(title, path, token)
            all_niches.update(niches_in(reply))
            if isinstance(reply, dict) and reply.get("gifs"):
                gifs = reply["gifs"]
                tags = [", ".join((g.get("tags") or [])[:4]) for g in gifs[:3]]
                say(f"   {len(gifs)} gifs; first tags: {tags}")

    say("\n\n######## NICHES FOUND IN THE REPLIES ########")
    for nid, n in list(all_niches.items())[:12]:
        say(f"   {nid}: {n.get('name')!r} gifs={n.get('gifs')} subscribers={n.get('subscribers')}")
    # try to open the first few niches
    for nid in list(all_niches)[:3]:
        say(f"\n\n######## OPEN NICHE {nid} ########")
        for title, path in (
            ("niche gifs A", f"/v2/niches/{nid}/gifs?order=trending&count=10&page=1"),
            ("niche gifs B", f"/v2/niches/{nid}?order=trending&count=10&page=1"),
            ("niche gifs C", f"/v2/gifs/search?niche={nid}&type=g&order=trending&count=10&page=1"),
            ("niche gifs D", f"/v2/niches/{nid}/gifs?order=top28&count=10&page=1"),
        ):
            reply = try_path(title, path, token)
            if isinstance(reply, dict) and reply.get("gifs"):
                g = reply["gifs"][0]
                say(f"   {len(reply['gifs'])} gifs; first: id={g.get('id')} tags={g.get('tags')} urls={list((g.get('urls') or {}).keys())}")
    say("\nDone.")


if __name__ == "__main__":
    try:
        main()
    finally:
        with open(OUT, "w", encoding="utf-8") as f:
            f.write("\n".join(_lines))
        print("\nSaved:", OUT)
