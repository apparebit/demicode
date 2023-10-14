import unittest

from demicode.codepoint import (
    CodePoint,
    CodePointRange,
    codepoints_to_ranges,
)

class TestModel(unittest.TestCase):

    CODEPOINTS = (CodePoint.of(cp) for cp in (
        'U+0665',
        'U+0667',
        'U+0668',
        'U+0669',
        'U+066A',
        'U+066C',
        'U+066E',
        'U+066F',
        'U+0670',
        'U+0671',
        'U+10FFFF',
    ))

    RANGES = (
        CodePointRange.of(0x0665),
        CodePointRange.of(0x0667, 0x066A),
        CodePointRange.of(0x066C),
        CodePointRange.of(0x066E, 0x0671),
        CodePointRange.of(0x10FFFF),
    )

    def test_codepoints_to_ranges(self) -> None:
        self.assertEqual(
            tuple(codepoints_to_ranges(TestModel.CODEPOINTS)),
            TestModel.RANGES
        )
