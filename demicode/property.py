"""
A code point's Unicode properties.
"""

from dataclasses import dataclass
from enum import StrEnum
from .codepoint import CodePoint


class Category(StrEnum):
    """
    The Unicode categories. Constant names are the property values in Unicode
    notation, i.e., preserving capitalization. Constant values are the shorter
    aliases.
    """

    Uppercase_Letter = 'Lu'
    Lowercase_Letter = 'Ll'
    Titlecase_Letter = 'Lt'
    Modifier_Letter = 'Lm'
    Other_Letter = 'Lo'
    Nonspacing_Mark = 'Mn'
    Spacing_Mark = 'Mc'
    Enclosing_Mark = 'Me'
    Decimal_Number = 'Nd'
    Letter_Number = 'Nl'
    Other_Number = 'No'
    Connector_Punctuation = 'Pc'
    Dash_Punctuation = 'Pd'
    Open_Punctuation = 'Ps'
    Close_Punctuation = 'Pe'
    Initial_Punctuation = 'Pi'
    Final_Punctuation = 'Pf'
    Other_Punctuation = 'Po'
    Math_Symbol = 'Sm'
    Currency_Symbol = 'Sc'
    Modifier_Symbol = 'Sk'
    Other_Symbol = 'So'
    Space_Separator = 'Zs'
    Line_Separator = 'Zl'
    Paragraph_Separator = 'Zp'
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

    # ----------------------------------------------------------------------------------
    # Non-standard properties

    @property
    def is_invalid(self) -> bool:
        return self in (
            Category.Surrogate,
            Category.Private_Use,
            Category.Unassigned
        )

    @property
    def is_zero_width(self) -> bool:
        return self in (
            Category.Enclosing_Mark,
            Category.Nonspacing_Mark,
            Category.Format
        )


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
            self.category in (
                Category.Enclosing_Mark,
                Category.Nonspacing_Mark,
                Category.Format
            ) and self.codepoint != 0x00AD
            or 0x1160 <= self.codepoint <= 0x11FF
            or self.codepoint == 0x200B
        )

    def wcwidth(self) -> int:
        # https://www.cl.cam.ac.uk/~mgk25/ucs/wcwidth.c
        # https://github.com/jquast/wcwidth
        if self.codepoint == 0 or self.is_zero_width:
            return 0
        if self.codepoint < 32 or 0x7F <= self.codepoint < 0xA0:
            return -1
        if self.east_asian_width.is_wide:
            return 2

        return 1

    def __str__(self) -> str:
        return f'{self.codepoint!s:<8} {format_properties(self)}'


def format_properties(
    data: CharacterData,
    *,
    flag_width: int = 25,
    max_width: None | int = None
) -> str:
    width = data.east_asian_width
    flags = ' '.join(f.value for f in data.flags)
    age = data.age or ''
    name = data.name or ''
    block = '' if data.block is None else f' ({data.block})'
    props = (
        f'{data.category.value} {width:<2} {flags:<{flag_width}} {age:>4} {name}{block}'
    )
    if max_width is not None and len(props) > max_width:
        props = props[:max_width - 1] + '…'
    return props
