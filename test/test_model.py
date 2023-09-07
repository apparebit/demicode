import unittest

from demicode.codepoint import CodePoint, CodePointRange
from demicode.model import Version


RANGE_DATA = (
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

    def test_ranges(self) -> None:
        for row in RANGE_DATA:
            range = CodePointRange(CodePoint(row[0]), CodePoint(row[1]))
            if len(row) == 5:
                other = CodePoint(row[2])
            else:
                other = CodePointRange(CodePoint(row[2]), CodePoint(row[3]))

            if row[-1] is None:
                self.assertFalse(range.can_merge_with(other))
                continue

            result = range.merge(other)
            expected = CodePointRange(CodePoint(row[-2]), CodePoint(row[-1]))
            self.assertEqual(result, expected)
