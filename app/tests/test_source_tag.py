import os, tempfile, unittest
from core import source_tag


class SourceTag(unittest.TestCase):
    def test_name(self):
        self.assertEqual(source_tag.tagged_name("cat.jpg", "reddit"), "reddit__cat.jpg")
        self.assertEqual(source_tag.tagged_name("reddit__cat.jpg", "reddit"), "reddit__cat.jpg")
        self.assertEqual(source_tag.tagged_name("cat__reddit.jpg", "reddit"), "cat__reddit.jpg")   # old style stays
        self.assertEqual(source_tag.tagged_name("a.b.mp4", "pmvhaven"), "pmvhaven__a.b.mp4")
        self.assertEqual(source_tag.tagged_name("x", ""), "x")

    def test_rename(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "cat.jpg")
            open(p, "wb").write(b"x")
            q = source_tag.tag_file(p, "gelbooru")
            self.assertEqual(os.path.basename(q), "gelbooru__cat.jpg")
            self.assertTrue(os.path.exists(q) and not os.path.exists(p))
            self.assertEqual(source_tag.tag_file(os.path.join(d, "nope.jpg"), "x"), os.path.join(d, "nope.jpg"))

    def test_long_name(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a" * 200 + ".jpg")
            open(p, "wb").write(b"x")
            q = source_tag.tag_file(p, "reddit")
            self.assertTrue(os.path.basename(q).startswith("reddit__") and os.path.exists(q))


if __name__ == "__main__":
    unittest.main()
