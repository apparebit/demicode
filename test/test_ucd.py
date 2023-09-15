from pathlib import Path
import unittest

from demicode.codepoint import CodePoint, CodePointSequence
from demicode.model import (
    BinaryProperty,
    CharacterData,
    EastAsianWidth,
    GeneralCategory,
    IndicSyllabicCategory,
    KNOWN_UCD_VERSIONS,
    Property,
    Script,
    Version,
)
from demicode.ucd import UnicodeCharacterDatabase

from test.grapheme_clusters import GRAPHEME_CLUSTER_BREAKS_15_0


UCD_PATH = Path(__file__).parents[1] / 'ucd'

PROPERTY_COUNTS = {
    BinaryProperty.Emoji: (1_424, 404, 151),
    BinaryProperty.Emoji_Component: (146, 10, 10),
    BinaryProperty.Emoji_Modifier: (5, 1, 1),
    BinaryProperty.Emoji_Modifier_Base: (134, 50, 40),
    BinaryProperty.Emoji_Presentation: (1_205, 282, 81),
    BinaryProperty.Extended_Pictographic: (3_537, 511, 78),
    Property.Canonical_Combining_Class: (286_719, 2_374, 1_196),
    Property.East_Asian_Width: (349_871, 2_575, 1_169),
    Property.General_Category: (288_767, 3_300, 3_300),
    Property.Grapheme_Cluster_Break: (18_003, 1_391, 1_371),
    Property.Indic_Syllabic_Category: (4_639, 922, 775),
    Property.Script: (149_251, 2_191, 952),
}

CHARACTER_DATA = (
    CharacterData(
        codepoint=CodePoint.of(0x0023),
        category=GeneralCategory.Other_Punctuation,
        east_asian_width=EastAsianWidth.Narrow,
        age='1.1',
        name='NUMBER SIGN',
        block='Basic Latin',
        flags=frozenset([BinaryProperty.Emoji, BinaryProperty.Emoji_Component])
    ),
    CharacterData(
        codepoint=CodePoint.of(0x26A1),
        category=GeneralCategory.Other_Symbol,
        east_asian_width=EastAsianWidth.Wide,
        age='4.0',
        name='HIGH VOLTAGE SIGN',
        block='Miscellaneous Symbols',
        flags=frozenset([BinaryProperty.Emoji, BinaryProperty.Emoji_Presentation,
                         BinaryProperty.Extended_Pictographic])
    ),
    CharacterData(
        codepoint=CodePoint.of(0x2763),
        category=GeneralCategory.Other_Symbol,
        east_asian_width=EastAsianWidth.Neutral,
        age='1.1',
        name='HEAVY HEART EXCLAMATION MARK ORNAMENT',
        block='Dingbats',
        flags=frozenset([BinaryProperty.Emoji, BinaryProperty.Extended_Pictographic])
    ),
    CharacterData(  # An unassigned code point that is an extended pictograph
        codepoint=CodePoint.of(0x1F2FF),
        category=GeneralCategory.Unassigned,
        east_asian_width=EastAsianWidth.Neutral,
        age=None,
        name=None,
        block='Enclosed Ideographic Supplement',
        flags=frozenset([BinaryProperty.Extended_Pictographic])
    ),
)

class TestProperty(unittest.TestCase):

    def test_known_versions(self):
        for raw_version in KNOWN_UCD_VERSIONS[:-1]:
            version = Version(*raw_version)
            with self.subTest(version=version):
                ucd = UnicodeCharacterDatabase(UCD_PATH, version).prepare()
                self.assertEqual(ucd.version, version)

                # Check that data is usable by looking up properties.
                self.assertEqual(ucd.age(CodePoint.FULL_BLOCK), '1.1')
                self.assertEqual(ucd.block(CodePoint.FULL_BLOCK), 'Block Elements')
                self.assertEqual(
                    ucd.canonical_combining_class(CodePoint.FULL_BLOCK),
                    0,
                )
                self.assertEqual(
                    ucd.east_asian_width(CodePoint.FULL_BLOCK),
                    EastAsianWidth.Ambiguous,
                )
                self.assertEqual(
                    ucd.general_category(CodePoint.FULL_BLOCK),
                    GeneralCategory.Other_Symbol,
                )
                self.assertEqual(
                    ucd.indic_syllabic_category(CodePoint.FULL_BLOCK),
                    IndicSyllabicCategory.Other,
                )
                self.assertEqual(ucd.name(CodePoint.FULL_BLOCK), 'FULL BLOCK')
                self.assertEqual(ucd.script(CodePoint.FULL_BLOCK), Script.Common)

    def check_property_value_counts(
        self,
        ucd: UnicodeCharacterDatabase,
    ) -> dict[BinaryProperty | Property, int]:
        property_value_counts: dict[BinaryProperty | Property, int] = {}

        for property, counts in PROPERTY_COUNTS.items():
            expected_cp_count, range_count, min_range_count = counts
            actual_count, actual_range_count = ucd.count_values(property)
            expected_range_count = min_range_count if ucd.is_optimized else range_count

            self.assertEqual(actual_count, expected_cp_count)
            self.assertEqual(actual_range_count, expected_range_count)

            property_value_counts[property] = actual_count

        return property_value_counts

    def test_counts(self) -> None:
        ucd = UnicodeCharacterDatabase(UCD_PATH, '15.0').prepare().validate()
        counts1 = self.check_property_value_counts(ucd)

        ucd.optimize().validate()
        counts2 = self.check_property_value_counts(ucd)

        self.assertDictEqual(counts1, counts2)

    def test_unicode_properties(self) ->  None:
        ucd = UnicodeCharacterDatabase(UCD_PATH, '15.0').prepare()

        for expected_data in CHARACTER_DATA:
            actual_data = ucd.lookup(expected_data.codepoint)
            self.assertEqual(actual_data, expected_data)

        for codepoints, expected in GRAPHEME_CLUSTER_BREAKS_15_0.items():
            sequence = CodePointSequence.of(*codepoints)
            actual = tuple(ucd.grapheme_cluster_breaks(sequence))
            self.assertTupleEqual(actual, expected)
