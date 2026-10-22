"""Bridge between the scraper scheduler and Edgeware's on-screen popup
engine. This is a stub: it assumes Edgeware exposes a working call to
pop a single media file to the screen, and we just need to invoke it.
Wire the real import/call in once that hook is confirmed on the
Edgeware side; scheduler code doesn't need to change either way."""


def pop_media(preset, item):
    """Hand one new MediaItem to Edgeware's display engine.

    preset: the Preset this item came from (name, sources list, etc.)
    item:   MediaItem with .file_path, .caption, .post_id, .source_type, etc.

    TODO: replace this body with the real Edgeware popup call, e.g.
        edgeware.display.show(item.file_path, caption=item.caption)
    """
    print(f"[POP] ({preset.name}/{item.source_type}) -> {item.file_path}")


def pop_batch(preset, items):
    for item in items:
        pop_media(preset, item)
