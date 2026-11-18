"""API keys that sources can use, in one place so a new entry is one line.

Each entry: (source id, settings key, label, hint). The Advanced section builds its fields from this list and
build_source_kwargs() hands each key to its source. No Tk imports, so it can be tested on its own."""

API_KEYS = [
    ("wallhaven", "wallhaven_api_key", "Wallhaven API key",
     "Free: wallhaven.cc > Account > Settings. Unlocks NSFW wallpapers."),
    ("freesound", "freesound_api_key", "Freesound API key",
     "Free: freesound.org > Apiv2 credentials. Needed for Freesound sounds."),
    ("rule34", "rule34_api_key", "Rule34 API key",
     "Rule34 needs a key AND a numeric user ID. rule34.xxx > Account > Options > API Access Credentials: tick \"Generate New Key?\", Save, reopen Options. The box shows &api_key=KEY&user_id=NUMBER. Pasting that whole line works."),
]

# Second half of a key + ID pair: passed to the source as user_id.
API_IDS = [
    ("rule34", "rule34_user_id", "Rule34 user ID (number)", "The account NUMBER shown as user_id= in Options (not your username)."),
]
ALL_FIELDS = API_KEYS + API_IDS      # what the Advanced tab shows and saves


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
    for source_id, setting_key, _label, _hint in API_IDS:
        value = str(settings.get(setting_key, "") or "").strip()
        if value:
            kwargs.setdefault(source_id, {})["user_id"] = value
    return kwargs
