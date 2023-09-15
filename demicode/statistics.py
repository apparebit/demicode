from collections import defaultdict
from pathlib import Path
from typing import cast

from .model import BinaryProperty, Property, Version
from .render import Renderer
from .ucd import UnicodeCharacterDatabase


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
    Property.Indic_Syllabic_Category,
    Property.Script,
)


def collect_statistics(
    root: Path, version: Version
) -> dict[BinaryProperty | Property, list[int]]:
    """
    For the UCD version cached at the given path, before and after optimizing
    its internal representation, and for each of several Unicode properties,
    count the number of code points with property values other than the default
    and the number of code point ranges used to represent that information. If a
    property's number of code points before and after optimizing diverges, this
    function raises an exception.
    """
    data: defaultdict[BinaryProperty | Property, list[int]] = defaultdict(list)

    ucd = UnicodeCharacterDatabase(root, version).prepare().validate()
    if ucd.is_optimized:
        raise AssertionError('UCD claims to be optimized without call to optimize()')
    for property in _PROPERTIES:
        data[property].extend(ucd.count_values(property))

    ucd.optimize().validate()
    if not getattr(ucd, 'is_optimized'):  # Work around mypy bug
        raise AssertionError('UCD claims not to be optimized after call to optimize()')
    for property in _PROPERTIES:
        data[property].extend(ucd.count_values(property))

    for property in _PROPERTIES:
        counts = data[property]
        assert counts[0] == counts[2],\
            f'{property} should have {counts[0]} == {counts[2]} code points'

    return data


def show_statistics(
    version: Version,
    data: dict[BinaryProperty | Property, list[int]],
    renderer: Renderer,
) -> None:
    print()
    v = version.in_short_format()
    print(renderer.strong(f'UCD {v} Properties (Before / After Range Optimization)'))
    print()

    def show_heading(text: str) -> None:
        print(renderer.hint(f' {text:<25}     Points  Ranges  MinRng'))
        print()

    sum_points = sum_ranges = sum_min_ranges = 0

    def show_counts(property: BinaryProperty | Property) -> None:
        nonlocal sum_points, sum_ranges, sum_min_ranges

        points, ranges, _, min_ranges = data[property]
        sum_points += points
        sum_ranges += ranges
        sum_min_ranges += min_ranges

        print(f' {property.name:<25}  {points:9,d}  {ranges:6,d}  {min_ranges:6,d}')

    def show_total() -> None:
        print(f' {" " * 25}  {renderer.hint("–" * (9 + 2 + 6 + 2 + 6))}' )
        heading = renderer.hint(f'{"Subtotal":<25}')
        print(f' {heading}  {sum_points:9,d}  {sum_ranges:6,d}  {sum_min_ranges:6,d}')
        print('\n')

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
    sum_points = sum_ranges = sum_min_ranges = 0
    for property in (
        Property.Canonical_Combining_Class,
        Property.East_Asian_Width,
        Property.General_Category,
        Property.Grapheme_Cluster_Break,
        Property.Indic_Syllabic_Category,
        Property.Script,
    ):
        show_counts(property)
    show_total()

    show_heading('Sequence Data')
    show_counts(Property.Emoji_Sequence)
    print('\n')

    show_heading('Required Properties')
    sum_points = sum_ranges = sum_min_ranges = 0
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
