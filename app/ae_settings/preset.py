"""A Preset defines one background scrape job: one or more sources
(site + query), how often to refresh, and where results land on disk.
Each source is a plain dict: {"source_type": "reddit", "query": "cats"}.
"""
import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Dict


@dataclass
class Preset:
    name: str                              # folder-safe identifier, e.g. "cats_mild"
    sources: List[Dict[str, str]] = field(default_factory=list)
    interval_seconds: int = 900            # how often to re-poll for new media
    limit: int = 20                        # items pulled per source per cycle
    sort: str = ""
    time_range: str = ""
    randomize: bool = False
    prioritize_images: bool = False
    enabled: bool = True

    def media_dir(self, media_root):
        path = os.path.join(media_root, self.name)
        os.makedirs(path, exist_ok=True)
        return path

    def description(self):
        if not self.sources:
            return "(no sources yet)"
        lines = []
        for s in self.sources:
            notes = []
            if s.get("limit"):
                notes.append(f"limit {s['limit']}")
            if s.get("quality") in ("Good", "Best"):
                notes.append(s["quality"])
            note = f" ({', '.join(notes)})" if notes else ""
            lines.append(f"\u2022 {s.get('source_type', '?')} \u2014 {s.get('query', '')}{note}")
        return "\n".join(lines)


QUALITY_LEVELS = ("Any", "Good", "Best")


def source_entry(source_type, query, limit_text="", quality="Any"):
    """One saved source row. Optional keys are left out when unused, so old presets stay valid:
    limit (a number) and quality ("Good"/"Best"; missing means Any)."""
    entry = {"source_type": source_type, "query": query}
    limit_text = str(limit_text).strip()
    if limit_text.isdigit():
        entry["limit"] = int(limit_text)
    if quality in ("Good", "Best"):
        entry["quality"] = quality
    return entry


def load_presets(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return [Preset(**p) for p in raw]


def save_presets(path, presets):
    with open(path, "w", encoding="utf-8") as f:
        json.dump([asdict(p) for p in presets], f, indent=2)
