"""
Python enumerations for Unicode properties.
"""

from enum import StrEnum


class Category(StrEnum):
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


# --------------------------------------------------------------------------------------


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
