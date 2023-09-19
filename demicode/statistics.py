import math
from pathlib import Path
from typing import cast, NamedTuple

import demicode.model as model
from .model import (
    BinaryProperty,
    Property,
    Version,
)
from .render import Renderer
from .ucd import OverlapCounter, UnicodeCharacterDatabase


_PROPERTIES: tuple[BinaryProperty | Property, ...] = (
    BinaryProperty.Emoji,
    BinaryProperty.Emoji_Component,
    BinaryProperty.Emoji_Modifier,
    BinaryProperty.Emoji_Modifier_Base,
    BinaryProperty.Emoji_Presentation,
    BinaryProperty.Extended_Pictographic,
    Property.Emoji_Sequence,
    Property.Canonical_Combining_Class,
    Property.East_Asian_Width,
    Property.General_Category,
    Property.Grapheme_Cluster_Break,
    Property.Indic_Conjunct_Break,
    Property.Indic_Syllabic_Category,
    Property.Script,
)


class PropertyInfo(NamedTuple):
    bits: int        # The number of bits to capture all property values
    points: int      # The number of code points with non-default values
    ranges: int      # The number of code point ranges used in UCD file
    max_ranges: int  # The number of code point ranges after combining adjacent ones


def collect_statistics(
    root: Path, version: Version
) -> dict[BinaryProperty | Property, PropertyInfo]:
    """
    For the UCD version cached at the given path and for each of several Unicode
    properties, collect the number of distinct values for the Unicode property,
    the number of code points with values other than the default, the number of
    code point ranges in the UCD file, and the number of code point ranges after
    combining adjacent ranges for the same property value.
    """
    ucd = UnicodeCharacterDatabase(root, version).prepare().validate()
    if ucd.is_optimized:
        raise AssertionError('UCD claims to be optimized without call to optimize()')
    counts: list[tuple[int, int]] = []
    for property in _PROPERTIES:
        counts.append(ucd.count_values(property))

    ucd.optimize().validate()
    if not getattr(ucd, 'is_optimized'):  # Work around mypy bug
        raise AssertionError('UCD claims not to be optimized after call to optimize()')

    stats: dict[BinaryProperty | Property, PropertyInfo] = {}
    for property, (points, ranges) in zip(_PROPERTIES, counts):
        if isinstance(property, BinaryProperty):
            bits = 1
        elif property is Property.Canonical_Combining_Class:
            # The enumeration defines constants only for some values, but the
            # values are drawn from 0-240. Hence we need 8 bits.
            bits = 8
        else:
            values = getattr(model, property.name.replace('_', ''))
            bits = math.ceil(math.log2(len(values)))

        points2, max_ranges = ucd.count_values(property)
        if points != points2:
            raise AssertionError(
                f'Property {property.name} has {points} != {points2} '
                'non-default codepoints'
            )

        stats[property] = PropertyInfo(bits, points, ranges, max_ranges)

    return stats


def show_statistics(
    version: Version,
    prop_counts: dict[BinaryProperty | Property, PropertyInfo],
    overlap: OverlapCounter,
    renderer: Renderer,
) -> None:
    print()
    v = version.in_short_format()
    print(renderer.strong(f'UCD {v} Properties (Before / After Range Optimization)'))
    print()

    def show_heading(text: str) -> None:
        print(renderer.hint(f' {text:<25}  Bt     Points  Ranges  MinRng'))
        print()

    sum_bits = sum_points = sum_ranges = sum_max_ranges = 0

    def show_counts(property: BinaryProperty | Property) -> None:
        nonlocal sum_bits, sum_points, sum_ranges, sum_max_ranges

        bits, points, ranges, max_ranges = prop_counts[property]
        sum_bits += bits
        sum_points += points
        sum_ranges += ranges
        sum_max_ranges += max_ranges

        print(
            f' {property.name:<25}  {bits:2,d}  {points:9,d}  '
            f'{ranges:6,d}  {max_ranges:6,d}'
        )

    def show_total() -> None:
        print(f' {" " * 25}  {renderer.hint("–" * (2 + 2 + 9 + 2 + 6 + 2 + 6))}' )
        heading = renderer.hint(f'{"Subtotal":<25}')
        print(
            f' {heading}  {sum_bits:2,d}  {sum_points:9,d}  '
            f'{sum_ranges:6,d}  {sum_max_ranges:6,d}'
        )
        print('\n')

    # ----------------------------------------------------------------------------------

    property: BinaryProperty | Property

    show_heading('Binary Properties')
    for property in (
        BinaryProperty.Emoji,
        BinaryProperty.Emoji_Component,
        BinaryProperty.Emoji_Modifier,
        BinaryProperty.Emoji_Modifier_Base,
        BinaryProperty.Emoji_Presentation,
        BinaryProperty.Extended_Pictographic,
    ):
        show_counts(property)
    show_total()

    show_heading('Complex Properties')
    sum_bits = sum_points = sum_ranges = sum_max_ranges = 0
    for property in (
        Property.Canonical_Combining_Class,
        Property.East_Asian_Width,
        Property.General_Category,
        Property.Grapheme_Cluster_Break,
        Property.Indic_Conjunct_Break,
        Property.Indic_Syllabic_Category,
        Property.Script,
    ):
        show_counts(property)
    show_total()

    show_heading('Sequence Data')
    show_counts(Property.Emoji_Sequence)
    print('\n')

    # ----------------------------------------------------------------------------------

    show_heading('Required Properties I')
    sum_bits = sum_points = sum_ranges = sum_max_ranges = 0
    for property in cast(tuple[BinaryProperty | Property, ...], (
        BinaryProperty.Emoji_Presentation,
        BinaryProperty.Extended_Pictographic,
        Property.Canonical_Combining_Class,
        Property.East_Asian_Width,
        Property.General_Category,
        Property.Grapheme_Cluster_Break,
        Property.Indic_Syllabic_Category,
        Property.Script,
    )):
        show_counts(property)
    show_total()

    # ----------------------------------------------------------------------------------

    show_heading('Required Properties II')
    sum_bits = sum_points = sum_ranges = sum_max_ranges = 0
    for property in cast(tuple[BinaryProperty | Property, ...], (
        BinaryProperty.Emoji_Presentation,
        BinaryProperty.Extended_Pictographic,
        Property.East_Asian_Width,
        Property.General_Category,
        Property.Grapheme_Cluster_Break,
        Property.Indic_Conjunct_Break,
    )):
        show_counts(property)
    show_total()

    # ----------------------------------------------------------------------------------

    print(renderer.hint('    InCB       GCB     Count  (Properties of code points)'))

    print()
    for incb, ocb in overlap.keys():
        left = '⋯' if incb is None else incb.name
        right = '⋯' if ocb is None else ocb.name
        print(f'{"":<2}  {left:<9}  {right:<6}  {overlap[(incb, ocb)]:5,d}')
    print('\n')

    # ----------------------------------------------------------------------------------

    print(renderer.hint(
        'https://github.com/apparebit/demicode/blob/boss/docs/props.md'
    ))
    print()
