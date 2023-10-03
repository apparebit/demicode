from dataclasses import dataclass
from itertools import chain
from pathlib import Path
import unittest

from demicode.codepoint import CodePoint, CodePointSequence
from demicode.model import (
    Age,
    Block,
    BinaryProperty,
    Canonical_Combining_Class,
    CharacterData,
    East_Asian_Width,
    FIRST_SUPPORTED_VERSION,
    General_Category,
    Grapheme_Cluster_Break,
    Indic_Conjunct_Break,
    Indic_Syllabic_Category,
    KNOWN_UCD_VERSIONS,
    Property,
    PropertyId,
    Script,
    Version,
)
from demicode.ucd import UnicodeCharacterDatabase

from test.grapheme_clusters import GRAPHEME_CLUSTER_BREAKS


UCD_PATH = Path(__file__).parents[1] / 'ucd'

PROPERTY_COUNTS: dict[str, dict[PropertyId, tuple[int, int, int]]] = {
    '15.0': {
        BinaryProperty.Emoji: (1_424, 404, 151),
        BinaryProperty.Emoji_Component: (146, 10, 10),
        BinaryProperty.Emoji_Modifier: (5, 1, 1),
        BinaryProperty.Emoji_Modifier_Base: (134, 50, 40),
        BinaryProperty.Emoji_Presentation: (1_205, 282, 81),
        BinaryProperty.Extended_Pictographic: (3_537, 511, 78),
        Age: (288_833, 1_718, 1_718),
        Block: (293_168, 327, 327),
        Canonical_Combining_Class: (286_719, 2_374, 1_196),
        East_Asian_Width: (349_871, 2_575, 1_169),
        General_Category: (288_767, 3_300, 3_300),
        Grapheme_Cluster_Break: (18_003, 1_391, 1_371),
        Indic_Syllabic_Category: (4_639, 922, 775),
        Script: (149_251, 2_191, 952),
    },
    '15.1': {
        BinaryProperty.Emoji: (1_424, 404, 151),
        BinaryProperty.Emoji_Component: (146, 10, 10),
        BinaryProperty.Emoji_Modifier: (5, 1, 1),
        BinaryProperty.Emoji_Modifier_Base: (134, 50, 40),
        BinaryProperty.Emoji_Presentation: (1_205, 282, 81),
        BinaryProperty.Extended_Pictographic: (3_537, 511, 78),
        Age: (289_460, 1_721, 1_721),
        Block: (293_792, 328, 328),
        Canonical_Combining_Class: (287_346, 2_376, 1_196),
        East_Asian_Width: (349_876, 2_578, 1_169),
        General_Category: (289_394, 3_302, 3_302),
        Grapheme_Cluster_Break: (18_003, 1_391, 1_371),
        Indic_Conjunct_Break: (1_130, 202, 201),
        Indic_Syllabic_Category: (4_639, 922, 775),
        Script: (149_878, 2_193, 953),
    },
}

CHARACTER_DATA = (
    CharacterData(
        codepoint=CodePoint.of(0x0023),
        category=General_Category.Other_Punctuation,
        east_asian_width=East_Asian_Width.Narrow,
        age=Age.V1_1,
        name='NUMBER SIGN',
        block=Block.Basic_Latin,
        flags=frozenset([BinaryProperty.Emoji, BinaryProperty.Emoji_Component])
    ),
    CharacterData(
        codepoint=CodePoint.of(0x26A1),
        category=General_Category.Other_Symbol,
        east_asian_width=East_Asian_Width.Wide,
        age=Age.V4_0,
        name='HIGH VOLTAGE SIGN',
        block=Block.Miscellaneous_Symbols,
        flags=frozenset([BinaryProperty.Emoji, BinaryProperty.Emoji_Presentation,
                         BinaryProperty.Extended_Pictographic])
    ),
    CharacterData(
        codepoint=CodePoint.of(0x2763),
        category=General_Category.Other_Symbol,
        east_asian_width=East_Asian_Width.Neutral,
        age=Age.V1_1,
        name='HEAVY HEART EXCLAMATION MARK ORNAMENT',
        block=Block.Dingbats,
        flags=frozenset([BinaryProperty.Emoji, BinaryProperty.Extended_Pictographic])
    ),
    CharacterData(  # An unassigned code point that is an extended pictograph
        codepoint=CodePoint.of(0x1F2FF),
        category=General_Category.Unassigned,
        east_asian_width=East_Asian_Width.Neutral,
        age=Age.Unassigned,
        name=None,
        block=Block.Enclosed_Ideographic_Supplement,
        flags=frozenset([BinaryProperty.Extended_Pictographic])
    ),
)


@dataclass
class ClusterBreakVisualizer:
    """Helper class to visualize grapheme cluster breaking failures."""
    ucd: UnicodeCharacterDatabase
    codepoints: tuple[int,...]
    actual: tuple[int,...]
    expected: tuple[int,...]

    def __str__(self) -> str:
        def ref(cp: int) -> Grapheme_Cluster_Break:
            return self.ucd.grapheme_cluster(CodePoint(cp))

        # Format code points and grapheme cluster properties, with space in between.
        codepoints = [*chain.from_iterable(
            ['', f'U+{cp:04X}/{ref(cp)}'] for cp in self.codepoints)
        ]
        codepoints.append('')

        # Add markers for actual and expected breaks
        for index in self.actual:
            index *= 2
            codepoints[index] = 'a'
        for index in self.expected:
            index *= 2
            codepoints[index] = codepoints[index] + 'e'

        # Return as string
        return ' '.join(codepoints)


class TestProperty(unittest.TestCase):

    def test_known_versions(self):
        for raw_version in KNOWN_UCD_VERSIONS:
            if raw_version < FIRST_SUPPORTED_VERSION:
                continue

            version = Version(*raw_version)
            with self.subTest(version=version):
                ucd = UnicodeCharacterDatabase(UCD_PATH, version).prepare()
                self.assertEqual(ucd.version, version)

                # Check that data is usable by looking up properties.
                data = ucd.lookup(CodePoint.FULL_BLOCK)
                self.assertEqual(data.category, General_Category.Other_Symbol)
                self.assertEqual(data.east_asian_width, East_Asian_Width.Ambiguous)
                self.assertEqual(data.age, Age.V1_1)
                self.assertEqual(data.name, 'FULL BLOCK')
                self.assertEqual(data.block, Block.Block_Elements)

                self.assertEqual(
                    ucd.resolve(CodePoint.FULL_BLOCK, Canonical_Combining_Class),
                    0)
                self.assertEqual(
                    ucd.resolve(CodePoint.FULL_BLOCK, Indic_Syllabic_Category),
                    Indic_Syllabic_Category.Other,
                )
                self.assertEqual(
                    ucd.resolve(CodePoint.FULL_BLOCK, Script),
                    Script.Common
                )

    def check_property_value_counts(
        self,
        expected_counts: dict[PropertyId, tuple[int, int, int]],
        ucd: UnicodeCharacterDatabase,
    ) -> dict[PropertyId, int]:
        property_value_counts: dict[PropertyId, int] = {}

        for property, (expected_points, ranges, max_ranges) in expected_counts.items():
            actual_points, actual_ranges = ucd.count_nondefault_values(property)
            expected_ranges = max_ranges if ucd.is_optimized else ranges

            self.assertEqual(actual_points, expected_points)
            self.assertEqual(actual_ranges, expected_ranges)

            property_value_counts[property] = actual_points

        return property_value_counts

    def test_counts(self) -> None:
        for version in ('15.0', '15.1'):
            with self.subTest(version=version):
                ucd = UnicodeCharacterDatabase(UCD_PATH, version).prepare().validate()
                expected_counts = PROPERTY_COUNTS[version]
                points1 = self.check_property_value_counts(expected_counts, ucd)

                ucd.optimize().validate()
                points2 = self.check_property_value_counts(expected_counts, ucd)

                self.assertDictEqual(points1, points2)

    def test_character_data(self) ->  None:
        ucd = UnicodeCharacterDatabase(UCD_PATH, '15.0').prepare()

        for expected_data in CHARACTER_DATA:
            actual_data = ucd.lookup(expected_data.codepoint)
            self.assertEqual(actual_data, expected_data)

    def test_grapheme_cluster_breaks(self) -> None:
        for version in ('15.0', '15.1'):
            with self.subTest(version=version):
                ucd = UnicodeCharacterDatabase(UCD_PATH, version).prepare()
                for codepoints, expected in GRAPHEME_CLUSTER_BREAKS[version].items():
                    sequence = CodePointSequence.of(*codepoints)
                    actual = tuple(ucd.grapheme_cluster_breaks(sequence))
                    self.assertTupleEqual(
                        actual,
                        expected,
                        ClusterBreakVisualizer(ucd, codepoints, actual, expected)
                    )
