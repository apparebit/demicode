"""
Representation of Unicode versions and properties.
"""
from dataclasses import dataclass
from enum import Enum, StrEnum
import re
from typing import TypeAlias

from .codepoint import CodePoint, CodePointSequence
from ._property import *
from ._version import (
    FIRST_SUPPORTED_VERSION,
    KNOWN_UCD_VERSIONS,
    VersioningError,
    Version,
)


__all__ = (
    'Age',
    'Block',
    'BLK',
    'Canonical_Combining_Class',
    'CCC',
    'East_Asian_Width',
    'EA',
    'General_Category',
    'GC',
    'Indic_Conjunct_Break',
    'InCB',
    'Indic_Syllabic_Category',
    'InSC',
    'Script',
    'SC',

    'BinaryProperty',
    'CharacterData',
    'Emoji_Sequence',
    'FIRST_SUPPORTED_VERSION',
    'Grapheme_Cluster_Break',
    'GCB',
    'GRAPHEME_CLUSTER_PATTERN',
    'KNOWN_UCD_VERSIONS',
    'Presentation',
    'Property',
    'PropertyId',
    'Version',
    'VersioningError',
)


# --------------------------------------------------------------------------------------
# Manually SpecifiedProperties


class Grapheme_Cluster_Break(Property, StrEnum):
    """
    Enumeration over the different code points that contribute to grapheme
    clusters. Note that, unlike for other enumerations in this module,
    enumeration constant values are *not* official Unicode aliases. Instead they
    are single, mnemonic characters used by `GRAPHEME_CLUSTER_PATTERN` to
    recognize grapheme clusters.

    Also note that technically Indic_Conjunct_Break is a separate property,
    whose non-default values overlap with Grapheme_Cluster_Break's non-default
    values. In theory, that gets in the way of maintaining both properties as
    one. However, in practice Indic_Conjunct_Break's Extend and Linker values
    overlap with Grapheme_Cluster_Break's Extend only. Hence this enumeration
    includes the three non-default Indic_Conjunct_Break values, too. However,
    this does mean that Grapheme_Cluster_Break's actual Extend requires
    InCB_Extend and InCB_Linker, too.
    """

    Prepend = 'P'
    CR = 'r'                     # U+000D
    LF = 'n'                     # U+000A
    Control = 'C'
    Extend = 'E'                 # Match "[ελE]"
    Regional_Indicator = 'R'
    SpacingMark = 'S'
    L = 'L'
    V = 'V'
    T = 'T'
    LV = 'v'
    LVT = 't'
    ZWJ = 'Z'                    # U+200D
    Other = 'O'

    # Code points with Extended_Pictographic (does not overlap with non-Other values)
    Extended_Pictographic = 'X'

    # Code points with InCB other than None (using Greek letters)
    InCB_Consonant = 'κ'
    InCB_Extend = 'ε'            # Carved out of Extend, missing ZWJ, hence match "[εZ]"
    InCB_Linker = 'λ'            # Carved out of Extend

    # Obsolete property values (using Etruscan letters)
    E_Base = '\U00010300'
    E_Modifier = '\U00010301'
    Glue_After_Zwj = '\U00010302'
    E_Base_GAZ = '\U00010303'


GCB = Grapheme_Cluster_Break


# https://unicode.org/reports/tr29/#Regex_Definitions
GRAPHEME_CLUSTER_PATTERN = re.compile(
    r"""
            rn                                         # GB3, GB4, GB5
        |   r
        |   n
        |   C
        |   P*                                         # GB9b
            (?:
                    (?:  L* (?: V+ | v V* | t ) T*  )  # GB6, GB7, GB8
                |   L+
                |   T+
                |   RR                                 # GB12, GB13
                |   X (?: [Eελ]* Z X )*                # GB11
                |   (?: κ (?: [ελZ]* λ [ελZ]* κ )+ )   # GB9c  Rewrite: ([εZ]*λ[εZλ]*κ)
                |   [^Cnr]
            )
            [EελZS]*                                   # GB9, GB9a
    """,
    re.VERBOSE,
)


class Emoji_Sequence(Property, StrEnum):
    """The different kinds of emoji sequences."""
    Basic_Emoji = 'Basic_Emoji'
    Emoji_Keycap_Sequence = 'Emoji_Keycap_Sequence'
    # In more recent UCD versions:
    RGI_Emoji_Flag_Sequence = 'RGI_Emoji_Flag_Sequence'
    RGI_Emoji_Modifier_Sequence = 'RGI_Emoji_Modifier_Sequence'
    RGI_Emoji_Tag_Sequence = 'RGI_Emoji_Tag_Sequence'
    RGI_Emoji_ZWJ_Sequence = 'RGI_Emoji_ZWJ_Sequence'
    # In older Unicode Emoji versions:
    Emoji_Combining_Sequence = 'Emoji_Combining_Sequence'
    Emoji_Flag_Sequence = 'Emoji_Flag_Sequence'
    Emoji_Modifier_Sequence = 'Emoji_Modifier_Sequence'
    Emoji_Tag_Sequence = 'Emoji_Tag_Sequence'
    Emoji_ZWJ_Sequence = 'Emoji_ZWJ_Sequence'


# --------------------------------------------------------------------------------------
# Unicode Properties


class BinaryProperty(StrEnum):
    """Supported binary Unicode properties"""
    Default_Ignorable_Code_Point = 'DI'
    Emoji = 'Emoji'
    Emoji_Component = 'EComp'
    Emoji_Modifier = 'EMod'
    Emoji_Modifier_Base = 'EBase'
    Emoji_Presentation = 'EPres'
    Extended_Pictographic = 'ExtPict'

    @property
    def label(self) -> str:
        return self.name

    @property
    def is_emoji(self) -> bool:
        """
        Determine whether the property relates to emoji, i.e., is `Emoji`,
        is prefixed with `Emoji_`, or is `Extended_Pictographic`.
        """
        return self is not BinaryProperty.Default_Ignorable_Code_Point


PropertyValue: TypeAlias = BinaryProperty | Property
PropertyId: TypeAlias = BinaryProperty | type[Property]


def to_property_name(property: PropertyId) -> str:
    return property.name if isinstance(property, BinaryProperty) else property.__name__


PropertyValueTypes: TypeAlias = (
      bool
    | int
    | Age
    | Block
    | East_Asian_Width
    | Emoji_Sequence
    | General_Category
    | Grapheme_Cluster_Break
    | Indic_Conjunct_Break
    | Indic_Syllabic_Category
    | Script
)


# --------------------------------------------------------------------------------------
# Combining Characters


class Presentation(Enum):
    """A character's presentation.

    This enumeration represents variation selectors and other code points that
    modify the presentation of another code point:

      * `CORNER` adds U+FE00 variation selector-1
      * `CENTER` adds U+FE01 variation selector-2
      * `TEXT` adds U+FE0E variation selector-15
      * `EMOJI` adds U+FE0F variation selector-16
      * `KEYCAP` adds U+FE0F variation selector-16 and U+20E3 combining
        enclosing keycap

    `CORNER` and `CENTER` are only valid with the full-width forms of of
    `!,.:;?` (U+FF01, U+FF0C, U+FF0E, U+FF1A, U+FF1B, U+FF1F). `TEXT` and
    `EMOJI` are only valid with the code points included in
    `USD.with_emoji_variation`, and `KEYCAP` only with `#*0123456789`, which
    also are in `USD.with_emoji_variation`.

    `NONE` means displaying a grapheme cluster without extra combining
    characters. `HEADING` is *not* associated with code points but rather a
    string for an instream heading.
    """

    HEADING = -2
    NONE = -1
    CORNER = CodePoint.VARIATION_SELECTOR_1
    CENTER = CodePoint.VARIATION_SELECTOR_2
    TEXT = CodePoint.TEXT_VARIATION_SELECTOR
    EMOJI = CodePoint.EMOJI_VARIATION_SELECTOR
    KEYCAP = CodePoint.COMBINING_ENCLOSING_KEYCAP

    @classmethod
    def unapply(cls, codepoints: CodePointSequence) -> 'Presentation':
        """Make an implicit presentation choice explicit again."""
        length = len(codepoints)
        if length == 2:
            try:
                return Presentation(codepoints[1])
            except ValueError:
                return Presentation.NONE
        elif (
            length == 3
            and codepoints[1] == CodePoint.EMOJI_VARIATION_SELECTOR
            and codepoints[2] == CodePoint.COMBINING_ENCLOSING_KEYCAP
        ):
            return Presentation.KEYCAP
        else:
            return Presentation.NONE

    def apply(self, codepoint: CodePoint) -> str:
        """Apply this presentation to the code point, yielding a string."""
        match self:
            case Presentation.NONE:
                return chr(codepoint)
            case Presentation.KEYCAP:
                return f'{chr(codepoint)}\uFE0F\u20E3'
            case _:
                return f'{chr(codepoint)}{chr(self.value)}'

    @property
    def is_heading(self) -> bool:
        return self is Presentation.HEADING

    @property
    def is_emoji_variation(self) -> bool:
        return self in (Presentation.EMOJI, Presentation.KEYCAP)

    @property
    def variation_selector(self) -> int:
        return (
            CodePoint.EMOJI_VARIATION_SELECTOR
            if self == Presentation.KEYCAP
            else self.value
        )

    def normalize(
        self, codepoints: CodePoint | CodePointSequence
    ) -> 'tuple[Presentation, CodePoint | CodePointSequence]':
        if codepoints.is_singleton():
            return self, codepoints
        codepoints = codepoints.to_sequence()
        presentation = Presentation.unapply(codepoints)
        return (
            presentation,
            codepoints if presentation is Presentation.NONE else codepoints[0]
        )


# --------------------------------------------------------------------------------------
# A Code Point with Properties


@dataclass(frozen=True, slots=True, kw_only=True)
class CharacterData:
    """A Unicode code point and its properties."""

    codepoint: CodePoint
    category: General_Category
    east_asian_width: East_Asian_Width
    age: Age
    name: None | str
    block: None | Block
    flags: frozenset[BinaryProperty]
