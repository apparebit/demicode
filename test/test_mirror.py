from pathlib import Path
import unittest

from demicode.mirror import Mirror
from demicode.version import Version, VersionError


UCD_PATH = Path(__file__).parents[1] / 'ucd'


class TestMirror(unittest.TestCase):

    def setUp(self) -> None:
        self.mirror = Mirror.setup(UCD_PATH)
        self.files= self.mirror.files

    def test_files_url(self) -> None:
        with self.assertRaises(ValueError):
            self.files.url('ThisFileDoesNotExist.txt', Version(15, 0, 0))
        with self.assertRaises(VersionError):
            self.files.url('UnicodeData.txt', Version(2, 0 , 0))
        with self.assertRaises(VersionError):
            self.files.url('UnicodeData.txt', Version(14, 9, 0))
        with self.assertRaises(VersionError):
            self.files.url('UnicodeData.txt', Version(665_665, 0, 0))

        self.assertIsNone(
            self.mirror.files.url('IndicSyllabicCategory.txt', Version(5, 0, 0)))
        self.assertIsNone(
            self.files.url('emoji-variation-sequences.txt', Version(9, 0, 0)))
        self.assertIsNone(self.files.url('emoji-test.txt', Version(9, 0, 0)))
        self.assertIsNone(self.files.url('emoji-sequences.txt', Version(8, 0, 0)))
        self.assertIsNone(self.files.url('emoji-data.txt', Version(7, 0, 0)))

        self.assertEqual(
            self.files.url('IndicSyllabicCategory.txt', Version(6, 0, 0)),
            'https://www.unicode.org/Public/6.0.0/ucd/IndicSyllabicCategory.txt'
        )
        self.assertEqual(
            self.files.url('emoji-variation-sequences.txt', Version(10, 0, 0)),
            'https://www.unicode.org/Public/emoji/5.0/emoji-variation-sequences.txt'
        )
        self.assertEqual(
            self.files.url('emoji-test.txt', Version(10, 0, 0)),
            'https://www.unicode.org/Public/emoji/5.0/emoji-test.txt'
        )
        self.assertEqual(
            self.files.url('emoji-sequences.txt', Version(9, 0, 0)),
            'https://www.unicode.org/Public/emoji/3.0/emoji-sequences.txt'
        )
        self.assertEqual(
            self.files.url('emoji-data.txt', Version(8, 0, 0)),
            'https://www.unicode.org/Public/emoji/1.0/emoji-data.txt'
        )
        self.assertEqual(
            self.files.url('emoji-data.txt', Version(13, 0, 0)),
            'https://www.unicode.org/Public/13.0.0/ucd/emoji/emoji-data.txt'
        )
