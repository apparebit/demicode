#!.venv/bin/python

from demicode.codepoint import CodePoint, CodePointRange, CodePointSequence
from demicode.model import (
    BinaryProperty,
    ComplexProperty,
    CharacterData,
    EastAsianWidth,
    GeneralCategory,
    Version,
)
from demicode.ucd import UCD
from test.grapheme_clusters import GRAPHEME_CLUSTERS


VERBOSE = True
UCD.use_version('15.0.0')
UCD.prepare()
UCD.validate()


# --------------------------------------------------------------------------------------


def test_versions() -> None:
    assert Version.of('13') == Version(13, 0, 0)
    assert Version.of('13').to_emoji() == Version(13, 0, 0)
    assert Version.of('10') == Version(10, 0, 0)
    assert Version.of('10').to_emoji() == Version(5, 0, 0)
    assert Version.of('9').to_emoji() == Version(3, 0, 0)
    assert Version.of('8').to_emoji() == Version(1, 0, 0)
    assert Version.of('7').to_emoji() == Version(0, 7, 0)
    assert Version.of('6').to_emoji() == Version(0, 6, 0)
    assert Version.of('5').to_emoji() == Version(0, 0, 0)
    assert Version.of('4.1').to_emoji() == Version(0, 0, 0)
    print('PASS: UCD and Emoji versions')


# --------------------------------------------------------------------------------------


PROPERTY_COUNTS = {
    BinaryProperty.Emoji: (1_424, 404, 151),
    BinaryProperty.Emoji_Component: (146, 10, 10),
    BinaryProperty.Emoji_Modifier: (5, 1, 1),
    BinaryProperty.Emoji_Modifier_Base: (134, 50, 40),
    BinaryProperty.Emoji_Presentation: (1_205, 282, 81),
    BinaryProperty.Extended_Pictographic: (3_537, 511, 78),
    ComplexProperty.East_Asian_Width: (349_871, 2_575, 1_169),
    ComplexProperty.Grapheme_Cluster_Break: (18_003, 1_391, 1_371),
}


def do_test_counts() -> dict[BinaryProperty | ComplexProperty, int]:
    counts: dict[BinaryProperty | ComplexProperty, int] = {}

    for property, (cp_count, range_count, min_range_count) in PROPERTY_COUNTS.items():
        actual_count, actual_range_count = UCD.count_property_values(property)
        expected_range_count = min_range_count if UCD.is_optimized else range_count
        assert actual_count == cp_count,\
            f'{property.name} has {actual_count} code points, not {cp_count}'
        assert actual_range_count == expected_range_count,\
            f'{property.name} has {actual_range_count} ranges, '\
            f'not {expected_range_count}'

        counts[property] = actual_count
    return counts


def test_counts() -> None:
    counts1 = do_test_counts()
    print(f'PASS: code point and range counts (optimized={UCD.is_optimized})')

    UCD.optimize()
    UCD.validate()

    counts2 = do_test_counts()
    print(f'PASS: code point and range counts (optimized={UCD.is_optimized})')

    for property in counts1:
        value_count1 = counts1[property]
        value_count2 = counts2[property]
        assert value_count1 == value_count2,\
            f'{property.name} has {value_count1} values before '\
            f'and {value_count2} after optimization'
    print(f'PASS: invariant code point counts')


# --------------------------------------------------------------------------------------

RANGE_MERGING = (
    # Merge range and code point
    (ord('r'), ord('t'), ord('p'), None, None),
    (ord('r'), ord('t'), ord('q'), ord('q'), ord('t')),
    (ord('r'), ord('t'), ord('r'), ord('r'), ord('t')),
    (ord('r'), ord('t'), ord('s'), ord('r'), ord('t')),
    (ord('r'), ord('t'), ord('t'), ord('r'), ord('t')),
    (ord('r'), ord('t'), ord('u'), ord('r'), ord('u')),
    (ord('r'), ord('t'), ord('v'), None, None),
    # Merge two ranges
    (ord('r'), ord('t'), ord('a'), ord('p'), None, None),
    (ord('r'), ord('t'), ord('b'), ord('q'), ord('b'), ord('t')),
    (ord('r'), ord('t'), ord('c'), ord('r'), ord('c'), ord('t')),
    (ord('r'), ord('t'), ord('d'), ord('s'), ord('d'), ord('t')),
    (ord('r'), ord('t'), ord('e'), ord('t'), ord('e'), ord('t')),
    (ord('r'), ord('t'), ord('f'), ord('u'), ord('f'), ord('u')),
    (ord('r'), ord('t'), ord('g'), ord('v'), ord('g'), ord('v')),
    (ord('r'), ord('t'), ord('q'), ord('z'), ord('q'), ord('z')),
    (ord('r'), ord('t'), ord('r'), ord('z'), ord('r'), ord('z')),
    (ord('r'), ord('t'), ord('s'), ord('z'), ord('r'), ord('z')),
    (ord('r'), ord('t'), ord('t'), ord('z'), ord('r'), ord('z')),
    (ord('r'), ord('t'), ord('u'), ord('z'), ord('r'), ord('z')),
    (ord('r'), ord('t'), ord('v'), ord('z'), None, None),
)


def test_ranges() -> None:
    for row in RANGE_MERGING:
        range = CodePointRange(CodePoint(row[0]), CodePoint(row[1]))
        if len(row) == 5:
            other = CodePoint(row[2])
        else:
            other = CodePointRange(CodePoint(row[2]), CodePoint(row[3]))

        if row[-1] is None:
            assert not range.can_merge_with(other),\
                f'{range!r} should not combine with {other!r}'
            continue

        result = range.merge(other)
        expected = CodePointRange(CodePoint(row[-2]), CodePoint(row[-1]))
        assert result == expected,\
            f'{range!r} should combine with {other!r} to {expected!r}, not {result!r}'
    print('PASS: range merging')


# --------------------------------------------------------------------------------------


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


def test_unicode_properties() ->  None:
    for expected_data in CHARACTER_DATA:
        actual_data = UCD.lookup(expected_data.codepoint)
        assert actual_data == expected_data,\
              f'actual vs expected properties:\n{actual_data}\n{expected_data}'
    print('PASS: property look up')

    for codepoints, expected in GRAPHEME_CLUSTERS.items():
        sequence = CodePointSequence.of(*codepoints)
        actual = tuple(UCD.grapheme_cluster_breaks(sequence))
        assert actual == expected, (
            f'grapheme cluster breaks for {sequence!r} with properties '
            f'"{UCD.grapheme_cluster_properties(sequence)}" should be {expected} '
            f'but are {actual}'
        )
    print('PASS: grapheme cluster breaks')


# --------------------------------------------------------------------------------------


if __name__ == '__main__':
    test_versions()
    test_counts()
    test_ranges()
    test_unicode_properties()
