#!.venv/bin/python
import re

from demicode.codepoint import CodePoint, CodePointRange, CodePointSequence
from demicode.mirror import mirror_unicode_data
from demicode.model import BinaryProperty, GeneralCategory, CharacterData, EastAsianWidth
from demicode.ucd import UCD


VERBOSE = True
UCD.use_version('15.0.0')
UCD.prepare()


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


EXPECTED_CHARACTER_DATA = (
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


EXPECTED_COUNTS = {
    BinaryProperty.Dash: 30,
    BinaryProperty.Emoji: 1424,
    BinaryProperty.Emoji_Component: 146,
    BinaryProperty.Emoji_Modifier: 5,
    BinaryProperty.Emoji_Modifier_Base: 134,
    BinaryProperty.Emoji_Presentation: 1205,
    BinaryProperty.Extended_Pictographic: 3537,
    BinaryProperty.Noncharacter_Code_Point: 66,
    BinaryProperty.Variation_Selector: 260,
    BinaryProperty.White_Space: 25,
}


def test_unicode_properties() ->  None:
    for expected_data in EXPECTED_CHARACTER_DATA:
        actual_data = UCD.lookup(expected_data.codepoint)
        assert actual_data == expected_data,\
              f'actual vs expected properties:\n{actual_data}\n{expected_data}'
    print('PASS: property look up')

    for property, expected_count in EXPECTED_COUNTS.items():
        actual_count = UCD.count_property(property)
        assert actual_count == expected_count,\
              f'count {property.name} is {actual_count} but should be {expected_count}'
    print('PASS: number of code points with given property')

    for codepoints, expected in GRAPHEME_BREAKS.items():
        sequence = CodePointSequence.of(*codepoints)
        actual = tuple(UCD.grapheme_cluster_breaks(sequence))
        assert actual == expected, (
            f'grapheme cluster breaks for {sequence!r} with properties '
            f'"{UCD.grapheme_cluster_properties(sequence)}" should be {expected} '
            f'but are {actual}'
        )
    print('PASS: grapheme cluster breaks')


MARK = re.compile(r'[÷×]')

def convert_grapheme_break_test() -> None:
    # Convert into dictionary entries, ready for testing.
    # https://www.unicode.org/Public/UCD/latest/ucd/auxiliary/GraphemeBreakTest.txt
    path = mirror_unicode_data(UCD.path, 'GraphemeBreakTest.txt', UCD.version)
    with open(path, mode='r', encoding='utf8') as file:
        for line in file:
            if line.startswith('#'):
                continue
            spec, _, _ = line.partition('#')
            spec = spec.strip().replace(' ', '')

            codepoints = ', '.join(f'0x{cp}' for cp in MARK.split(spec) if cp)
            marks = ', '.join(
                str(idx) for idx, mark in enumerate(MARK.findall(spec)) if mark == '÷')

            print(f'    ({codepoints}): ({marks}),')


GRAPHEME_BREAKS = {
    (0x0020, 0x0020): (0, 1, 2),
    (0x0020, 0x0308, 0x0020): (0, 2, 3),
    (0x0020, 0x000D): (0, 1, 2),
    (0x0020, 0x0308, 0x000D): (0, 2, 3),
    (0x0020, 0x000A): (0, 1, 2),
    (0x0020, 0x0308, 0x000A): (0, 2, 3),
    (0x0020, 0x0001): (0, 1, 2),
    (0x0020, 0x0308, 0x0001): (0, 2, 3),
    (0x0020, 0x034F): (0, 2),
    (0x0020, 0x0308, 0x034F): (0, 3),
    (0x0020, 0x1F1E6): (0, 1, 2),
    (0x0020, 0x0308, 0x1F1E6): (0, 2, 3),
    (0x0020, 0x0600): (0, 1, 2),
    (0x0020, 0x0308, 0x0600): (0, 2, 3),
    (0x0020, 0x0903): (0, 2),
    (0x0020, 0x0308, 0x0903): (0, 3),
    (0x0020, 0x1100): (0, 1, 2),
    (0x0020, 0x0308, 0x1100): (0, 2, 3),
    (0x0020, 0x1160): (0, 1, 2),
    (0x0020, 0x0308, 0x1160): (0, 2, 3),
    (0x0020, 0x11A8): (0, 1, 2),
    (0x0020, 0x0308, 0x11A8): (0, 2, 3),
    (0x0020, 0xAC00): (0, 1, 2),
    (0x0020, 0x0308, 0xAC00): (0, 2, 3),
    (0x0020, 0xAC01): (0, 1, 2),
    (0x0020, 0x0308, 0xAC01): (0, 2, 3),
    (0x0020, 0x231A): (0, 1, 2),
    (0x0020, 0x0308, 0x231A): (0, 2, 3),
    (0x0020, 0x0300): (0, 2),
    (0x0020, 0x0308, 0x0300): (0, 3),
    (0x0020, 0x200D): (0, 2),
    (0x0020, 0x0308, 0x200D): (0, 3),
    (0x0020, 0x0378): (0, 1, 2),
    (0x0020, 0x0308, 0x0378): (0, 2, 3),
    (0x000D, 0x0020): (0, 1, 2),
    (0x000D, 0x0308, 0x0020): (0, 1, 2, 3),
    (0x000D, 0x000D): (0, 1, 2),
    (0x000D, 0x0308, 0x000D): (0, 1, 2, 3),
    (0x000D, 0x000A): (0, 2),
    (0x000D, 0x0308, 0x000A): (0, 1, 2, 3),
    (0x000D, 0x0001): (0, 1, 2),
    (0x000D, 0x0308, 0x0001): (0, 1, 2, 3),
    (0x000D, 0x034F): (0, 1, 2),
    (0x000D, 0x0308, 0x034F): (0, 1, 3),
    (0x000D, 0x1F1E6): (0, 1, 2),
    (0x000D, 0x0308, 0x1F1E6): (0, 1, 2, 3),
    (0x000D, 0x0600): (0, 1, 2),
    (0x000D, 0x0308, 0x0600): (0, 1, 2, 3),
    (0x000D, 0x0903): (0, 1, 2),
    (0x000D, 0x0308, 0x0903): (0, 1, 3),
    (0x000D, 0x1100): (0, 1, 2),
    (0x000D, 0x0308, 0x1100): (0, 1, 2, 3),
    (0x000D, 0x1160): (0, 1, 2),
    (0x000D, 0x0308, 0x1160): (0, 1, 2, 3),
    (0x000D, 0x11A8): (0, 1, 2),
    (0x000D, 0x0308, 0x11A8): (0, 1, 2, 3),
    (0x000D, 0xAC00): (0, 1, 2),
    (0x000D, 0x0308, 0xAC00): (0, 1, 2, 3),
    (0x000D, 0xAC01): (0, 1, 2),
    (0x000D, 0x0308, 0xAC01): (0, 1, 2, 3),
    (0x000D, 0x231A): (0, 1, 2),
    (0x000D, 0x0308, 0x231A): (0, 1, 2, 3),
    (0x000D, 0x0300): (0, 1, 2),
    (0x000D, 0x0308, 0x0300): (0, 1, 3),
    (0x000D, 0x200D): (0, 1, 2),
    (0x000D, 0x0308, 0x200D): (0, 1, 3),
    (0x000D, 0x0378): (0, 1, 2),
    (0x000D, 0x0308, 0x0378): (0, 1, 2, 3),
    (0x000A, 0x0020): (0, 1, 2),
    (0x000A, 0x0308, 0x0020): (0, 1, 2, 3),
    (0x000A, 0x000D): (0, 1, 2),
    (0x000A, 0x0308, 0x000D): (0, 1, 2, 3),
    (0x000A, 0x000A): (0, 1, 2),
    (0x000A, 0x0308, 0x000A): (0, 1, 2, 3),
    (0x000A, 0x0001): (0, 1, 2),
    (0x000A, 0x0308, 0x0001): (0, 1, 2, 3),
    (0x000A, 0x034F): (0, 1, 2),
    (0x000A, 0x0308, 0x034F): (0, 1, 3),
    (0x000A, 0x1F1E6): (0, 1, 2),
    (0x000A, 0x0308, 0x1F1E6): (0, 1, 2, 3),
    (0x000A, 0x0600): (0, 1, 2),
    (0x000A, 0x0308, 0x0600): (0, 1, 2, 3),
    (0x000A, 0x0903): (0, 1, 2),
    (0x000A, 0x0308, 0x0903): (0, 1, 3),
    (0x000A, 0x1100): (0, 1, 2),
    (0x000A, 0x0308, 0x1100): (0, 1, 2, 3),
    (0x000A, 0x1160): (0, 1, 2),
    (0x000A, 0x0308, 0x1160): (0, 1, 2, 3),
    (0x000A, 0x11A8): (0, 1, 2),
    (0x000A, 0x0308, 0x11A8): (0, 1, 2, 3),
    (0x000A, 0xAC00): (0, 1, 2),
    (0x000A, 0x0308, 0xAC00): (0, 1, 2, 3),
    (0x000A, 0xAC01): (0, 1, 2),
    (0x000A, 0x0308, 0xAC01): (0, 1, 2, 3),
    (0x000A, 0x231A): (0, 1, 2),
    (0x000A, 0x0308, 0x231A): (0, 1, 2, 3),
    (0x000A, 0x0300): (0, 1, 2),
    (0x000A, 0x0308, 0x0300): (0, 1, 3),
    (0x000A, 0x200D): (0, 1, 2),
    (0x000A, 0x0308, 0x200D): (0, 1, 3),
    (0x000A, 0x0378): (0, 1, 2),
    (0x000A, 0x0308, 0x0378): (0, 1, 2, 3),
    (0x0001, 0x0020): (0, 1, 2),
    (0x0001, 0x0308, 0x0020): (0, 1, 2, 3),
    (0x0001, 0x000D): (0, 1, 2),
    (0x0001, 0x0308, 0x000D): (0, 1, 2, 3),
    (0x0001, 0x000A): (0, 1, 2),
    (0x0001, 0x0308, 0x000A): (0, 1, 2, 3),
    (0x0001, 0x0001): (0, 1, 2),
    (0x0001, 0x0308, 0x0001): (0, 1, 2, 3),
    (0x0001, 0x034F): (0, 1, 2),
    (0x0001, 0x0308, 0x034F): (0, 1, 3),
    (0x0001, 0x1F1E6): (0, 1, 2),
    (0x0001, 0x0308, 0x1F1E6): (0, 1, 2, 3),
    (0x0001, 0x0600): (0, 1, 2),
    (0x0001, 0x0308, 0x0600): (0, 1, 2, 3),
    (0x0001, 0x0903): (0, 1, 2),
    (0x0001, 0x0308, 0x0903): (0, 1, 3),
    (0x0001, 0x1100): (0, 1, 2),
    (0x0001, 0x0308, 0x1100): (0, 1, 2, 3),
    (0x0001, 0x1160): (0, 1, 2),
    (0x0001, 0x0308, 0x1160): (0, 1, 2, 3),
    (0x0001, 0x11A8): (0, 1, 2),
    (0x0001, 0x0308, 0x11A8): (0, 1, 2, 3),
    (0x0001, 0xAC00): (0, 1, 2),
    (0x0001, 0x0308, 0xAC00): (0, 1, 2, 3),
    (0x0001, 0xAC01): (0, 1, 2),
    (0x0001, 0x0308, 0xAC01): (0, 1, 2, 3),
    (0x0001, 0x231A): (0, 1, 2),
    (0x0001, 0x0308, 0x231A): (0, 1, 2, 3),
    (0x0001, 0x0300): (0, 1, 2),
    (0x0001, 0x0308, 0x0300): (0, 1, 3),
    (0x0001, 0x200D): (0, 1, 2),
    (0x0001, 0x0308, 0x200D): (0, 1, 3),
    (0x0001, 0x0378): (0, 1, 2),
    (0x0001, 0x0308, 0x0378): (0, 1, 2, 3),
    (0x034F, 0x0020): (0, 1, 2),
    (0x034F, 0x0308, 0x0020): (0, 2, 3),
    (0x034F, 0x000D): (0, 1, 2),
    (0x034F, 0x0308, 0x000D): (0, 2, 3),
    (0x034F, 0x000A): (0, 1, 2),
    (0x034F, 0x0308, 0x000A): (0, 2, 3),
    (0x034F, 0x0001): (0, 1, 2),
    (0x034F, 0x0308, 0x0001): (0, 2, 3),
    (0x034F, 0x034F): (0, 2),
    (0x034F, 0x0308, 0x034F): (0, 3),
    (0x034F, 0x1F1E6): (0, 1, 2),
    (0x034F, 0x0308, 0x1F1E6): (0, 2, 3),
    (0x034F, 0x0600): (0, 1, 2),
    (0x034F, 0x0308, 0x0600): (0, 2, 3),
    (0x034F, 0x0903): (0, 2),
    (0x034F, 0x0308, 0x0903): (0, 3),
    (0x034F, 0x1100): (0, 1, 2),
    (0x034F, 0x0308, 0x1100): (0, 2, 3),
    (0x034F, 0x1160): (0, 1, 2),
    (0x034F, 0x0308, 0x1160): (0, 2, 3),
    (0x034F, 0x11A8): (0, 1, 2),
    (0x034F, 0x0308, 0x11A8): (0, 2, 3),
    (0x034F, 0xAC00): (0, 1, 2),
    (0x034F, 0x0308, 0xAC00): (0, 2, 3),
    (0x034F, 0xAC01): (0, 1, 2),
    (0x034F, 0x0308, 0xAC01): (0, 2, 3),
    (0x034F, 0x231A): (0, 1, 2),
    (0x034F, 0x0308, 0x231A): (0, 2, 3),
    (0x034F, 0x0300): (0, 2),
    (0x034F, 0x0308, 0x0300): (0, 3),
    (0x034F, 0x200D): (0, 2),
    (0x034F, 0x0308, 0x200D): (0, 3),
    (0x034F, 0x0378): (0, 1, 2),
    (0x034F, 0x0308, 0x0378): (0, 2, 3),
    (0x1F1E6, 0x0020): (0, 1, 2),
    (0x1F1E6, 0x0308, 0x0020): (0, 2, 3),
    (0x1F1E6, 0x000D): (0, 1, 2),
    (0x1F1E6, 0x0308, 0x000D): (0, 2, 3),
    (0x1F1E6, 0x000A): (0, 1, 2),
    (0x1F1E6, 0x0308, 0x000A): (0, 2, 3),
    (0x1F1E6, 0x0001): (0, 1, 2),
    (0x1F1E6, 0x0308, 0x0001): (0, 2, 3),
    (0x1F1E6, 0x034F): (0, 2),
    (0x1F1E6, 0x0308, 0x034F): (0, 3),
    (0x1F1E6, 0x1F1E6): (0, 2),
    (0x1F1E6, 0x0308, 0x1F1E6): (0, 2, 3),
    (0x1F1E6, 0x0600): (0, 1, 2),
    (0x1F1E6, 0x0308, 0x0600): (0, 2, 3),
    (0x1F1E6, 0x0903): (0, 2),
    (0x1F1E6, 0x0308, 0x0903): (0, 3),
    (0x1F1E6, 0x1100): (0, 1, 2),
    (0x1F1E6, 0x0308, 0x1100): (0, 2, 3),
    (0x1F1E6, 0x1160): (0, 1, 2),
    (0x1F1E6, 0x0308, 0x1160): (0, 2, 3),
    (0x1F1E6, 0x11A8): (0, 1, 2),
    (0x1F1E6, 0x0308, 0x11A8): (0, 2, 3),
    (0x1F1E6, 0xAC00): (0, 1, 2),
    (0x1F1E6, 0x0308, 0xAC00): (0, 2, 3),
    (0x1F1E6, 0xAC01): (0, 1, 2),
    (0x1F1E6, 0x0308, 0xAC01): (0, 2, 3),
    (0x1F1E6, 0x231A): (0, 1, 2),
    (0x1F1E6, 0x0308, 0x231A): (0, 2, 3),
    (0x1F1E6, 0x0300): (0, 2),
    (0x1F1E6, 0x0308, 0x0300): (0, 3),
    (0x1F1E6, 0x200D): (0, 2),
    (0x1F1E6, 0x0308, 0x200D): (0, 3),
    (0x1F1E6, 0x0378): (0, 1, 2),
    (0x1F1E6, 0x0308, 0x0378): (0, 2, 3),
    (0x0600, 0x0020): (0, 2),
    (0x0600, 0x0308, 0x0020): (0, 2, 3),
    (0x0600, 0x000D): (0, 1, 2),
    (0x0600, 0x0308, 0x000D): (0, 2, 3),
    (0x0600, 0x000A): (0, 1, 2),
    (0x0600, 0x0308, 0x000A): (0, 2, 3),
    (0x0600, 0x0001): (0, 1, 2),
    (0x0600, 0x0308, 0x0001): (0, 2, 3),
    (0x0600, 0x034F): (0, 2),
    (0x0600, 0x0308, 0x034F): (0, 3),
    (0x0600, 0x1F1E6): (0, 2),
    (0x0600, 0x0308, 0x1F1E6): (0, 2, 3),
    (0x0600, 0x0600): (0, 2),
    (0x0600, 0x0308, 0x0600): (0, 2, 3),
    (0x0600, 0x0903): (0, 2),
    (0x0600, 0x0308, 0x0903): (0, 3),
    (0x0600, 0x1100): (0, 2),
    (0x0600, 0x0308, 0x1100): (0, 2, 3),
    (0x0600, 0x1160): (0, 2),
    (0x0600, 0x0308, 0x1160): (0, 2, 3),
    (0x0600, 0x11A8): (0, 2),
    (0x0600, 0x0308, 0x11A8): (0, 2, 3),
    (0x0600, 0xAC00): (0, 2),
    (0x0600, 0x0308, 0xAC00): (0, 2, 3),
    (0x0600, 0xAC01): (0, 2),
    (0x0600, 0x0308, 0xAC01): (0, 2, 3),
    (0x0600, 0x231A): (0, 2),
    (0x0600, 0x0308, 0x231A): (0, 2, 3),
    (0x0600, 0x0300): (0, 2),
    (0x0600, 0x0308, 0x0300): (0, 3),
    (0x0600, 0x200D): (0, 2),
    (0x0600, 0x0308, 0x200D): (0, 3),
    (0x0600, 0x0378): (0, 2),
    (0x0600, 0x0308, 0x0378): (0, 2, 3),
    (0x0903, 0x0020): (0, 1, 2),
    (0x0903, 0x0308, 0x0020): (0, 2, 3),
    (0x0903, 0x000D): (0, 1, 2),
    (0x0903, 0x0308, 0x000D): (0, 2, 3),
    (0x0903, 0x000A): (0, 1, 2),
    (0x0903, 0x0308, 0x000A): (0, 2, 3),
    (0x0903, 0x0001): (0, 1, 2),
    (0x0903, 0x0308, 0x0001): (0, 2, 3),
    (0x0903, 0x034F): (0, 2),
    (0x0903, 0x0308, 0x034F): (0, 3),
    (0x0903, 0x1F1E6): (0, 1, 2),
    (0x0903, 0x0308, 0x1F1E6): (0, 2, 3),
    (0x0903, 0x0600): (0, 1, 2),
    (0x0903, 0x0308, 0x0600): (0, 2, 3),
    (0x0903, 0x0903): (0, 2),
    (0x0903, 0x0308, 0x0903): (0, 3),
    (0x0903, 0x1100): (0, 1, 2),
    (0x0903, 0x0308, 0x1100): (0, 2, 3),
    (0x0903, 0x1160): (0, 1, 2),
    (0x0903, 0x0308, 0x1160): (0, 2, 3),
    (0x0903, 0x11A8): (0, 1, 2),
    (0x0903, 0x0308, 0x11A8): (0, 2, 3),
    (0x0903, 0xAC00): (0, 1, 2),
    (0x0903, 0x0308, 0xAC00): (0, 2, 3),
    (0x0903, 0xAC01): (0, 1, 2),
    (0x0903, 0x0308, 0xAC01): (0, 2, 3),
    (0x0903, 0x231A): (0, 1, 2),
    (0x0903, 0x0308, 0x231A): (0, 2, 3),
    (0x0903, 0x0300): (0, 2),
    (0x0903, 0x0308, 0x0300): (0, 3),
    (0x0903, 0x200D): (0, 2),
    (0x0903, 0x0308, 0x200D): (0, 3),
    (0x0903, 0x0378): (0, 1, 2),
    (0x0903, 0x0308, 0x0378): (0, 2, 3),
    (0x1100, 0x0020): (0, 1, 2),
    (0x1100, 0x0308, 0x0020): (0, 2, 3),
    (0x1100, 0x000D): (0, 1, 2),
    (0x1100, 0x0308, 0x000D): (0, 2, 3),
    (0x1100, 0x000A): (0, 1, 2),
    (0x1100, 0x0308, 0x000A): (0, 2, 3),
    (0x1100, 0x0001): (0, 1, 2),
    (0x1100, 0x0308, 0x0001): (0, 2, 3),
    (0x1100, 0x034F): (0, 2),
    (0x1100, 0x0308, 0x034F): (0, 3),
    (0x1100, 0x1F1E6): (0, 1, 2),
    (0x1100, 0x0308, 0x1F1E6): (0, 2, 3),
    (0x1100, 0x0600): (0, 1, 2),
    (0x1100, 0x0308, 0x0600): (0, 2, 3),
    (0x1100, 0x0903): (0, 2),
    (0x1100, 0x0308, 0x0903): (0, 3),
    (0x1100, 0x1100): (0, 2),
    (0x1100, 0x0308, 0x1100): (0, 2, 3),
    (0x1100, 0x1160): (0, 2),
    (0x1100, 0x0308, 0x1160): (0, 2, 3),
    (0x1100, 0x11A8): (0, 1, 2),
    (0x1100, 0x0308, 0x11A8): (0, 2, 3),
    (0x1100, 0xAC00): (0, 2),
    (0x1100, 0x0308, 0xAC00): (0, 2, 3),
    (0x1100, 0xAC01): (0, 2),
    (0x1100, 0x0308, 0xAC01): (0, 2, 3),
    (0x1100, 0x231A): (0, 1, 2),
    (0x1100, 0x0308, 0x231A): (0, 2, 3),
    (0x1100, 0x0300): (0, 2),
    (0x1100, 0x0308, 0x0300): (0, 3),
    (0x1100, 0x200D): (0, 2),
    (0x1100, 0x0308, 0x200D): (0, 3),
    (0x1100, 0x0378): (0, 1, 2),
    (0x1100, 0x0308, 0x0378): (0, 2, 3),
    (0x1160, 0x0020): (0, 1, 2),
    (0x1160, 0x0308, 0x0020): (0, 2, 3),
    (0x1160, 0x000D): (0, 1, 2),
    (0x1160, 0x0308, 0x000D): (0, 2, 3),
    (0x1160, 0x000A): (0, 1, 2),
    (0x1160, 0x0308, 0x000A): (0, 2, 3),
    (0x1160, 0x0001): (0, 1, 2),
    (0x1160, 0x0308, 0x0001): (0, 2, 3),
    (0x1160, 0x034F): (0, 2),
    (0x1160, 0x0308, 0x034F): (0, 3),
    (0x1160, 0x1F1E6): (0, 1, 2),
    (0x1160, 0x0308, 0x1F1E6): (0, 2, 3),
    (0x1160, 0x0600): (0, 1, 2),
    (0x1160, 0x0308, 0x0600): (0, 2, 3),
    (0x1160, 0x0903): (0, 2),
    (0x1160, 0x0308, 0x0903): (0, 3),
    (0x1160, 0x1100): (0, 1, 2),
    (0x1160, 0x0308, 0x1100): (0, 2, 3),
    (0x1160, 0x1160): (0, 2),
    (0x1160, 0x0308, 0x1160): (0, 2, 3),
    (0x1160, 0x11A8): (0, 2),
    (0x1160, 0x0308, 0x11A8): (0, 2, 3),
    (0x1160, 0xAC00): (0, 1, 2),
    (0x1160, 0x0308, 0xAC00): (0, 2, 3),
    (0x1160, 0xAC01): (0, 1, 2),
    (0x1160, 0x0308, 0xAC01): (0, 2, 3),
    (0x1160, 0x231A): (0, 1, 2),
    (0x1160, 0x0308, 0x231A): (0, 2, 3),
    (0x1160, 0x0300): (0, 2),
    (0x1160, 0x0308, 0x0300): (0, 3),
    (0x1160, 0x200D): (0, 2),
    (0x1160, 0x0308, 0x200D): (0, 3),
    (0x1160, 0x0378): (0, 1, 2),
    (0x1160, 0x0308, 0x0378): (0, 2, 3),
    (0x11A8, 0x0020): (0, 1, 2),
    (0x11A8, 0x0308, 0x0020): (0, 2, 3),
    (0x11A8, 0x000D): (0, 1, 2),
    (0x11A8, 0x0308, 0x000D): (0, 2, 3),
    (0x11A8, 0x000A): (0, 1, 2),
    (0x11A8, 0x0308, 0x000A): (0, 2, 3),
    (0x11A8, 0x0001): (0, 1, 2),
    (0x11A8, 0x0308, 0x0001): (0, 2, 3),
    (0x11A8, 0x034F): (0, 2),
    (0x11A8, 0x0308, 0x034F): (0, 3),
    (0x11A8, 0x1F1E6): (0, 1, 2),
    (0x11A8, 0x0308, 0x1F1E6): (0, 2, 3),
    (0x11A8, 0x0600): (0, 1, 2),
    (0x11A8, 0x0308, 0x0600): (0, 2, 3),
    (0x11A8, 0x0903): (0, 2),
    (0x11A8, 0x0308, 0x0903): (0, 3),
    (0x11A8, 0x1100): (0, 1, 2),
    (0x11A8, 0x0308, 0x1100): (0, 2, 3),
    (0x11A8, 0x1160): (0, 1, 2),
    (0x11A8, 0x0308, 0x1160): (0, 2, 3),
    (0x11A8, 0x11A8): (0, 2),
    (0x11A8, 0x0308, 0x11A8): (0, 2, 3),
    (0x11A8, 0xAC00): (0, 1, 2),
    (0x11A8, 0x0308, 0xAC00): (0, 2, 3),
    (0x11A8, 0xAC01): (0, 1, 2),
    (0x11A8, 0x0308, 0xAC01): (0, 2, 3),
    (0x11A8, 0x231A): (0, 1, 2),
    (0x11A8, 0x0308, 0x231A): (0, 2, 3),
    (0x11A8, 0x0300): (0, 2),
    (0x11A8, 0x0308, 0x0300): (0, 3),
    (0x11A8, 0x200D): (0, 2),
    (0x11A8, 0x0308, 0x200D): (0, 3),
    (0x11A8, 0x0378): (0, 1, 2),
    (0x11A8, 0x0308, 0x0378): (0, 2, 3),
    (0xAC00, 0x0020): (0, 1, 2),
    (0xAC00, 0x0308, 0x0020): (0, 2, 3),
    (0xAC00, 0x000D): (0, 1, 2),
    (0xAC00, 0x0308, 0x000D): (0, 2, 3),
    (0xAC00, 0x000A): (0, 1, 2),
    (0xAC00, 0x0308, 0x000A): (0, 2, 3),
    (0xAC00, 0x0001): (0, 1, 2),
    (0xAC00, 0x0308, 0x0001): (0, 2, 3),
    (0xAC00, 0x034F): (0, 2),
    (0xAC00, 0x0308, 0x034F): (0, 3),
    (0xAC00, 0x1F1E6): (0, 1, 2),
    (0xAC00, 0x0308, 0x1F1E6): (0, 2, 3),
    (0xAC00, 0x0600): (0, 1, 2),
    (0xAC00, 0x0308, 0x0600): (0, 2, 3),
    (0xAC00, 0x0903): (0, 2),
    (0xAC00, 0x0308, 0x0903): (0, 3),
    (0xAC00, 0x1100): (0, 1, 2),
    (0xAC00, 0x0308, 0x1100): (0, 2, 3),
    (0xAC00, 0x1160): (0, 2),
    (0xAC00, 0x0308, 0x1160): (0, 2, 3),
    (0xAC00, 0x11A8): (0, 2),
    (0xAC00, 0x0308, 0x11A8): (0, 2, 3),
    (0xAC00, 0xAC00): (0, 1, 2),
    (0xAC00, 0x0308, 0xAC00): (0, 2, 3),
    (0xAC00, 0xAC01): (0, 1, 2),
    (0xAC00, 0x0308, 0xAC01): (0, 2, 3),
    (0xAC00, 0x231A): (0, 1, 2),
    (0xAC00, 0x0308, 0x231A): (0, 2, 3),
    (0xAC00, 0x0300): (0, 2),
    (0xAC00, 0x0308, 0x0300): (0, 3),
    (0xAC00, 0x200D): (0, 2),
    (0xAC00, 0x0308, 0x200D): (0, 3),
    (0xAC00, 0x0378): (0, 1, 2),
    (0xAC00, 0x0308, 0x0378): (0, 2, 3),
    (0xAC01, 0x0020): (0, 1, 2),
    (0xAC01, 0x0308, 0x0020): (0, 2, 3),
    (0xAC01, 0x000D): (0, 1, 2),
    (0xAC01, 0x0308, 0x000D): (0, 2, 3),
    (0xAC01, 0x000A): (0, 1, 2),
    (0xAC01, 0x0308, 0x000A): (0, 2, 3),
    (0xAC01, 0x0001): (0, 1, 2),
    (0xAC01, 0x0308, 0x0001): (0, 2, 3),
    (0xAC01, 0x034F): (0, 2),
    (0xAC01, 0x0308, 0x034F): (0, 3),
    (0xAC01, 0x1F1E6): (0, 1, 2),
    (0xAC01, 0x0308, 0x1F1E6): (0, 2, 3),
    (0xAC01, 0x0600): (0, 1, 2),
    (0xAC01, 0x0308, 0x0600): (0, 2, 3),
    (0xAC01, 0x0903): (0, 2),
    (0xAC01, 0x0308, 0x0903): (0, 3),
    (0xAC01, 0x1100): (0, 1, 2),
    (0xAC01, 0x0308, 0x1100): (0, 2, 3),
    (0xAC01, 0x1160): (0, 1, 2),
    (0xAC01, 0x0308, 0x1160): (0, 2, 3),
    (0xAC01, 0x11A8): (0, 2),
    (0xAC01, 0x0308, 0x11A8): (0, 2, 3),
    (0xAC01, 0xAC00): (0, 1, 2),
    (0xAC01, 0x0308, 0xAC00): (0, 2, 3),
    (0xAC01, 0xAC01): (0, 1, 2),
    (0xAC01, 0x0308, 0xAC01): (0, 2, 3),
    (0xAC01, 0x231A): (0, 1, 2),
    (0xAC01, 0x0308, 0x231A): (0, 2, 3),
    (0xAC01, 0x0300): (0, 2),
    (0xAC01, 0x0308, 0x0300): (0, 3),
    (0xAC01, 0x200D): (0, 2),
    (0xAC01, 0x0308, 0x200D): (0, 3),
    (0xAC01, 0x0378): (0, 1, 2),
    (0xAC01, 0x0308, 0x0378): (0, 2, 3),
    (0x231A, 0x0020): (0, 1, 2),
    (0x231A, 0x0308, 0x0020): (0, 2, 3),
    (0x231A, 0x000D): (0, 1, 2),
    (0x231A, 0x0308, 0x000D): (0, 2, 3),
    (0x231A, 0x000A): (0, 1, 2),
    (0x231A, 0x0308, 0x000A): (0, 2, 3),
    (0x231A, 0x0001): (0, 1, 2),
    (0x231A, 0x0308, 0x0001): (0, 2, 3),
    (0x231A, 0x034F): (0, 2),
    (0x231A, 0x0308, 0x034F): (0, 3),
    (0x231A, 0x1F1E6): (0, 1, 2),
    (0x231A, 0x0308, 0x1F1E6): (0, 2, 3),
    (0x231A, 0x0600): (0, 1, 2),
    (0x231A, 0x0308, 0x0600): (0, 2, 3),
    (0x231A, 0x0903): (0, 2),
    (0x231A, 0x0308, 0x0903): (0, 3),
    (0x231A, 0x1100): (0, 1, 2),
    (0x231A, 0x0308, 0x1100): (0, 2, 3),
    (0x231A, 0x1160): (0, 1, 2),
    (0x231A, 0x0308, 0x1160): (0, 2, 3),
    (0x231A, 0x11A8): (0, 1, 2),
    (0x231A, 0x0308, 0x11A8): (0, 2, 3),
    (0x231A, 0xAC00): (0, 1, 2),
    (0x231A, 0x0308, 0xAC00): (0, 2, 3),
    (0x231A, 0xAC01): (0, 1, 2),
    (0x231A, 0x0308, 0xAC01): (0, 2, 3),
    (0x231A, 0x231A): (0, 1, 2),
    (0x231A, 0x0308, 0x231A): (0, 2, 3),
    (0x231A, 0x0300): (0, 2),
    (0x231A, 0x0308, 0x0300): (0, 3),
    (0x231A, 0x200D): (0, 2),
    (0x231A, 0x0308, 0x200D): (0, 3),
    (0x231A, 0x0378): (0, 1, 2),
    (0x231A, 0x0308, 0x0378): (0, 2, 3),
    (0x0300, 0x0020): (0, 1, 2),
    (0x0300, 0x0308, 0x0020): (0, 2, 3),
    (0x0300, 0x000D): (0, 1, 2),
    (0x0300, 0x0308, 0x000D): (0, 2, 3),
    (0x0300, 0x000A): (0, 1, 2),
    (0x0300, 0x0308, 0x000A): (0, 2, 3),
    (0x0300, 0x0001): (0, 1, 2),
    (0x0300, 0x0308, 0x0001): (0, 2, 3),
    (0x0300, 0x034F): (0, 2),
    (0x0300, 0x0308, 0x034F): (0, 3),
    (0x0300, 0x1F1E6): (0, 1, 2),
    (0x0300, 0x0308, 0x1F1E6): (0, 2, 3),
    (0x0300, 0x0600): (0, 1, 2),
    (0x0300, 0x0308, 0x0600): (0, 2, 3),
    (0x0300, 0x0903): (0, 2),
    (0x0300, 0x0308, 0x0903): (0, 3),
    (0x0300, 0x1100): (0, 1, 2),
    (0x0300, 0x0308, 0x1100): (0, 2, 3),
    (0x0300, 0x1160): (0, 1, 2),
    (0x0300, 0x0308, 0x1160): (0, 2, 3),
    (0x0300, 0x11A8): (0, 1, 2),
    (0x0300, 0x0308, 0x11A8): (0, 2, 3),
    (0x0300, 0xAC00): (0, 1, 2),
    (0x0300, 0x0308, 0xAC00): (0, 2, 3),
    (0x0300, 0xAC01): (0, 1, 2),
    (0x0300, 0x0308, 0xAC01): (0, 2, 3),
    (0x0300, 0x231A): (0, 1, 2),
    (0x0300, 0x0308, 0x231A): (0, 2, 3),
    (0x0300, 0x0300): (0, 2),
    (0x0300, 0x0308, 0x0300): (0, 3),
    (0x0300, 0x200D): (0, 2),
    (0x0300, 0x0308, 0x200D): (0, 3),
    (0x0300, 0x0378): (0, 1, 2),
    (0x0300, 0x0308, 0x0378): (0, 2, 3),
    (0x200D, 0x0020): (0, 1, 2),
    (0x200D, 0x0308, 0x0020): (0, 2, 3),
    (0x200D, 0x000D): (0, 1, 2),
    (0x200D, 0x0308, 0x000D): (0, 2, 3),
    (0x200D, 0x000A): (0, 1, 2),
    (0x200D, 0x0308, 0x000A): (0, 2, 3),
    (0x200D, 0x0001): (0, 1, 2),
    (0x200D, 0x0308, 0x0001): (0, 2, 3),
    (0x200D, 0x034F): (0, 2),
    (0x200D, 0x0308, 0x034F): (0, 3),
    (0x200D, 0x1F1E6): (0, 1, 2),
    (0x200D, 0x0308, 0x1F1E6): (0, 2, 3),
    (0x200D, 0x0600): (0, 1, 2),
    (0x200D, 0x0308, 0x0600): (0, 2, 3),
    (0x200D, 0x0903): (0, 2),
    (0x200D, 0x0308, 0x0903): (0, 3),
    (0x200D, 0x1100): (0, 1, 2),
    (0x200D, 0x0308, 0x1100): (0, 2, 3),
    (0x200D, 0x1160): (0, 1, 2),
    (0x200D, 0x0308, 0x1160): (0, 2, 3),
    (0x200D, 0x11A8): (0, 1, 2),
    (0x200D, 0x0308, 0x11A8): (0, 2, 3),
    (0x200D, 0xAC00): (0, 1, 2),
    (0x200D, 0x0308, 0xAC00): (0, 2, 3),
    (0x200D, 0xAC01): (0, 1, 2),
    (0x200D, 0x0308, 0xAC01): (0, 2, 3),
    (0x200D, 0x231A): (0, 1, 2),
    (0x200D, 0x0308, 0x231A): (0, 2, 3),
    (0x200D, 0x0300): (0, 2),
    (0x200D, 0x0308, 0x0300): (0, 3),
    (0x200D, 0x200D): (0, 2),
    (0x200D, 0x0308, 0x200D): (0, 3),
    (0x200D, 0x0378): (0, 1, 2),
    (0x200D, 0x0308, 0x0378): (0, 2, 3),
    (0x0378, 0x0020): (0, 1, 2),
    (0x0378, 0x0308, 0x0020): (0, 2, 3),
    (0x0378, 0x000D): (0, 1, 2),
    (0x0378, 0x0308, 0x000D): (0, 2, 3),
    (0x0378, 0x000A): (0, 1, 2),
    (0x0378, 0x0308, 0x000A): (0, 2, 3),
    (0x0378, 0x0001): (0, 1, 2),
    (0x0378, 0x0308, 0x0001): (0, 2, 3),
    (0x0378, 0x034F): (0, 2),
    (0x0378, 0x0308, 0x034F): (0, 3),
    (0x0378, 0x1F1E6): (0, 1, 2),
    (0x0378, 0x0308, 0x1F1E6): (0, 2, 3),
    (0x0378, 0x0600): (0, 1, 2),
    (0x0378, 0x0308, 0x0600): (0, 2, 3),
    (0x0378, 0x0903): (0, 2),
    (0x0378, 0x0308, 0x0903): (0, 3),
    (0x0378, 0x1100): (0, 1, 2),
    (0x0378, 0x0308, 0x1100): (0, 2, 3),
    (0x0378, 0x1160): (0, 1, 2),
    (0x0378, 0x0308, 0x1160): (0, 2, 3),
    (0x0378, 0x11A8): (0, 1, 2),
    (0x0378, 0x0308, 0x11A8): (0, 2, 3),
    (0x0378, 0xAC00): (0, 1, 2),
    (0x0378, 0x0308, 0xAC00): (0, 2, 3),
    (0x0378, 0xAC01): (0, 1, 2),
    (0x0378, 0x0308, 0xAC01): (0, 2, 3),
    (0x0378, 0x231A): (0, 1, 2),
    (0x0378, 0x0308, 0x231A): (0, 2, 3),
    (0x0378, 0x0300): (0, 2),
    (0x0378, 0x0308, 0x0300): (0, 3),
    (0x0378, 0x200D): (0, 2),
    (0x0378, 0x0308, 0x200D): (0, 3),
    (0x0378, 0x0378): (0, 1, 2),
    (0x0378, 0x0308, 0x0378): (0, 2, 3),
    (0x000D, 0x000A, 0x0061, 0x000A, 0x0308): (0, 2, 3, 4, 5),
    (0x0061, 0x0308): (0, 2),
    (0x0020, 0x200D, 0x0646): (0, 2, 3),
    (0x0646, 0x200D, 0x0020): (0, 2, 3),
    (0x1100, 0x1100): (0, 2),
    (0xAC00, 0x11A8, 0x1100): (0, 2, 3),
    (0xAC01, 0x11A8, 0x1100): (0, 2, 3),
    (0x1F1E6, 0x1F1E7, 0x1F1E8, 0x0062): (0, 2, 3, 4),
    (0x0061, 0x1F1E6, 0x1F1E7, 0x1F1E8, 0x0062): (0, 1, 3, 4, 5),
    (0x0061, 0x1F1E6, 0x1F1E7, 0x200D, 0x1F1E8, 0x0062): (0, 1, 4, 5, 6),
    (0x0061, 0x1F1E6, 0x200D, 0x1F1E7, 0x1F1E8, 0x0062): (0, 1, 3, 5, 6),
    (0x0061, 0x1F1E6, 0x1F1E7, 0x1F1E8, 0x1F1E9, 0x0062): (0, 1, 3, 5, 6),
    (0x0061, 0x200D): (0, 2),
    (0x0061, 0x0308, 0x0062): (0, 2, 3),
    (0x0061, 0x0903, 0x0062): (0, 2, 3),
    (0x0061, 0x0600, 0x0062): (0, 1, 3),
    (0x1F476, 0x1F3FF, 0x1F476): (0, 2, 3),
    (0x0061, 0x1F3FF, 0x1F476): (0, 2, 3),
    (0x0061, 0x1F3FF, 0x1F476, 0x200D, 0x1F6D1): (0, 2, 5),
    (0x1F476, 0x1F3FF, 0x0308, 0x200D, 0x1F476, 0x1F3FF): (0, 6),
    (0x1F6D1, 0x200D, 0x1F6D1): (0, 3),
    (0x0061, 0x200D, 0x1F6D1): (0, 2, 3),
    (0x2701, 0x200D, 0x2701): (0, 3),
    (0x0061, 0x200D, 0x2701): (0, 2, 3),
}


if __name__ == '__main__':
    test_ranges()
    test_unicode_properties()
