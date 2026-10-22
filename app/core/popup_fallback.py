"""When a roll asks for an image but no image is eligible (or the reverse), show the other kind instead,
so popups keep flowing while the downloads and the popup chances disagree.

Also checks the video limit BEFORE a video file is picked. Edgeware's VideoPopup picks first and checks the
limit after, which used up a no-repeat slot (and logged 'shown') for a video that never appeared.
No Edgeware or Tk imports, so it can be tested on its own."""

_OTHER = {"image": "video", "video": "image"}


def choose_kind(wanted, usable):
    """usable: {'image': bool, 'video': bool}. Returns (kind, fell_back)."""
    if usable[wanted]:
        return wanted, False
    if usable[_OTHER[wanted]]:
        return _OTHER[wanted], True
    return wanted, False


def make_popup_chooser(pack, state, settings, show_image, show_video, log=None):
    """Returns (image_roll, video_roll): drop-in replacements for the two RollTarget functions.
    show_image() / show_video() build the real popup."""
    def video_slot_free():
        return state.video_number < settings.max_video

    def usable():
        # A full set of video slots does NOT make video "unusable": the roll is just skipped (below),
        # so a video-heavy setup is not flooded with image popups while its videos are playing.
        return {"image": pack.has_eligible("image"), "video": pack.has_eligible("video")}

    def roll(wanted):
        kind, fell_back = choose_kind(wanted, usable())
        if fell_back and log:
            log(f"POPUP: no {wanted} available right now - showing a {kind} instead")
        if kind == "video":
            if video_slot_free():
                show_video()
        else:
            show_image()          # nothing eligible anywhere: the popup logs its own 'skipped / none yet'

    return (lambda: roll("image")), (lambda: roll("video"))
