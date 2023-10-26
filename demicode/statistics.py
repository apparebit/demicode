import math
from pathlib import Path
from typing import cast, NamedTuple

import demicode.model as model
from .model import (
    Age,
    BinaryProperty,
    Block,
    Canonical_Combining_Class,
    East_Asian_Width,
    Emoji_Sequence,
    General_Category,
    Grapheme_Cluster_Break,
    Indic_Conjunct_Break,
    Indic_Syllabic_Category,
    PropertyId,
    Script,
    to_property_name,
    Version,
)
from .ucd import OverlapCounter, UnicodeCharacterDatabase
from .ui.render import Renderer


_PROPERTIES: tuple[PropertyId, ...] = (
    BinaryProperty.Default_Ignorable_Code_Point,
    BinaryProperty.Emoji,
    BinaryProperty.Emoji_Component,
    BinaryProperty.Emoji_Modifier,
    BinaryProperty.Emoji_Modifier_Base,
    BinaryProperty.Emoji_Presentation,
    BinaryProperty.Extended_Pictographic,
    BinaryProperty.White_Space,
    Emoji_Sequence,
    Age,
    Block,
    Canonical_Combining_Class,
    East_Asian_Width,
    General_Category,
    Grapheme_Cluster_Break,
    Indic_Conjunct_Break,
    Indic_Syllabic_Category,
    Script,
)


class PropertyInfo(NamedTuple):
    bits: int        # The number of bits to capture all property values
    points: int      # The number of code points with non-default values
    ranges: int      # The number of code point ranges used in UCD file
    max_ranges: int  # The number of code point ranges after combining adjacent ones


def collect_statistics(root: Path, version: Version) -> dict[PropertyId, PropertyInfo]:
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
        counts.append(ucd.count_nondefault_values(property))

    ucd.optimize().validate()
    if not getattr(ucd, 'is_optimized'):  # Work around mypy bug
        raise AssertionError('UCD claims not to be optimized after call to optimize()')

    stats: dict[PropertyId, PropertyInfo] = {}
    for property, (points, ranges) in zip(_PROPERTIES, counts):
        if isinstance(property, BinaryProperty):
            bits = 1
        elif property is Canonical_Combining_Class:
            # The enumeration defines constants only for some values, but the
            # values are drawn from 0-240. Hence we need 8 bits.
            bits = 8
        else:
            values = getattr(model, property.__name__)
            bits = math.ceil(math.log2(len(values)))

        points2, max_ranges = ucd.count_nondefault_values(property)
        if points != points2:
            raise AssertionError(
                f'Property {to_property_name(property)} has {points} != {points2} '
                'non-default codepoints'
            )

        stats[property] = PropertyInfo(bits, points, ranges, max_ranges)

    return stats


def show_statistics(
    version: Version,
    prop_counts: dict[PropertyId, PropertyInfo],
    overlap: OverlapCounter,
    renderer: Renderer,
) -> None:
    renderer.newline()
    v = version.in_short_format()
    renderer.strong(f'UCD {v} Properties (Before / After Range Optimization)')
    renderer.newline()

    def show_heading(text: str) -> None:
        renderer.faint(f' {text:<28}  Bt     Points  Ranges  MinRng')
        renderer.writeln('\n')

    sum_bits = sum_points = sum_ranges = sum_max_ranges = 0

    def show_counts(property: PropertyId) -> None:
        nonlocal sum_bits, sum_points, sum_ranges, sum_max_ranges

        bits, points, ranges, max_ranges = prop_counts[property]
        sum_bits += bits
        sum_points += points
        sum_ranges += ranges
        sum_max_ranges += max_ranges

        renderer.writeln(
            f' {to_property_name(property):<28}  {bits:2,d}  {points:9,d}  '
            f'{ranges:6,d}  {max_ranges:6,d}'
        )

    def show_total() -> None:
        renderer.write(f' {" " * 28}  ')
        renderer.faint('–' * (2 + 2 + 9 + 2 + 6 + 2 + 6))
        renderer.newline()

        renderer.faint(f' {"Subtotal":<28}')
        renderer.writeln(
            f'  {sum_bits:2,d}  {sum_points:9,d}  '
            f'{sum_ranges:6,d}  {sum_max_ranges:6,d}'
        )
        renderer.writeln('\n')

    # ----------------------------------------------------------------------------------

    property: PropertyId

    show_heading('Binary Properties')
    for property in (
        BinaryProperty.Default_Ignorable_Code_Point,
        BinaryProperty.Emoji,
        BinaryProperty.Emoji_Component,
        BinaryProperty.Emoji_Modifier,
        BinaryProperty.Emoji_Modifier_Base,
        BinaryProperty.Emoji_Presentation,
        BinaryProperty.Extended_Pictographic,
        BinaryProperty.White_Space,
    ):
        show_counts(property)
    show_total()

    show_heading('Complex Properties')
    sum_bits = sum_points = sum_ranges = sum_max_ranges = 0
    for property in (
        Age,
        Block,
        Canonical_Combining_Class,
        East_Asian_Width,
        General_Category,
        Grapheme_Cluster_Break,
        Indic_Conjunct_Break,
        Indic_Syllabic_Category,
        Script,
    ):
        show_counts(property)
    show_total()

    show_heading('Sequence Data')
    show_counts(Emoji_Sequence)
    renderer.writeln('\n')

    # ----------------------------------------------------------------------------------

    show_heading('Required Properties I')
    sum_bits = sum_points = sum_ranges = sum_max_ranges = 0
    for property in cast(tuple[PropertyId, ...], (
        BinaryProperty.Emoji_Presentation,
        BinaryProperty.Extended_Pictographic,
        Canonical_Combining_Class,
        East_Asian_Width,
        General_Category,
        Grapheme_Cluster_Break,
        Indic_Syllabic_Category,
        Script,
    )):
        show_counts(property)
    show_total()

    # ----------------------------------------------------------------------------------

    show_heading('Required Properties II')
    sum_bits = sum_points = sum_ranges = sum_max_ranges = 0
    for property in cast(tuple[PropertyId, ...], (
        BinaryProperty.Emoji_Presentation,
        BinaryProperty.Extended_Pictographic,
        East_Asian_Width,
        General_Category,
        Grapheme_Cluster_Break,
        Indic_Conjunct_Break,
    )):
        show_counts(property)
    show_total()

    # ----------------------------------------------------------------------------------

    renderer.faint('    InCB       GCB     Count  (Properties of code points)')

    renderer.writeln()
    assert len(overlap) == 5
    for incb, ocb in (
        (Indic_Conjunct_Break.Extend, Grapheme_Cluster_Break.ZWJ),
        (Indic_Conjunct_Break.Extend, Grapheme_Cluster_Break.Extend),
        (Indic_Conjunct_Break.Linker, Grapheme_Cluster_Break.Extend),
        (None, Grapheme_Cluster_Break.Extend),
        (Indic_Conjunct_Break.Consonant, None),
    ):
        left = '⋯' if incb is None else incb.name
        right = '⋯' if ocb is None else ocb.name
        renderer.writeln(f'{"":<2}  {left:<9}  {right:<6}  {overlap[(incb, ocb)]:5,d}')
    renderer.writeln('\n')

    # ----------------------------------------------------------------------------------

    renderer.link('https://github.com/apparebit/demicode/blob/boss/docs/props.md')
    renderer.newline()
