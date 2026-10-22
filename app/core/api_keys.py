"""API keys that sources can use, in one place so a new entry is one line.

Each entry: (source id, settings key, label, hint). The Advanced section builds its fields from this list and
build_source_kwargs() hands each key to its source. No Tk imports, so it can be tested on its own."""

API_KEYS = [
    ("wallhaven", "wallhaven_api_key", "Wallhaven API key",
     "Free: wallhaven.cc > Account > Settings. Unlocks NSFW wallpapers."),
    ("freesound", "freesound_api_key", "Freesound API key",
     "Free: freesound.org > Apiv2 credentials. Needed for Freesound sounds."),
]


def build_source_kwargs(settings):
    """{source_id: constructor kwargs} from the saved settings. Empty keys are left out."""
    kwargs = {}
    key, uid = settings.get("gelbooru_api_key", ""), settings.get("gelbooru_user_id", "")
    if key and uid:
        kwargs["gelbooru"] = {"api_key": key, "user_id": uid}
    for source_id, setting_key, _label, _hint in API_KEYS:
        value = str(settings.get(setting_key, "") or "").strip()
        if value:
            kwargs[source_id] = {"api_key": value}
    return kwargs
