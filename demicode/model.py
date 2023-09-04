"""
Representation of Unicode versions and properties.
"""
from dataclasses import dataclass
from enum import Enum, StrEnum
import re
from typing import NamedTuple

from .codepoint import CodePoint, CodePointSequence
from ._property import *


# --------------------------------------------------------------------------------------
# Versions


class VersionError(Exception):
    pass


KNOWN_UCD_VERSIONS = tuple(v + (0,) for v in (
    (4, 1),
    (5, 0),
    (5, 1),
    (5, 2),
    (6, 0),
    (6, 1),
    (6, 2),
    (6, 3),
    (7, 0),
    (8, 0),
    (9, 0),
    (10, 0),
    (11, 0),
    (12, 0),
    (12, 1),
    (13, 0),
    (14, 0),
    (15, 0),
    (15, 1),
))

KNOWN_EMOJI_VERSIONS = tuple(v + (0,) for v in (
    (0, 0),
    (0, 6),
    (0, 7),
    (1, 0),
    (2, 0),
    (3, 0),
    (4, 0),
    (5, 0),
    (11, 0),
    (12, 0),
    (12, 1),
    (13, 0),
    (13, 1),
    (14, 0),
    (15, 0),
))


class Version(NamedTuple):
    """A version number."""

    major: int
    minor: int
    patch: int

    @classmethod
    def of(cls, text: str) -> 'Version':
        """
        Parse the string as a version number with at most three components. If
        the string has fewer components, pad the missing components with zero.
        """
        try:
            components = tuple(int(c) for c in text.split('.'))
        except:
            raise ValueError(f'malformed components in version "{text}"')

        count = len(components)
        if count < 3:
            components += (0,) * (3 - count)
        elif count > 3:
            raise ValueError(f'too many components in version "{text}"')

        return cls(*components)

    def is_ucd(self) -> bool:
        """
        Test whether the version is a valid UCD version. This method only
        rejects versions that cannot possibly be valid because they don't
        identify an existing version but are smaller than the latest known
        version. For now, it also rejects versions before 4.1.0, since file
        mirroring does not yet support the necessary name wrangling.
        """
        if self <= KNOWN_UCD_VERSIONS[-1] and self not in KNOWN_UCD_VERSIONS:
            return False
        return True

    def ucd(self) -> 'Version':
        """Validate this version as a UCD version."""
        if self.is_ucd():
            return self
        raise ValueError(f'version {self} is not a valid UCD version')

    def is_emoji(self) -> bool:
        """
        Test whether the version is a valid emoji version. This method rejects
        only versions that cannot possibly be valid because they don't identify
        an existing version but are smaller than the latest known version.

        Even though this method accepts 0.0, 0.6, and 0.7, those versions are
        informal versions only, without corresponding normative files. You can
        use `is_v0()` to test for those versions, since there are no other valid
        emoji versions with zero as major version.
        """
        if self <= KNOWN_EMOJI_VERSIONS[-1] and self not in KNOWN_EMOJI_VERSIONS:
            return False
        return True

    def is_v0(self) -> bool:
        """Test whether the major version component is zero."""
        return self.major == 0

    def to_emoji(self) -> 'Version':
        """
        Convert this UCD version to the smallest corresponding Emoji version.
        This method returns 0.0, 0.6, and 0.7, even though those versions have
        no normative files.
        """
        if self.major < 6:
            return Version(0, 0, 0)
        if self.major == 6:
            return Version(0, 6, 0)
        if self.major == 7:
            return Version(0, 7, 0)
        if 8 <= self.major <= 10:
            return Version(1 + 2 * (self.major - 8), 0, 0)
        if self.major == 13:
            return Version(13, 0, 0)
        return self

    def in_short_format(self) -> str:
        return f'{self.major}.{self.minor}'

    def in_emoji_format(self) -> str:
        return f'E{self.major}.{self.minor}'

    def __str__(self) -> str:
        return '.'.join(str(c) for c in self)


# --------------------------------------------------------------------------------------
# Unicode Properties


class ComplexProperty(StrEnum):
    """
    An enumeration of complex properties, i.e., Unicode properties that have
    more than two values. For each included property, this module exports an
    enumeration with the same name modulo underscores. The enumeration's
    constants represent the domain of named values for the property, with each
    constant's value providing a shorter alias. Most enumerations are
    machine-generated from Unicode data.
    """
    Canonical_Combining_Class = 'ccc'
    East_Asian_Width = 'ea'
    General_Category = 'gc'
    Grapheme_Cluster_Break = 'GCB'
    Indic_Syllabic_Category = 'InSC'
    Script = 'sc'


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
    """

    NONE = -1
    CORNER = 0xFE00
    CENTER = 0xFE01
    TEXT = 0xFE0E
    EMOJI = 0xFE0F
    KEYCAP = 0x20E3

    @classmethod
    def unapply(cls, codepoints: CodePointSequence) -> 'Presentation':
        """Make an implicit presentation choice explicit again."""
        length = len(codepoints)
        if length == 2:
            try:
                return Presentation(codepoints[1])
            except ValueError:
                return Presentation.NONE
        elif length == 3 and codepoints[1] == 0xFE0F and codepoints[2] == 0x20E3:
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
    def is_emoji_variation(self) -> bool:
        return self in (Presentation.EMOJI, Presentation.KEYCAP)

    @property
    def variation_selector(self) -> int:
        return 0xFE0F if self == Presentation.KEYCAP else self.value


# --------------------------------------------------------------------------------------
# Grapheme Clusters


class GraphemeCluster(StrEnum):
    """
    Enumeration over the different code points that contribute to grapheme
    clusters. Note that, unlike for other enumerations in this module,
    enumeration constant values are *not* official Unicode aliases. Instea d they
    are single, mnemonic characters used by `GRAPHEME_CLUSTER_PATTERN` to
    recognize grapheme clusters.
    """

    Prepend = 'P'
    CR = 'r'         # U+000D
    LF = 'n'         # U+000A
    Control = 'C'
    Extend = 'E'
    Regional_Indicator = 'R'
    SpacingMark = 'S'
    L = 'l'
    V = 'v'
    T = 't'
    LV = 'V'
    LVT = 'T'
    ZWJ = 'Z'        # U+200D
    Other = 'O'
    Extended_Pictographic = 'X'


# https://unicode.org/reports/tr29/#Regex_Definitions
GRAPHEME_CLUSTER_PATTERN = re.compile(
    r"""
            rn
        |   r
        |   n
        |   C
        |   P*      # precore
            (?:
                    (?:  l* (?: v+ | Vv* | T ) t*  )  # hangul-syllable
                |   l+
                |   t+
                |   RR               # ri-sequence
                |   X (?: E* Z X )*  # xpicto-sequence
                |   [^Cnr]           # all but Control, CR, LF
            )
            [EZS]*  # postcore
    """,
    re.VERBOSE,
)


class EmojiSequence(StrEnum):
    """The different kinds of emoji sequences."""
    Basic_Emoji = 'Basic_Emoji'
    Emoji_Keycap_Sequence = 'Emoji_Keycap_Sequence'
    RGI_Emoji_Flag_Sequence = 'RGI_Emoji_Flag_Sequence'
    RGI_Emoji_Tag_Sequence = 'RGI_Emoji_Tag_Sequence'
    RGI_Emoji_Modifier_Sequence = 'RGI_Emoji_Modifier_Sequence'
    RGI_Emoji_ZWJ_Sequence = 'RGI_Emoji_ZWJ_Sequence'


# --------------------------------------------------------------------------------------
# A Code Point with Properties


@dataclass(frozen=True, slots=True, kw_only=True)
class CharacterData:
    """A Unicode code point and its properties."""

    codepoint: CodePoint
    category: GeneralCategory
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
                GeneralCategory.Enclosing_Mark,
                GeneralCategory.Nonspacing_Mark,
                GeneralCategory.Format
            ) and self.codepoint != 0x00AD
            or 0x1160 <= self.codepoint <= 0x11FF
        )

    @property
    def is_invalid(self) -> bool:
        # Surrogate code points should not appear inside strings. Private_Use
        # may appear but aren't very meaningful in general. Still, a robust
        # width property might want to consider assigning different widths to
        # different private use ranges.
        return self.category in (GeneralCategory.Surrogate, GeneralCategory.Private_Use)

    def wcwidth(self) -> int:
        """
        Determine [wcwidth](https://www.cl.cam.ac.uk/~mgk25/ucs/wcwidth.c) of
        code point. Instead of calling this method, prefer `UCD.width()`.
        """
        # Also https://github.com/jquast/wcwidth
        if self.is_zero_width:
            return 0
        if self.is_invalid or self.codepoint < 32 or 0x7F <= self.codepoint < 0xA0:
            return -1
        if self.east_asian_width in (EastAsianWidth.Fullwidth, EastAsianWidth.Wide):
            return 2
        return 1
