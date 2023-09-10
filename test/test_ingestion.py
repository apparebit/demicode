from pathlib import Path
import unittest

from demicode.model import KNOWN_UCD_VERSIONS, Version
from demicode.ucd import UnicodeCharacterDatabase


UCD_PATH = Path(__file__).parents[1] / 'ucd'

class TestIngestion(unittest.TestCase):

    def test_known_versions(self):
        for raw_version in KNOWN_UCD_VERSIONS[:-1]:
            version = Version(*raw_version)
            with self.subTest(version=version):
                ucd = UnicodeCharacterDatabase(UCD_PATH, version).prepare()
                self.assertEqual(ucd.version, version)
