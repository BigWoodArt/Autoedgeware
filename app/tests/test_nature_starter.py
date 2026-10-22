import unittest

from ae_settings.wizard_logic import nature_sources
from sources import SOURCE_CLASSES


class NatureStarter(unittest.TestCase):
    def test_sources_exist(self):
        for s in nature_sources():
            self.assertIn(s["source_type"], {c.id for c in SOURCE_CLASSES})

    def test_covers_images_and_clips(self):
        types = {s["source_type"] for s in nature_sources()}
        self.assertTrue({"reddit", "wallhaven"} <= types)


if __name__ == "__main__":
    unittest.main()
