import unittest

from demicode.mirror import ucd_url_of
from demicode.model import Version, VersioningError

class TestMirror(unittest.TestCase):

    def test_versioning_errors(self) -> None:
        with self.assertRaises(VersioningError):
            ucd_url_of('IndicSyllabicCategory.txt', Version(5, 0, 0))

        with self.assertRaises(VersioningError):
            ucd_url_of('emoji-variation-sequences.txt', Version(9, 0, 0))

        with self.assertRaises(VersioningError):
            ucd_url_of('emoji-test.txt', Version(9, 0, 0))

        with self.assertRaises(VersioningError):
            ucd_url_of('emoji-sequences.txt', Version(8, 0, 0))

        with self.assertRaises(VersioningError):
            ucd_url_of('emoji-data.txt', Version(7, 0, 0))

    def test_urls(self) -> None:
        self.assertEqual(
            ucd_url_of('ReadMe.txt', Version(6, 0, 0)),
            'https://www.unicode.org/Public/UCD/latest/ReadMe.txt'
        )

        self.assertEqual(
            ucd_url_of('Indic_Syllabic_Category.txt', Version(6, 0, 0)),
            'https://www.unicode.org/Public/6.0.0/ucd/Indic_Syllabic_Category.txt'
        )

        self.assertEqual(
            ucd_url_of('emoji-variation-sequences.txt', Version(10, 0, 0)),
            'https://www.unicode.org/Public/emoji/5.0/emoji-variation-sequences.txt'
        )

        self.assertEqual(
            ucd_url_of('emoji-test.txt', Version(10, 0, 0)),
            'https://www.unicode.org/Public/emoji/5.0/emoji-test.txt'
        )

        self.assertEqual(
            ucd_url_of('emoji-sequences.txt', Version(9, 0, 0)),
            'https://www.unicode.org/Public/emoji/3.0/emoji-sequences.txt'
        )

        self.assertEqual(
            ucd_url_of('emoji-data.txt', Version(8, 0, 0)),
            'https://www.unicode.org/Public/emoji/1.0/emoji-data.txt'
        )

        self.assertEqual(
            ucd_url_of('emoji-data.txt', Version(13, 0, 0)),
            'https://www.unicode.org/Public/13.0.0/ucd/emoji/emoji-data.txt'
        )
