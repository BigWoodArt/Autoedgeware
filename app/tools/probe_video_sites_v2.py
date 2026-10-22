"""Probe v2 for Hypnotube + PMVHaven. Run:  python probe_video_sites_v2.py > probe2.txt   (then attach probe2.txt)
Answers: how many videos per page, does paging work, does the search word really filter, which sort options exist."""
import re
import sys
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
HT_LINK = re.compile(r'href=["\'](?:https?://(?:www\.)?hypnotube\.com)?(/video/[^"\'#?\s]*?-(\d+)\.html)', re.I)
PMV_LINK = re.compile(r'href=["\'](?:https?://(?:www\.)?pmvhaven\.com)?(/video/[^"\'?#&\s]*?_([0-9a-f]{24}))', re.I)


def get(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=25) as r:
            return r.status, r.read().decode("utf-8", "ignore")
    except Exception as ex:
        return getattr(ex, "code", 0), f"ERROR {ex}"


def ids(rx, page):
    return list(dict.fromkeys(m[1] for m in rx.findall(page.replace("&amp;", "&"))))


def show(title, url, rx):
    status, page = get(url)
    found = ids(rx, page)
    print(f"\n== {title}\n   {url}\n   HTTP {status}, {len(page)} bytes, {len(found)} video links, first: {found[:3]}")
    return page, found


print("### HYPNOTUBE")
for word in ("spiral", "zzqxjv"):
    page, a = show(f"search '{word}'", f"https://hypnotube.com/search/{word}/", HT_LINK)
    for m in re.findall(r'[^<>]{0,40}\b\d[\d,]*\s*(?:videos?|results?)\b[^<>]{0,30}', page, re.I)[:3]:
        print("   count text:", m.strip())
    print("   paging hrefs:", sorted(set(re.findall(r'href="([^"]*(?:page|/\d+/)[^"]*)"', page)))[:8])
    print("   sort hrefs:", sorted(set(re.findall(r'href="([^"]*/(?:newest|rating|views|duration)/[^"]*)"', page)))[:8])
_, p1 = show("page 1", "https://hypnotube.com/search/spiral/", HT_LINK)
for guess in ("https://hypnotube.com/search/spiral/page2/", "https://hypnotube.com/search/spiral/2/",
              "https://hypnotube.com/search/spiral/?page=2", "https://hypnotube.com/search/spiral/newest/page2/"):
    _, p2 = show("page 2 guess", guess, HT_LINK)
    print("   same as page 1:", p2 == p1 or ids(HT_LINK, p2) == p1)
show("sort rating", "https://hypnotube.com/search/spiral/rating/", HT_LINK)
show("sort views", "https://hypnotube.com/search/spiral/views/", HT_LINK)

print("\n### PMVHAVEN")
_, a = show("search q=spiral", "https://pmvhaven.com/search?q=spiral", PMV_LINK)
_, b = show("search q=zzqxjv (nonsense)", "https://pmvhaven.com/search?q=zzqxjv", PMV_LINK)
print("   q filters the list:", a != b)
_, c = show("search tags=Hypno", "https://pmvhaven.com/search?tags=Hypno", PMV_LINK)
_, d = show("search tags=zzqxjv", "https://pmvhaven.com/search?tags=zzqxjv", PMV_LINK)
print("   tags filters the list:", c != d)
for q in ("&page=2", "&sort=views", "&sort=rating", "&sort=newest", "&order=top"):
    _, e = show(f"q=spiral{q}", "https://pmvhaven.com/search?q=spiral" + q, PMV_LINK)
    print("   differs from plain:", e != a)
page, _ = get("https://pmvhaven.com/search?q=spiral")
for key in ("totalResults", "total", "totalCount", "hasMore", "nextPage", "sortBy", "sort"):
    hits = [m.start() for m in re.finditer(f'"{key}"', page)]
    print(f"   NUXT key {key!r}: {len(hits)} hit(s)", page[hits[0]:hits[0] + 60].replace("\n", " ") if hits else "")
print("   sort/order words in page:", sorted(set(re.findall(r'(?:sort|order)[A-Za-z]*=[A-Za-z_]+', page)))[:10])
sys.stdout.flush()
