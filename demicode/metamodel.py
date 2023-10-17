from dataclasses import dataclass
from enum import auto, Enum, Flag, nonmember, StrEnum
from itertools import filterfalse
from pathlib import Path
from typing import Any

from .codepoint import CodePoint, CodePointRange, CodePoints
from .mirror import mirrored_data
from .parser import parse, Properties
from ._version import Version


def _is_ignorable(c: str) -> bool:
    return c in ' _-'


def are_same_name(n1: str, n2: str) -> bool:
    """
    Determine whether the given property names or enumeration values identify
    the same property or property value under Unicode's [loose matching
    rules](https://www.unicode.org/reports/tr44/#UAX44-LM3). This function does
    *not* account for aliases.
    """
    if n1.startswith('is'):
        n1 = n1[2:]
    if n2.startswith('is'):
        n2 = n2[2:]
    try:
        for c1, c2 in zip(
            filterfalse(_is_ignorable, n1),
            filterfalse(_is_ignorable, n2),
            strict=True
        ):
            if c1.upper() != c2.upper():
                return False
    except ValueError:
        return False
    else:
        return True


class PropertyName(str):

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return are_same_name(self, other)
        return NotImplemented


@dataclass(frozen=True, slots=True)
class PropertyValue:
    name: PropertyName
    value: object


class Property:
    pass


class BinaryProperty(Property, Enum):
    YES = 'Y'
    NO = 'N'

    @property
    def DEFAULT(self) -> 'BinaryProperty':
        return BinaryProperty.NO


class NumericProperty(Property, int):

    @property
    def DEFAULT(self) -> 'NumericProperty':
        return _default_numeric_property


_default_numeric_property = NumericProperty(0)


class EnumerationProperty(Property, StrEnum):
    pass


class CatalogProperty(Property, StrEnum):





class PropertyType(Enum):
    CATALOG = auto()
    ENUMERATION = auto()
    BINARY = auto()
    STRING_VALUED = auto()
    NUMERIC = auto()
    NAME = auto()            # Code point names
    EMOSEQ = auto()          # Emoji variation sequences


class FileFormat(Flag):
    SOLOPROP = 0             # Default: File contains one property and uses long names
    POLYPROP = auto()        # File contains multiple properties
    ALIASED = auto()         # Values are short aliases instead of long names
    POLY_ALIASED = POLYPROP | ALIASED


@dataclass(frozen=True, slots=True)
class MetaProperty:
    name: PropertyName
    alias: PropertyName
    type: PropertyType
    file: str
    format: FileFormat = FileFormat.SOLOPROP
    slot: None | int = None
    extras: tuple[PropertyValue, ...] = ()
    min_version: None | Version = None



PROPERTIES = [
    {
        'name': 'Age',  'alias': 'age',  'type': PropertyType.CATALOG,
        'file': 'DerivedAge.txt',  'format': FileFormat.ALIASED,
    },
    {
        'name': 'Block', 'alias': 'blk', 'type': PropertyType.CATALOG,
        'file': 'Blocks.txt'
    },
    {
        'name': 'Canonical_Combining_Class', 'alias': 'ccc',
        'type': PropertyType.NUMERIC,
        'file': 'DerivedCombiningClass.txt',
    },
    {
        'name': 'Dash', 'alias': 'Dash',
        'type': PropertyType.BINARY,
        'file': 'PropList.txt', 'format': FileFormat.POLYPROP,
    },
    {
        'name': 'Default_Ignorable_Code_Point', 'alias': 'DI',
        'type': PropertyType.BINARY,
        'file': 'DerivedCoreProperties.txt', 'format': FileFormat.POLYPROP,
    },
    {
        'name': 'East_Asian_Width', 'alias': 'EA',
        'type': PropertyType.ENUMERATION,
        'file': 'EastAsianWidth.txt', 'format': FileFormat.ALIASED,
    },
    {
        'name': 'Emoji', 'alias': 'Emoji',
        'type': PropertyType.BINARY,
        'file': 'emoji-data.txt', 'format': FileFormat.POLYPROP,
        'min_version': '9.0',
    },
    {
        'name': 'Emoji_Component', 'alias': 'EComp',
        'type': PropertyType.BINARY,
        'file': 'emoji-data.txt', 'format': FileFormat.POLYPROP,
        'min_version': '9.0',
    },
    {
        'name': 'Emoji_Modifier', 'alias': 'EMod',
        'type': PropertyType.BINARY,
        'file': 'emoji-data.txt', 'format': FileFormat.POLYPROP,
        'min_version': '9.0',
    },
    {
        'name': 'Emoji_Modifier_Base', 'alias': 'EBase',
        'type': PropertyType.BINARY,
        'file': 'emoji-data.txt', 'format': FileFormat.POLYPROP,
        'min_version': '9.0',
    },
    {
        'name': 'Emoji_Presentation', 'alias': 'EPres',
        'type': PropertyType.BINARY,
        'file': 'emoji-data.txt', 'format': FileFormat.POLYPROP,
        'min_version': '9.0',
    },
    {
        'name': 'Emoji_Variation_Sequences',
        'type': PropertyType.EMOSEQ,
        'file': 'emoji-variation-sequences.txt',
    },
    {
        'name': 'Extended_Pictographic', 'alias': 'ExtPict',
        'type': PropertyType.BINARY,
        'file': 'emoji-data.txt', 'format': FileFormat.POLYPROP,
        'min_version': '9.0',
    },
    {
        'name': 'General_Category', 'alias': 'GC', 'type': PropertyType.ENUMERATION,
        'file': 'DerivedGeneralCategory.txt', 'format': FileFormat.ALIASED,
    },
    {
        'name': 'Grapheme_Cluster_Break', 'alias': 'GCB',
        'type': PropertyType.ENUMERATION,
        'file': 'GraphemeBreakProperty.txt',
    },
    {
        'name': 'Indic_Conjunct_Break', 'alias': 'InCB',
        'type': PropertyType.ENUMERATION,
        'file': 'DerivedCoreProperties.txt', 'format': FileFormat.POLY_ALIASED,
    },
    {
        'name': 'Indic_Syllabic_Category', 'alias': 'InSC',
        'type': PropertyType.ENUMERATION,
        'file': 'IndicSyllabicCategory.txt',
        'extras': ({'name': 'Consonant_Repha', 'value': 'Consonant_Repha'},)
    },
    {
        'name': 'Name',
        'type': PropertyType.NAME,
        'file': 'UnicodeData.txt', 'slot': 0,
    },
    {
        'name': 'Script', 'alias': 'sc', 'type': PropertyType.ENUMERATION,
        'file': 'Scripts.txt',
    },
    {
        'name': 'While_Space', 'alias': 'WSpace', 'type': PropertyType.BINARY,
        'file': 'emoji-data.txt', 'format': FileFormat.POLYPROP,
    },
]


def load_property(
    property: MetaProperty, version: Version, root: Path
) -> list[tuple[CodePoints, object]]:
    # Return empty list if the requested version precedes the minimum version
    if property.min_version is not None:
        min_version = Version.of(property.min_version)
        if version < min_version:
            return []

    name = property.alias if property.format & FileFormat.ALIASED else property.name

    if property.type is PropertyType.BINARY:
        def get_slot(props: Properties) -> str:
            raise NotImplementedError()
    elif property.slot is None:
        def get_slot(props: Properties) -> str:
            return props[0]
    else:
        def get_slot(props: Properties) -> str:
            assert property.slot is not None  # Couldn't assert outside get_slot()
            return props[property.slot]

    if property.format & FileFormat.POLYPROP:
        def has_property(props: Properties) -> bool:
            return are_same_name(props[0], name)
    else:
        def has_property(props: Properties) -> bool:
            return True

    if property.type is PropertyType.EMOSEQ:
        def get_codepoints(codepoints: CodePoints) -> CodePoints:
            return codepoints.to_sequence_head()
    else:
        def get_codepoints(codepoints: CodePoints) -> CodePoints:
            return codepoints.to_range()

    def get_data(
        codepoints: CodePoints, properties: Properties
    ) -> None | tuple[CodePoints, object]:
        return (
            (get_codepoints(codepoints), get_slot(properties))
            if has_property(properties)
            else None
        )

    with mirrored_data(property.file, version, root) as lines:
        return sorted(parse(lines, get_data))
