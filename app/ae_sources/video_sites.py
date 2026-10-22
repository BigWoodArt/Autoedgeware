"""Hypnotube and PMV Haven for Autoedgeware: the Media Collector files in sources/, plus two small guards.

* A sort the site doesn't know (Autoedgeware's preset sort is meant for Reddit and friends) is ignored.
* PMV Haven: if its web API gives nothing for a plain keyword search, the website pages are read instead
  (needs ffmpeg), so a closed API doesn't leave the row empty."""
from sources.hypnotube_source import HypnoTubeSource as _HypnoTube
from sources.pmvhaven_source import PmvHavenSource as _PmvHaven
from ae_sources.pmvhaven_pages import PmvhavenPageSource, clean_word


class _SortGuard:
    def fetch(self, query, limit, sort, *a, **kw):
        allowed = {params.get("sort") for _key, _label, params in self.order_choices if "sort" in params}
        return super().fetch(query, limit, sort if sort in allowed else "", *a, **kw)


class HypnotubeSource(_SortGuard, _HypnoTube):
    pass


class PmvhavenSource(_SortGuard, _PmvHaven):
    def _resolve_url(self, post, log):
        url = super()._resolve_url(post, log)
        if url and url.split("?")[0].lower().endswith((".m3u8", ".mpd")):    # a stream playlist is not a file
            self.stream_only = getattr(self, "stream_only", 0) + 1
            return None
        return url

    def fetch(self, query, limit, sort, time_range, dest_dir, log, progress, stop_event, *a, **kw):
        self.stream_only = 0
        results = super().fetch(query, limit, sort, time_range, dest_dir, log, progress, stop_event, *a, **kw)
        word = clean_word(query)
        if results or stop_event.is_set() or not word or ":" in word:
            return results
        why = (f"the API only offered stream playlists ({self.stream_only})" if self.stream_only
               else "the API gave nothing")
        log(f"[PMV Haven] {why}; reading the website pages instead", "info")
        return PmvhavenPageSource().fetch(word, limit, "", time_range, dest_dir, log, progress, stop_event, *a, **kw)
