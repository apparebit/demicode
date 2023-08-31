"""
The Unicode properties of code points and sequences of code points.
"""
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
import re
from typing import Callable

from .codepoint import CodePoint


class Category(StrEnum):
    """
    The Unicode categories. Constant names are the property values in Unicode
    notation, i.e., preserving capitalization. Constant values are the shorter
    aliases.
    """

    # L for Letter
    Uppercase_Letter = 'Lu'
    Lowercase_Letter = 'Ll'
    Titlecase_Letter = 'Lt'
    Modifier_Letter = 'Lm'
    Other_Letter = 'Lo'

    # M for Mark
    Nonspacing_Mark = 'Mn'
    Spacing_Mark = 'Mc'
    Enclosing_Mark = 'Me'

    # N for Number
    Decimal_Number = 'Nd'
    Letter_Number = 'Nl'
    Other_Number = 'No'

    # P for Punctuation
    Connector_Punctuation = 'Pc'
    Dash_Punctuation = 'Pd'
    Open_Punctuation = 'Ps'
    Close_Punctuation = 'Pe'
    Initial_Punctuation = 'Pi'
    Final_Punctuation = 'Pf'
    Other_Punctuation = 'Po'

    # S for Symbol
    Math_Symbol = 'Sm'
    Currency_Symbol = 'Sc'
    Modifier_Symbol = 'Sk'
    Other_Symbol = 'So'

    # Z for Zeparator
    Space_Separator = 'Zs'
    Line_Separator = 'Zl'
    Paragraph_Separator = 'Zp'

    # C for Control
    Control = 'Cc'
    Format = 'Cf'
    Surrogate = 'Cs'
    Private_Use = 'Co'
    Unassigned = 'Cn'

    @property
    def is_letter(self) -> bool:
        return self.value[0] == 'L'

    @property
    def is_mark(self) -> bool:
        return self.value[0] == 'M'

    @property
    def is_number(self) -> bool:
        return self.value[0] == 'N'

    @property
    def is_punctuation(self) -> bool:
        return self.value[0] == 'P'

    @property
    def is_symbol(self) -> bool:
        return self.value[0] == 'S'

    @property
    def is_separator(self) -> bool:
        return self.value[0] == 'Z'

    @property
    def is_other(self) -> bool:
        return self.value[0] == 'C'


class EastAsianWidth(StrEnum):
    Ambiguous = 'A'
    Fullwidth = 'F'
    Halfwidth = 'H'
    Neutral = 'N'
    Narrow = 'Na'
    Wide = 'W'

    @property
    def is_ambiguous(self) -> bool:
        return self is EastAsianWidth.Ambiguous

    @property
    def is_narrow(self) -> bool:
        return self in (EastAsianWidth.Halfwidth, EastAsianWidth.Narrow)

    @property
    def is_neutral(self) -> bool:
        return self is EastAsianWidth.Neutral

    @property
    def is_wide(self) -> bool:
        return self in (EastAsianWidth.Fullwidth, EastAsianWidth.Wide)


# --------------------------------------------------------------------------------------


class BinaryProperty(StrEnum):
    """Supported binary Unicode properties"""
    Dash = 'Dash'
    Emoji = 'Emoji'
    Emoji_Component = 'EComp'
    Emoji_Modifier = 'EMod'
    Emoji_Modifier_Base = 'EBase'
    Emoji_Presentation = 'EPres'
    Extended_Pictographic = 'ExtPict'
    Noncharacter_Code_Point = 'NChar'
    Variation_Selector = 'VS'
    White_Space = 'WSpace'

    @property
    def is_emoji(self) -> bool:
        """
        Determine whether the property relates to emoji, i.e., is `Emoji`,
        is prefixed with `Emoji_`, or is `Extended_Pictographic`.
        """
        return self in _EMOJI_PROPERTIES


_EMOJI_PROPERTIES = frozenset([
    BinaryProperty.Emoji,
    BinaryProperty.Emoji_Component,
    BinaryProperty.Emoji_Modifier,
    BinaryProperty.Emoji_Modifier_Base,
    BinaryProperty.Emoji_Presentation,
    BinaryProperty.Extended_Pictographic,
])


# --------------------------------------------------------------------------------------


class GraphemeClusterProperty(StrEnum):
    Prepend = 'P'
    CR = 'r'
    LF = 'n'
    Control = 'C'
    Extend = 'E'
    Regional_Indicator = 'R'
    SpacingMark = 'S'
    L = 'l'
    V = 'v'
    T = 't'
    LV = 'V'
    LVT = 'T'
    ZWJ = 'Z'
    Other = 'O'
    Extended_Pictographic = 'X'


GRAPHEME_CLUSTER_PATTERN = re.compile(
    r"""
        rn
        | C
        | (?:
            P*                        # precore
            (?:
                (?:                   # hangul-syllable
                    l*
                    (?: v+ | Vv* | T )
                    t*
                )
                |   l+
                |   t+
                |   RR                # ri-sequence
                |   X (?: E* Z X )*   # xpicto-sequence
                |   [^CrnlvtVTRX]     # all but Control, CR, LF, already covered symbols
            )
            [EZS]*                    # postcore
        )
    """,
    re.VERBOSE,
)


# --------------------------------------------------------------------------------------


class EmojiSequence(StrEnum):
    """The different kinds of emoji sequences."""
    Basic_Emoji = 'Basic_Emoji'
    Emoji_Keycap_Sequence = 'Emoji_Keycap_Sequence'
    RGI_Emoji_Flag_Sequence = 'RGI_Emoji_Flag_Sequence'
    RGI_Emoji_Tag_Sequence = 'RGI_Emoji_Tag_Sequence'
    RGI_Emoji_Modifier_Sequence = 'RGI_Emoji_Modifier_Sequence'
    RGI_Emoji_ZWJ_Sequence = 'RGI_Emoji_ZWJ_Sequence'


# --------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class CharacterData:
    """A Unicode code point and its properties."""

    codepoint: CodePoint
    category: Category
    east_asian_width: EastAsianWidth
    age: None | str
    name: None | str
    block: None | str
    flags: frozenset[BinaryProperty]

    @property
    def is_zero_width(self) -> bool:
        return (
            self.codepoint == 0
            or self.category in (
                Category.Enclosing_Mark,
                Category.Nonspacing_Mark,
                Category.Format
            ) and self.codepoint != 0x00AD
            or 0x1160 <= self.codepoint <= 0x11FF
        )

    @property
    def is_invalid(self) -> bool:
        # Surrogate code points should not appear inside strings. Private_Use
        # may appear but aren't very meaningful in general. Still, a robust
        # width property might want to consider assigning different widths to
        # different private use ranges.
        return self.category in (Category.Surrogate, Category.Private_Use)

    def wcwidth(self) -> int:
        # https://www.cl.cam.ac.uk/~mgk25/ucs/wcwidth.c
        # https://github.com/jquast/wcwidth
        if self.is_zero_width:
            return 0
        if self.is_invalid or self.codepoint < 32 or 0x7F <= self.codepoint < 0xA0:
            return -1
        if self.east_asian_width.is_wide:
            return 2
        return 1
