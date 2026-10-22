import os
import unittest
from unittest import mock

import main


class DefaultPreset(unittest.TestCase):
    def test_fresh_install_has_nature(self):
        with mock.patch.object(main, "PRESETS_PATH", os.path.join(os.devnull, "nope.json")):
            presets = main.ensure_default_presets()
        self.assertEqual([p.name for p in presets], ["Nature"])
        self.assertTrue(presets[0].sources)


if __name__ == "__main__":
    unittest.main()
