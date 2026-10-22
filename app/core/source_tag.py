"""Puts the source id in front of a downloaded file's name: cat.jpg from reddit -> reddit__cat.jpg.
Pure file-name logic plus one rename. Never raises: on any problem the file keeps its name."""
import os
import re

SEP = "__"
MAX_PATH = 240          # stay under the Windows path limit


def tagged_name(name, source_type):
    tag = re.sub(r"[^A-Za-z0-9_-]", "", str(source_type or ""))
    stem, ext = os.path.splitext(name)
    if not tag or stem.startswith(tag + SEP) or stem.endswith(SEP + tag):
        return name
    return f"{tag}{SEP}{stem}{ext}"


def tag_file(path, source_type):
    """Renames path on disk; returns the new path (or the old one if nothing changed)."""
    try:
        folder, name = os.path.split(path)
        new = tagged_name(name, source_type)
        if new == name:
            return path
        stem, ext = os.path.splitext(new)
        over = len(os.path.join(folder, new)) - MAX_PATH
        if over > 0:                                  # shorten the original part, keep the tag
            head = stem[:stem.find(SEP) + len(SEP)]
            stem = head + stem[len(head):][:max(8, len(stem) - len(head) - over)]
            new = stem + ext
        target = os.path.join(folder, new)
        os.replace(path, target)
        return target
    except Exception:
        return path
