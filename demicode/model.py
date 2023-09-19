"""
Representation of Unicode versions and properties.
"""
from dataclasses import dataclass
from enum import Enum, StrEnum
import re
from typing import NamedTuple, TypeAlias

from .codepoint import CodePoint, CodePointSequence
from ._property import *


# --------------------------------------------------------------------------------------
# Versions


class VersioningError(Exception):
    """
    An error indicating that some resource is not available for the requested
    version of Unicode. See `demicode.mirror.mirror_unicode_data()` for details.
    """
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
    (15, 1),
))


class Version(NamedTuple):
    """A version number."""

    major: int
    minor: int
    patch: int

    @classmethod
    def of(cls, v: 'str | Version') -> 'Version':
        """
        Parse the string as a version number with at most three components. If
        the string has fewer components, pad the missing components with zero.
        """
        if isinstance(v, Version):
            return v

        try:
            components = tuple(int(c) for c in v.split('.'))
        except:
            raise ValueError(f'malformed components in version "{v}"')

        count = len(components)
        if count < 3:
            components += (0,) * (3 - count)
        elif count > 3:
            raise ValueError(f'too many components in version "{v}"')

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

    def to_ucd(self) -> 'Version':
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
# Property Values (see _property module for machine-generated ones)


class GraphemeClusterBreak(StrEnum):
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


# https://unicode.org/reports/tr29/#Regex_Definitions
GRAPHEME_CLUSTER_PATTERN = re.compile(
    r"""
            rn                                        # GB3, GB4, GB5
        |   r
        |   n
        |   C
        |   P*                                        # GB9b
            (?:
                    (?:  L* (?: V+ | vV* | t ) T*  )  # GB6, GB7, GB8
                |   L+
                |   T+
                |   RR                                # GB12, GB13
                |   X (?: [Eελ]* Z X )*               # GB11
                |   (?: κ (?: [ελZ]* λ [ελZ]* κ )+ )  # GB9c  Rewrite: ([εZ]*λ[εZλ]*κ)
                |   [^Cnr]
            )
            [EελZS]*                                  # GB9, GB9a
    """,
    re.VERBOSE,
)


class EmojiSequence(StrEnum):
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


class Property(StrEnum):
    """
    An enumeration of supported Unicode properties. For each included property,
    this module exports an enumeration with the same name sans underscores. The
    enumeration's constants represent the domain of named values for the
    property, with each constant's value providing a shorter alias. Most
    enumerations are machine-generated from Unicode data. The enumeration for
    binary Unicode properties is separate for now.
    """
    Canonical_Combining_Class = 'ccc'
    East_Asian_Width = 'ea'
    Emoji_Sequence = 'Emoji_Sequence'
    General_Category = 'gc'
    Grapheme_Cluster_Break = 'GCB'
    Indic_Conjunct_Break = 'InCB'
    Indic_Syllabic_Category = 'InSC'
    Script = 'sc'

    def is_manually_generated(self) -> bool:
        return self in (
            Property.Emoji_Sequence,
            Property.Grapheme_Cluster_Break,
        )

    def is_binary(self) -> bool:
        return False  # For now


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
    def is_emoji(self) -> bool:
        """
        Determine whether the property relates to emoji, i.e., is `Emoji`,
        is prefixed with `Emoji_`, or is `Extended_Pictographic`.
        """
        return self is not BinaryProperty.Default_Ignorable_Code_Point


PropertyValueTypes: TypeAlias = (
      bool
    | int
    | EastAsianWidth
    | EmojiSequence
    | GeneralCategory
    | GraphemeClusterBreak
    | IndicConjunctBreak
    | IndicSyllabicCategory
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
    category: GeneralCategory
    east_asian_width: EastAsianWidth
    age: None | str
    name: None | str
    block: None | str
    flags: frozenset[BinaryProperty]
