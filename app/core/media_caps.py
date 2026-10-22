"""Download caps per preset: once a preset's folder holds CAP files of one kind (all sites together), no more of
that kind are downloaded for it. 0 = no cap. No Tk, so it can be tested."""
import os

from core.pool_stats import count_media

DEFAULT_CAPS = {"images": 500, "videos": 500, "audio": 50}
SETTING_KEYS = {"images": "max_images_per_preset", "videos": "max_videos_per_preset", "audio": "max_audio_per_preset"}
KIND_OF = {"images": "image", "videos": "video", "audio": "audio"}


def caps_from_settings(settings):
    out = {}
    for kind, key in SETTING_KEYS.items():
        try:
            out[kind] = max(0, int(settings.get(key, DEFAULT_CAPS[kind])))
        except (TypeError, ValueError):
            out[kind] = DEFAULT_CAPS[kind]
    return out


def count_for_folder(folder):
    """{'images': n, 'videos': n, 'audio': n}: everything in the preset's folder, whichever site it came from."""
    images, videos, audio = count_media(folder)
    return {"images": images, "videos": videos, "audio": audio}


def blocked_kinds(counts, caps):
    """Kinds ('image', 'video', 'audio') this preset has filled up."""
    return {KIND_OF[k] for k, cap in (caps or {}).items() if cap and counts.get(k, 0) >= cap}


def site_kinds(category):
    """What a site can give, from its category: video sites only videos, audio sites only audio, the rest pictures
    and videos."""
    return {"Audio": {"audio"}, "Videos": {"video"}}.get(category, {"image", "video"})


def plan(blocked, kinds):
    """(skip, wanted): skip = nothing this site gives is still wanted; wanted = the kinds to keep when only some of
    them are full (None = no restriction)."""
    kinds = set(kinds)
    open_kinds = kinds - set(blocked)
    if not open_kinds:
        return True, None
    return False, (open_kinds if set(blocked) & kinds else None)
