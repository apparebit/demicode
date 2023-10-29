import unittest

from demicode.codepoint import CodePoint, CodePointRange
from demicode.version import Version


POINT_DATA = (
    ('SPACE', 0x0020),
    ('DELETE', 0x007F),
    ('PAD', 0x0080),
    ('NO_BREAK_SPACE', 0x00A0),
    ('SOFT_HYPHEN', 0x00AD),
    ('HANGUL_JUNGSEONG_FILLER', 0x1160),
    ('HANGUL_JONGSEONG_SSANGNIEUN', 0x11FF),
    ('ZERO_WIDTH_JOINER', 0x200D),
    ('COMBINING_ENCLOSING_KEYCAP', 0x20E3),
    ('FULL_BLOCK', 0x2588),
    ('LEFTWARDS_BLACK_ARROW', 0x2B05),
    ('RIGHTWARDS_BLACK_ARROW', 0x2B95),
    ('VARIATION_SELECTOR_1', 0xFE00),
    ('VARIATION_SELECTOR_2', 0xFE01),
    ('TEXT_VARIATION_SELECTOR', 0xFE0E),
    ('EMOJI_VARIATION_SELECTOR', 0xFE0F),
    ('REPLACEMENT_CHARACTER', 0xFFFD),
    ('REGIONAL_INDICATOR_SYMBOL_LETTER_A', 0x1F1E6),
    ('REGIONAL_INDICATOR_SYMBOL_LETTER_Z', 0x1F1FF),
)

RANGE_DATA = (
    # Merge code point and code point
    (ord('r'), ord('p'), None, None),
    (ord('r'), ord('q'), ord('q'), ord('r')),
    (ord('r'), ord('r'), ord('r'), ord('r')),
    (ord('r'), ord('s'), ord('r'), ord('s')),
    (ord('r'), ord('t'), None, None),
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


class TestModel(unittest.TestCase):

    def test_versions(self) -> None:
        self.assertEqual(Version.of('13'), Version(13, 0, 0))
        self.assertEqual(Version.of('13').to_emoji(), Version(13, 0, 0))
        self.assertEqual(Version.of('10'), Version(10, 0, 0))
        self.assertEqual(Version.of('10').to_emoji(), Version(5, 0, 0))
        self.assertEqual(Version.of('9').to_emoji(), Version(3, 0, 0))
        self.assertEqual(Version.of('8').to_emoji(), Version(1, 0, 0))
        self.assertEqual(Version.of('7').to_emoji(), Version(0, 7, 0))
        self.assertEqual(Version.of('6').to_emoji(), Version(0, 6, 0))
        self.assertEqual(Version.of('5').to_emoji(), Version(0, 0, 0))
        self.assertEqual(Version.of('4.1').to_emoji(), Version(0, 0, 0))

    def test_code_points(self) -> None:
        for name, value in POINT_DATA:
            self.assertEqual(getattr(CodePoint, name), value)
            self.assertEqual(getattr(CodePoint, name), CodePoint(value))

    def test_ranges(self) -> None:
        for row in RANGE_DATA:
            row_length = len(row)

            if row_length == 4:
                this = CodePoint(row[0])
                other = CodePoint(row[1])
            else:
                this = CodePointRange(CodePoint(row[0]), CodePoint(row[1]))
                if row_length == 5:
                    other = CodePoint(row[2])
                else:
                    other = CodePointRange(CodePoint(row[2]), CodePoint(row[3]))

            if row[-1] is None:
                self.assertFalse(this.can_merge(other))
                continue

            self.assertTrue(this.can_merge(other))
            actual = this.merge(other)
            expected = CodePointRange(CodePoint(row[-2]), CodePoint(row[-1]))
            self.assertEqual(actual, expected)
