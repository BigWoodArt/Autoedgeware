import os
import sys
import unittest
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from sources.booru_extra_sources import Rule34Source as R

clean = R.clean_credentials


class Rule34Creds(unittest.TestCase):
    def test_pasted_line_splits_into_key_and_id(self):
        for k, u in (("&api_key=LONGKEY&user_id=1234567", ""), ("", "&api_key=LONGKEY&user_id=1234567"),
                     ("api_key=LONGKEY&user_id=1234567", "")):
            self.assertEqual(clean(k, u), ("LONGKEY", "1234567", ""))

    def test_username_as_id_is_rejected(self):
        key, uid, problem = clean("K", "someuser")
        self.assertEqual((key, uid), ("K", ""))
        self.assertIn("NUMBER", problem)

    def test_empty_key_is_flagged(self):
        self.assertEqual(clean("&api_key=&user_id=123", ""), ("", "123", "API key is empty"))
        self.assertEqual(clean("", "123")[2], "API key is empty")

    def test_good_pair_passes_unchanged(self):
        self.assertEqual(clean(" KEY ", " 42 "), ("KEY", "42", ""))

    def test_no_credentials_no_problem(self):
        self.assertEqual(clean("", ""), ("", "", ""))
        self.assertEqual(clean(None, None), ("", "", ""))

    def test_mode_api_with_good_pair_pages_with_bad(self):
        self.assertEqual(R("K", "42")._mode, "dapi")
        self.assertEqual(R("&api_key=K&user_id=42", "")._mode, "dapi")
        for k, u in (("K", "name"), ("", "42"), ("K", ""), ("", "")):
            self.assertEqual(R(k, u)._mode, "html", (k, u))

    def test_error_message_names_the_problem_but_never_the_key(self):
        s = R("SECRETKEY", "name")
        text = s._explain(urllib.error.HTTPError("u", 403, "x", {}, None))
        self.assertIn("NUMBER", text)
        self.assertIn("numeric User ID", text)
        self.assertNotIn("SECRETKEY", text)


if __name__ == "__main__":
    unittest.main()
