"""Which ONE preset the engine runs. Presets are never mixed."""


def pick_preset(presets, settings, argv):
    """--preset NAME if given, else the last one used in the window, else the first."""
    wanted = None
    if "--preset" in argv and argv.index("--preset") + 1 < len(argv):
        wanted = argv[argv.index("--preset") + 1]
    wanted = wanted or settings.get("last_preset")
    for preset in presets:
        if preset.name == wanted:
            return preset
    return presets[0] if presets else None
