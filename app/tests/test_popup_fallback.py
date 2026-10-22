"""Autoedgeware-only: an image roll with no image ready shows a video (and the reverse)."""
import unittest

from core.popup_fallback import choose_kind, make_popup_chooser


class Pack:
    def __init__(self, image=True, video=True):
        self.eligible = {"image": image, "video": video}

    def has_eligible(self, kind):
        return self.eligible[kind]


class State:
    video_number = 0


class Settings:
    max_video = 2


def build(image=True, video=True, videos_open=0, max_video=2):
    shown, logs = [], []
    state, settings = State(), Settings()
    state.video_number, settings.max_video = videos_open, max_video
    img, vid = make_popup_chooser(Pack(image, video), state, settings,
                                  lambda: shown.append("image"), lambda: shown.append("video"), logs.append)
    return img, vid, shown, logs


class Choose(unittest.TestCase):
    def test_wanted_kind_wins_when_usable(self):
        self.assertEqual(choose_kind("image", {"image": True, "video": True}), ("image", False))
        self.assertEqual(choose_kind("video", {"image": True, "video": True}), ("video", False))

    def test_falls_back_to_the_other_kind(self):
        self.assertEqual(choose_kind("image", {"image": False, "video": True}), ("video", True))
        self.assertEqual(choose_kind("video", {"image": True, "video": False}), ("image", True))

    def test_nothing_usable_keeps_the_wanted_kind(self):
        self.assertEqual(choose_kind("image", {"image": False, "video": False}), ("image", False))


class Roll(unittest.TestCase):
    def test_image_roll_with_no_images_shows_a_video_and_says_so(self):
        img, _vid, shown, logs = build(image=False)
        img()
        self.assertEqual(shown, ["video"])
        self.assertIn("no image available", logs[0])

    def test_video_roll_with_no_videos_shows_an_image(self):
        _img, vid, shown, _ = build(video=False)
        vid()
        self.assertEqual(shown, ["image"])

    def test_full_video_slots_skip_the_roll_when_videos_exist(self):
        # videos exist but all slots are busy: nothing pops (no image spam), no video is requested
        _img, vid, shown, _ = build(videos_open=2)
        vid()
        self.assertEqual(shown, [])

    def test_no_videos_at_all_still_falls_back_to_an_image(self):
        _img, vid, shown, _ = build(video=False, videos_open=2)
        vid()
        self.assertEqual(shown, ["image"])

    def test_image_roll_with_no_images_and_full_video_slots_still_asks_for_an_image(self):
        img, _vid, shown, _ = build(image=False, video=False, videos_open=2)
        img()
        self.assertEqual(shown, ["image"])   # lets the popup log its own 'skipped' line

    def test_normal_rolls_are_untouched(self):
        img, vid, shown, logs = build()
        img(); vid()
        self.assertEqual(shown, ["image", "video"])
        self.assertEqual(logs, [])


if __name__ == "__main__":
    unittest.main()
