import contextlib
import io
from pathlib import Path
import tempfile
import unittest

from import_latin import LATIN_FILE, extract_latin


class ExtractLatinTests(unittest.TestCase):
    def extract(self, path):
        with contextlib.redirect_stdout(io.StringIO()):
            return extract_latin(path)

    def test_split_verse_is_joined_without_renumbering(self):
        lines = self.extract(LATIN_FILE)
        self.assertEqual(len(lines), 9896)
        self.assertEqual(
            lines[10, 62],
            "da, pater, Iliacos Teucris. Tum regia Iuno",
        )
        self.assertTrue(lines[10, 63].startswith("acta furore gravi:"))

    def test_invalid_fragments_and_duplicates_are_rejected(self):
        source = LATIN_FILE.read_text()
        for replacement, error in [
            ('n="62b"', "Invalid continuation"),
            ('n="9999b" part="F"', "Invalid continuation"),
            ('n="62"', "Duplicate line"),
        ]:
            with self.subTest(replacement=replacement), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "latin.xml"
                path.write_text(source.replace('n="62b" part="F"', replacement))
                with self.assertRaisesRegex(ValueError, error):
                    self.extract(path)


if __name__ == "__main__":
    unittest.main()
