"""Share presets as small .json files. Imported files are untrusted: only known fields are kept and
sizes are capped."""
import json
import os
from dataclasses import asdict

from ae_settings.preset import Preset
from ae_settings.wizard_logic import safe_name

FORMAT_KEY = "autoedgeware_preset"
MAX_SOURCES = 50
MAX_FILE_BYTES = 1_000_000


def export_preset(preset, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({FORMAT_KEY: 1, "preset": asdict(preset)}, f, indent=2)


def _clean_source(raw, known_types):
    if not isinstance(raw, dict):
        return None
    stype, query = raw.get("source_type"), raw.get("query")
    if not isinstance(stype, str) or not isinstance(query, str) or not query.strip():
        return None
    if known_types is not None and stype not in known_types:
        return None
    entry = {"source_type": stype, "query": query.strip()[:200]}
    if isinstance(raw.get("limit"), int) and 0 < raw["limit"] <= 500:
        entry["limit"] = raw["limit"]
    if raw.get("quality") in ("Good", "Best"):
        entry["quality"] = raw["quality"]
    return entry


def _unique(name, taken):
    if name.lower() not in taken:
        return name
    n = 2
    while f"{name} ({n})".lower() in taken:
        n += 1
    return f"{name} ({n})"


def import_presets(path, existing_names, known_types=None):
    """Returns (presets, skipped_source_count). Raises ValueError for a file that is not a preset file."""
    if os.path.getsize(path) > MAX_FILE_BYTES:
        raise ValueError("That file is too big to be a preset file.")
    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            raise ValueError("That file is not a preset file.")
    if isinstance(data, dict) and FORMAT_KEY in data and isinstance(data.get("preset"), dict):
        raws = [data["preset"]]
    elif isinstance(data, list) and all(isinstance(x, dict) for x in data):
        raws = data                     # a presets.json copied from another install
    else:
        raise ValueError("That file is not a preset file.")
    taken = {n.lower() for n in existing_names}
    out, skipped = [], 0
    for raw in raws[:20]:
        sources_raw = raw.get("sources") if isinstance(raw.get("sources"), list) else []
        sources = []
        for s in sources_raw[:MAX_SOURCES]:
            cleaned = _clean_source(s, known_types)
            if cleaned:
                sources.append(cleaned)
            else:
                skipped += 1
        if not sources:
            continue
        name = _unique(safe_name(str(raw.get("name", "")), "Imported Preset"), taken)
        taken.add(name.lower())
        interval = raw.get("interval_seconds")
        limit = raw.get("limit")
        out.append(Preset(
            name=name, sources=sources,
            interval_seconds=interval if isinstance(interval, int) and 30 <= interval <= 86400 else 300,
            limit=limit if isinstance(limit, int) and 1 <= limit <= 500 else 30,
        ))
    if not out:
        raise ValueError("No usable sources were found in that file.")
    return out, skipped
