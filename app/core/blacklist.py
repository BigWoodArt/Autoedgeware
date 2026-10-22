"""Blacklisted files: Edgeware's Alt+click moves a popup's file into edgeware_core/data/blacklist/<pack>/.
Anything in that folder must never come back from a scraper. No Tk, so it can be tested.

- names(root): file names currently in the blacklist folder (restore a file by taking it out of there).
- Each preset keeps .post_ids_by_file.json (file name -> post id), so a blacklisted file's post id can be
  looked up and skipped BEFORE downloading, in every preset, even if a preset's seen-list was lost.
- A download whose name is blacklisted anyway is deleted (see scheduler)."""
import glob
import json
import os

MAP_NAME = ".post_ids_by_file.json"


def names(root):
    found = set()
    if not root or not os.path.isdir(root):
        return found
    for _dir, _subdirs, files in os.walk(root):
        found.update(files)
    return found


def _read(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def record(dest_dir, name, post_id):
    """Remember which post a downloaded file came from (callers hold the scheduler's lock)."""
    if not post_id:
        return
    path = os.path.join(dest_dir, MAP_NAME)
    data = _read(path)
    if data.get(name) == post_id:
        return
    data[name] = post_id
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def post_ids(media_root, blocked_names):
    """Post ids of the blacklisted files, looked up in every preset's map."""
    ids = set()
    if not blocked_names:
        return ids
    for path in glob.glob(os.path.join(media_root, "*", MAP_NAME)):
        for name, post_id in _read(path).items():
            if name in blocked_names and post_id:
                ids.add(post_id)
    return ids
