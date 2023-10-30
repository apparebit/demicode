from bisect import bisect_right as stdlib_bisect_right
from collections import Counter, defaultdict
from collections.abc import Iterator, Sequence, Set
import itertools
import json
import logging
from pathlib import Path
import re
from typing import (
    Any,
    Callable,
    Self,
    TypeAlias,
    TypeVar,
)


from .codepoint import CodePoint, CodePointRange, CodePointSequence
from .mirror import Mirror
from .model import (
    Age,
    Block,
    BinaryProperty,
    Canonical_Combining_Class,
    General_Category,
    CharacterData,
    East_Asian_Width,
    Emoji_Sequence,
    GRAPHEME_CLUSTER_PATTERN,
    Grapheme_Cluster_Break,
    Indic_Conjunct_Break,
    Indic_Syllabic_Category,
    Property,
    PropertyId,
    Script,
)

from .parser import (
    get_range,
    no_range,
    parse,
    simplify_range_data,
    simplify_only_ranges,
    to_property_value,
    to_range_and_string,
)

from .version import Version
from . import __version__


_logger = logging.getLogger(__name__)


OverlapCounter: TypeAlias = Counter[
    tuple[None | Indic_Conjunct_Break, None | Grapheme_Cluster_Break]
]


_T = TypeVar('_T')

# --------------------------------------------------------------------------------------
# Minor sets of code points


_COMBINE_WITH_ENCLOSING_KEYCAPS = frozenset(CodePoint.of(cp) for cp in '#*0123456789')

_FULLWIDTH_PUNCTUATION = frozenset(CodePoint.of(cp) for cp in (
    '\uFF01', '\uFF0C', '\uFF0E', '\uFF1A', '\uFF1B', '\uFF1F'
))


# --------------------------------------------------------------------------------------
# Load some of the more complex UCD Files


_EmojiSequenceEntry: TypeAlias = tuple[
    CodePoint | CodePointSequence, None | str, None | Version
]


def _load_emoji_data_as_sequences(
    mirror: Mirror, version: Version,
) -> Sequence[_EmojiSequenceEntry]:
    assert version == (8, 0, 0)
    with mirror.data('emoji-data.txt', version) as lines:
        return [*parse(lines, lambda cp, _: (no_range(cp), None, None))]


_EMOJI_VERSION = re.compile(r'E(\d+\.\d+)')

def _load_emoji_sequences(
    mirror: Mirror, version: Version,
) -> Sequence[_EmojiSequenceEntry]:
    with mirror.data('emoji-sequences.txt', version) as lines:
        data1 = [*parse(lines, lambda cp, p: (cp, p), with_comment=True)]
    with mirror.data('emoji-zwj-sequences.txt', version) as lines:
        data2 = [*parse(lines, lambda cp, p: (cp, p), with_comment=True)]

    result: list[_EmojiSequenceEntry] = []
    for codepoints, props in itertools.chain(data1, data2):
        name, emoji_version = props[1] if len(props) == 3 else None, props[-1]
        match = _EMOJI_VERSION.match(emoji_version)
        age = None if match is None else Version.of(match.group(1))

        if isinstance(codepoints, (CodePoint, CodePointSequence)):
            result.append((codepoints, name, age))
        else:
            # For basic emoji, emoji-sequences.txt contains ranges of code
            # points and of names. That means some sequence names are missing.
            first_name = last_name = None
            if name is not None:
                first_name, _, last_name = name.partition('..')
            for codepoint in codepoints.codepoints():
                if codepoint == codepoints.start:
                    given_name: None | str = first_name
                elif codepoint == codepoints.stop:
                    given_name = last_name
                else:
                    given_name = None
                result.append((codepoint, given_name, age))
    return result


# --------------------------------------------------------------------------------------
# Look Up


def _is_in_range(codepoint: CodePoint, ranges: Sequence[CodePointRange]) -> bool:
    """Bisect the ranges of a binary property."""
    idx = stdlib_bisect_right(ranges, codepoint, key=lambda range: range.stop)
    range_count = len(ranges)
    if 0 < idx <= range_count and ranges[idx - 1].stop == codepoint:
        idx -= 1
    return 0 <= idx < range_count and codepoint in ranges[idx]


def _bisect_range_data(
    range_data: Sequence[tuple[CodePointRange, *tuple[Any, ...]]], # type: ignore
    codepoint: CodePoint,
) -> int:
    """Bisect the ranges of code point range, property tuples."""
    range_count = len(range_data)
    idx = stdlib_bisect_right(range_data, codepoint, key=lambda rd: rd[0].stop)
    if 0 < idx <= range_count and range_data[idx - 1][0].stop == codepoint:
        idx -= 1

    # Validate result
    if __debug__:
        if idx == range_count:
            if range_count > 0:
                range = range_data[-1][0]
                assert range.stop < codepoint,\
                    f'{codepoint} should come after last {range}'
        else:
            range = range_data[idx][0]
            if codepoint not in range:
                assert codepoint < range.start,\
                     f'{codepoint} should come before {range}'
                if idx > 0:
                    range = range_data[idx-1][0]
                    assert range.stop < codepoint,\
                        f'{codepoint} should come after {range}'

    return idx


# --------------------------------------------------------------------------------------
# The UCD


_TOTAL_ELEMENTS_PATTERN = re.compile(r'# Total elements: (\d+)')

_PROPERTY_RANGES_AND_DEFAULT: dict[type[Property], tuple[str, Property]] = {
    Age: ('_age', Age.Unassigned),
    Block: ('_block', Block.No_Block),
    Canonical_Combining_Class: (
        '_combining_class', Canonical_Combining_Class.Not_Reordered),
    East_Asian_Width: ('_east_asian_width', East_Asian_Width.Neutral),
    General_Category: ('_general_category', General_Category.Unassigned),
    Grapheme_Cluster_Break: ('_grapheme_break', Grapheme_Cluster_Break.Other),
    Indic_Conjunct_Break: ('_indic_conjunct_break', Indic_Conjunct_Break.None_),
    Indic_Syllabic_Category: ('_indic_syllabic', Indic_Syllabic_Category.Other),
    Script: ('_script', Script.Common),
}


class UnicodeCharacterDatabase:
    """
    A convenient interface to interrogating the Unicode Character Database.

    By default, the data used this class is the latest released version of the
    UCD. Since file formats have hardly changed, this class can use older
    versions of the UCD just the same. In either case, it downloads the
    necessary files upon first use and thereafter utilizes the locally mirrored
    versions. Just like the Unicode website has distinct directories for each
    version, the local mirror uses version-specific directories.

    This module defines an eagerly created global instance, `UCD`. That instance
    can be configured with the `use_path()` and `use_version()` methods before
    the first look-up. The configuration is locked in with `prepare()`, which
    downloads necessary UCD files. While client code may explicitly invoke the
    method, that is not required. `UnicodeCharacterDatabase` automatically
    invokes the method as needed, i.e., on look-ups.
    """

    def __init__(
        self,
        root: None | str | Path = None,
        version: None | str | Version = None,
        tick: None | Callable[[], None] = None,
    ) -> None:
        self._is_optimized: bool = False

        self._mirror = mirror = Mirror(root, version, tick)
        version = mirror.version
        _logger.info('mirroring UCD files at "%s"', mirror.root)
        _logger.info('running with UCD version %s', mirror.version)

        with mirror.data('DerivedAge.txt', version) as lines:
            self._age = sorted(parse(
                lines, lambda cp, p: (cp.to_range(), Age(p[0]))
            ), key=get_range)
        with mirror.data('Blocks.txt', version) as lines:
            self._block = [*parse(
                lines, lambda cp, p: (cp.to_range(), Block[to_property_value(p[0])])
            )]
        with mirror.data('DerivedCombiningClass.txt', version) as lines:
            self._combining_class = sorted(parse(
                lines, lambda cp, p: (cp.to_range(), int(p[0]))
            ), key=get_range)
        with mirror.data('DerivedCoreProperties.txt', version) as lines:
            self._default_ignorable = [*parse(lines, lambda cp, p: (
                cp.to_range()
                if p[0] == BinaryProperty.Default_Ignorable_Code_Point.name
                else None
            ))]
        with mirror.data('EastAsianWidth.txt', version) as lines:
            self._east_asian_width = [*parse(lines, lambda cp, p: (
                cp.to_range(), East_Asian_Width(p[0])
            ))]
        if version != (8, 0, 0):
            self._emoji_data: dict[str, list[CodePointRange]] = defaultdict(list)
            with mirror.data('emoji-data.txt', version) as lines:
                for range, label in parse(lines, to_range_and_string):
                    self._emoji_data[label].append(range)
        else:
            # Make sure that look-ups don't fail.
            self._emoji_data = { p.name: [] for p in BinaryProperty if p.is_emoji }
        with mirror.data('emoji-variation-sequences.txt', version) as lines:
            self._emoji_variations = frozenset(dict.fromkeys(parse(
                lines, lambda cp, _: cp.to_sequence_head()
            )))
        with mirror.data('DerivedGeneralCategory.txt', version) as lines:
            # The file covers *all* Unicode code points, so we drop Unassigned.
            # That's consistent with the default category for UnicodeData.txt.
            # Also, Cn accounts for 825,345 out of 1,114,112 code points.
            self._general_category = sorted(parse(
                lines, lambda cp, p: (
                    None if p[0] == 'Cn' else (cp.to_range(), General_Category(p[0]))
                )
            ), key=get_range)
        with mirror.data('GraphemeBreakProperty.txt', version) as lines:
            self._grapheme_break = sorted(parse(
                lines, lambda cp, p: (cp.to_range(), Grapheme_Cluster_Break[p[0]])
            ), key=get_range)
        with mirror.data('DerivedCoreProperties.txt', version) as lines:
            self._indic_conjunct_break = sorted(parse(lines, lambda cp, p: (
                (cp.to_range(), Indic_Conjunct_Break(p[1])) if p[0] == 'InCB' else None
            )))
        with mirror.data('IndicSyllabicCategory.txt', version) as lines:
            self._indic_syllabic = sorted(parse(
                lines, lambda cp, p: (cp.to_range(), Indic_Syllabic_Category[p[0]])
            ), key=get_range)
        with mirror.data('UnicodeData.txt', version) as lines:
            self._name = dict(parse(lines, lambda cp, p: (
                None if p[0].startswith('<') else (cp.to_singleton(), p[0])
            )))
        with mirror.data('Scripts.txt', version) as lines:
            self._script = sorted(parse(
                lines, lambda cp, p: (cp.to_range(), Script[p[0]])
            ), key=get_range)
        with mirror.data('PropList.txt', version) as lines:
            self._white_space = [*parse(lines, lambda cp, p: (
                cp.to_range()
                if p[0] == BinaryProperty.White_Space.name
                else None
            ))]

        # Load list of emoji sequences. UCD 8.0 / E1.0 has no emoji sequence
        # files, but `emoji-data.txt` is so different it is more suitable as a
        # replacement sequence file without name or age. UCD 9.0 / E3.0 and
        # later do contain sequence files, which provide CLDR names for most
        # sequences but not all. Since they are not covered by Unicode's
        # stability policy, they may be more accurate and hence are preferable.
        if version == (8, 0, 0):
            sequences = _load_emoji_data_as_sequences(mirror, version)
        else:
            sequences = _load_emoji_sequences(mirror, version)

        # Also load CLDR annotations with names for emoji sequences. While the
        # primary distribution format for the CLDR is XML, JSON is officially
        # supported through several NPM packages as well. Alas, that means
        # executing NPM's version resolution and download logic in Python. 😜
        annotations: dict[str, str] = {}
        for stem, key1, key2 in (
            ('annotations', 'annotations', 'annotations'),
            ('derived-annotations', 'annotationsDerived', 'annotations'),
        ):
            path = mirror.root / mirror.cldr_filename(stem, '.json')
            with open(path, mode='r') as file:
                raw = json.load(file)
            annotations |= { k: v['tts'][0] for k, v in raw[key1][key2].items() }

        # Try to fill in missing emoji sequence names from CLDR data.
        invalid = False
        self._emoji_sequences: dict[
            CodePoint | CodePointSequence, tuple[None | str, None | Version]
        ] = {}
        for codepoints, name, age in sequences:
            if name is None:
                name = annotations.get(str(codepoints))
                # UCD 9.0 / E3.0 contains sequences without CLDR name
                if name is None and version > (9, 0, 0):
                    _logger.error('emoji sequence %r has no CLDR name', codepoints)
                    invalid = True
            self._emoji_sequences[codepoints] = (name, age)
        if invalid:
            raise AssertionError('UCD is missing data; see log messages')

    def optimize(self) -> Self:
        if self._is_optimized:
            return self

        self._combining_class = [*simplify_range_data(self._combining_class)]
        self._default_ignorable = simplify_only_ranges(self._default_ignorable)
        self._east_asian_width = [*simplify_range_data(self._east_asian_width)]
        for property in self._emoji_data:
            self._emoji_data[property] = (
                simplify_only_ranges(self._emoji_data[property]))
        self._general_category = [*simplify_range_data(self._general_category)]
        self._grapheme_break = [*simplify_range_data(self._grapheme_break)]
        self._indic_conjunct_break = [*simplify_range_data(self._indic_conjunct_break)]
        self._indic_syllabic = [*simplify_range_data(self._indic_syllabic)]
        self._script = [*simplify_range_data(self._script)]
        self._white_space = simplify_only_ranges(self._white_space)
        self._is_optimized = True
        return self

    def validate(self) -> Self:
        invalid = False

        # Check that the number of ingested emoji sequences is the sum of the
        # total counts given in comments in the corresponding files.
        version_root = self.mirror.root / str(self.version)
        text = (version_root / 'emoji-sequences.txt').read_text('utf8')
        entries = sum(int(c) for c in _TOTAL_ELEMENTS_PATTERN.findall(text))
        text = (version_root / 'emoji-zwj-sequences.txt').read_text('utf8')
        entries += sum(int(c) for c in _TOTAL_ELEMENTS_PATTERN.findall(text))
        if len(self._emoji_sequences) != entries:
            _logger.error(
                'UCD has %d emoji sequences even though there should be %d',
                len(self._emoji_sequences),
                entries,
            )
            invalid = True

        # Extended_Pictographic is layered on top of Grapheme_Break. Make sure
        # that code points with former property have Other for latter property.
        grapheme_break = self._grapheme_break
        grapheme_break_count = len(grapheme_break)
        if grapheme_break_count > 0:
            for range in self._emoji_data[BinaryProperty.Extended_Pictographic.name]:
                # All code points in range are Extended_Pictographic
                for codepoint in range.codepoints():
                    if (val := self._resolve(codepoint, grapheme_break, None)) is None:
                        continue
                    _logger.error(
                        'extended pictograph %s %r has grapheme cluster break '
                        '%s, not Other',
                        codepoint, codepoint, val.name
                    )
                    invalid = True

        # Check that code points that have emoji presentation but are not just
        # emoji components are also listed as valid emoji sequences. If they may
        # be combined with variation selectors, check that the sequence code
        # point, U+FE0F is not redundantly included amongst emoji sequences.
        for range in self._emoji_data[BinaryProperty.Emoji_Presentation.name]:
            for cp in range.codepoints():
                if not (
                    CodePoint.REGIONAL_INDICATOR_SYMBOL_LETTER_A
                     <= cp <= CodePoint.REGIONAL_INDICATOR_SYMBOL_LETTER_Z
                ) and cp not in self._emoji_sequences:
                    _logger.error(
                        '%r %s has emoji presentation but is not amongst valid '
                        'emoji sequences', cp, cp
                    )
                    invalid = True
                if cp in self._emoji_variations:
                    redundant = CodePointSequence.of(
                        cp, CodePoint.EMOJI_VARIATION_SELECTOR
                    )
                    if redundant in self._emoji_sequences:
                        _logger.error(
                            'the redundant but valid sequence %r U+FE0F %s is listed '
                            'amongst emoji sequences', cp, cp
                        )
                        invalid = True

        if invalid:
            raise AssertionError('UCD validation failed; see log messages')
        return self

    # ----------------------------------------------------------------------------------
    # Introspecting the Configuration

    @property
    def mirror(self) -> Mirror:
        return self._mirror

    @property
    def version(self) -> Version:
        return self._mirror.version

    @property
    def is_optimized(self) -> bool:
        return self._is_optimized

    # ----------------------------------------------------------------------------------
    # Property Lookup

    def lookup(self, codepoint: CodePoint) -> CharacterData:
        return CharacterData(
            codepoint=codepoint,
            category=self.resolve(codepoint, General_Category),
            east_asian_width=self.resolve(codepoint, East_Asian_Width),
            age=self.resolve(codepoint, Age),
            name=self._name.get(codepoint),
            block=self.resolve(codepoint, Block),
            flags=frozenset(p for p in BinaryProperty if self.test(codepoint, p)),
        )

    def grapheme_cluster(self, codepoint: CodePoint) -> Grapheme_Cluster_Break:
        """Look up the code point's grapheme cluster."""
        if self.test(codepoint, BinaryProperty.Extended_Pictographic):
            return Grapheme_Cluster_Break.Extended_Pictographic
        if codepoint != CodePoint.ZERO_WIDTH_JOINER:
            match self._resolve(codepoint, self._indic_conjunct_break, None):
                case Indic_Conjunct_Break.Consonant:
                    return Grapheme_Cluster_Break.InCB_Consonant
                case Indic_Conjunct_Break.Extend:
                    return Grapheme_Cluster_Break.InCB_Extend
                case Indic_Conjunct_Break.Linker:
                    return Grapheme_Cluster_Break.InCB_Linker
                case _:
                    pass
        return self._resolve(
            codepoint, self._grapheme_break, Grapheme_Cluster_Break.Other
        )

    def count_break_overlap(self) -> OverlapCounter:
        counts: OverlapCounter = Counter()
        icb: None | Indic_Conjunct_Break
        for range, icb in self._indic_conjunct_break:
            # All code points in range have Indic_Conjunct_Break other than None
            for codepoint in range.codepoints():
                gcb = self._resolve(codepoint, self._grapheme_break, None)
                counts[(icb, gcb)] += 1
        for range, gcb in self._grapheme_break:
            if gcb is not Grapheme_Cluster_Break.Extend:
                continue
            for codepoint in range.codepoints():
                icb = self._resolve(codepoint, self._indic_conjunct_break, None)
                if icb is None:
                    counts[(None, gcb)] += 1
        return counts

    # ----------------------------------------------------------------------------------
    # Grapheme Clusters and Their Breaks

    def _to_grapheme_cluster_string(
        self, text: str | CodePointSequence
    ) -> str:
        if isinstance(text, str):
            text = CodePointSequence.from_string(text)
        return ''.join(self.grapheme_cluster(cp).value for cp in text)

    def grapheme_cluster_breaks(self, text: str | CodePointSequence) -> Iterator[int]:
        """
        Iterate over the grapheme cluster breaks for the given string or
        sequence of code points. The implementation has some startup cost
        because it first converts the entire string into a sequence of grapheme
        cluster property values. Thereafter, it uses a regular expression for
        iterating over the grapheme cluster breaks.
        """
        grapheme_cluster_props = self._to_grapheme_cluster_string(text)
        length = len(text)

        index = 0
        yield index

        while index < length:
            grapheme = GRAPHEME_CLUSTER_PATTERN.match(grapheme_cluster_props, index)
            if grapheme is None:
                raise AssertionError(
                    f'could not find next grapheme at position {index} of '
                    f'{text!r} with properties "{grapheme_cluster_props}"'
                )

            index = grapheme.end()
            yield index

    def is_grapheme_cluster(self, text: str | CodePoint | CodePointSequence) -> bool:
        """
        Determine whether the string, code point, or sequence of code points
        forms a single Unicode grapheme cluster. A single code point always is a
        grapheme cluster. So invoking this method on a known code point makes
        little sense. This method nonetheless accepts code points to simplify
        calling code, which often handles code points and code point sequences
        interchangeably.
        """
        if isinstance(text, CodePoint):
            return True
        return [*self.grapheme_cluster_breaks(text)] == [0, len(text)]

    # ----------------------------------------------------------------------------------
    # Test Binary Properties, Count Properties

    def test(self, codepoint: CodePoint, property: BinaryProperty) -> bool:
        if property is BinaryProperty.Default_Ignorable_Code_Point:
            return _is_in_range(codepoint, self._default_ignorable)
        elif property is BinaryProperty.White_Space:
            return _is_in_range(codepoint, self._white_space)
        return _is_in_range(codepoint, self._emoji_data[property.name])

    def _resolve(
        self,
        codepoint: CodePoint,
        ranges: Sequence[tuple[CodePointRange, _T]],
        default: _T,
    ) -> _T:
        index = _bisect_range_data(ranges, codepoint)
        if not (0 <= index < len(ranges)):
            return default
        record = ranges[index]
        return record[1] if codepoint in record[0] else default

    def resolve(
        self, codepoint: CodePoint, property: type[Property]
    ) -> Any:
        """Resolve the codepoint's property."""
        if property is Emoji_Sequence:
            return self.emoji_sequence_data(codepoint)
        else:
            attribute, default = _PROPERTY_RANGES_AND_DEFAULT[property]
            ranges = getattr(self, attribute)
            return self._resolve(codepoint, ranges, default)

    def count(self, selection: Property) -> int:
        attribute, default = _PROPERTY_RANGES_AND_DEFAULT[selection.__class__]
        ranges = getattr(self, attribute)
        result = 0

        if selection == default:
            next = CodePoint.MIN
            for range, _ in ranges:
                previous = range.start.previous()
                if next <= previous:
                    result += previous - next + 1
                next = range.stop.next()
        else:
            for range, range_value in ranges:
                if selection == range_value:
                    result += len(range)

        return result

    def materialize(
        self, selection: BinaryProperty | Property
    ) -> set[CodePoint]:
        result: set[CodePoint] = set()

        if isinstance(selection, BinaryProperty):
            if selection is BinaryProperty.Default_Ignorable_Code_Point:
                ranges = self._default_ignorable
            elif selection is BinaryProperty.White_Space:
                ranges = self._white_space
            else:
                ranges = self._emoji_data[selection.name]

            for range in ranges:
                result |= {cp for cp in range.codepoints()}
            return result

        attribute, default = _PROPERTY_RANGES_AND_DEFAULT[selection.__class__]
        ranges = getattr(self, attribute)

        previous_plus_one: int = CodePoint.MIN
        for range, value in ranges:
            if selection is default:
                if previous_plus_one < range.start:
                    result |= {
                        cp for cp
                        in CodePoint(previous_plus_one).upto(range.start.previous())
                    }
                previous_plus_one = range.stop + 1
            elif selection is value:
                result |= {cp for cp in range.codepoints()}

        if selection is default and previous_plus_one <= CodePoint.MAX:
            result |= {cp for cp in CodePoint(previous_plus_one).upto(CodePoint.MAX)}

        return result

    # def combine(
    #     self, *properties: BinaryProperty | PropertyValue
    # ) -> list[tuple[CodePointRange, dict[str, PropertyValueTypes]]]:
    #     """
    #     Combine the internal range data for the given properties into a single
    #     list of ranges and mappings containing the properties. The latter is
    #     used in lieu of dataclasses so that this method can be used for
    #     exploratory analysis of arbitrary properties.
    #     """
    #     # Collect properties by code point
    #     by_codepoint: list[dict[str, PropertyValueTypes]] = [
    #         dict() for _ in CodePointRange.ALL.codepoints()
    #     ]

    #     for codepoint in CodePointRange.ALL.codepoints():
    #         property_values = by_codepoint[codepoint]

    #         for property in properties:
    #             match property:
    #                 case BinaryProperty():
    #                     value: PropertyValueTypes = self.test(codepoint, property)
    #                     property_values[property] = value
    #                 case Property():
    #                     value = self.resolve(codepoint, property)
    #                     property_values[property] = value

    #     # Compress properties per code point into consecutive ranges.
    #     start: CodePoint = CodePoint.MIN
    #     stop: CodePoint = CodePoint.MIN
    #     pending: None | dict[str, PropertyValueTypes] = None
    #     by_range: list[tuple[CodePointRange, dict[str, PropertyValueTypes]]] = []
    #     for codepoint in CodePointRange.ALL.codepoints():
    #         current = by_codepoint[codepoint]
    #         if pending == current:
    #             stop = codepoint
    #             continue
    #         if pending is not None:
    #             by_range.append((CodePointRange(start, stop), pending))
    #         start = stop = codepoint
    #         pending = current

    #     if pending is not None:
    #         by_range.append((CodePointRange(start, stop), pending))

    #     # Validate the resulting data.
    #     discontinuities = 0
    #     prev: None | CodePointRange = None
    #     for range, property_values in by_range:
    #         if prev is None or prev.stop + 1 == range.start:
    #             prev = range
    #             continue
    #         discontinuities += 1
    #         logger.error('{0!r} does not abut {1!r}', prev.stop, range.start)
    #         prev = range

    #     if discontinuities > 0:
    #         raise ValueError(
    #             f'range compression left {discontinuities} discontinuities')

    #     return by_range

    def count_nondefault_values(self, property: PropertyId) -> tuple[int, int]:
        """
        Count the number of code points that have a non-default property value.
        If the property is accessed by bisecting an ordered list of code point
        ranges, also count the number of distinct ranges. Otherwise, the second
        count is the same. `None` indicates that the property is not currently
        maintained.
        """
        if isinstance(property, BinaryProperty):
            if property.is_emoji:
                return (
                    sum(len(r) for r in self._emoji_data[property.name]),
                    len(self._emoji_data[property.name]),
                )
            if property is BinaryProperty.Default_Ignorable_Code_Point:
                ranges = self._default_ignorable
            elif property is BinaryProperty.White_Space:
                ranges = self._white_space
            else:
                assert False
            return sum(len(r) for r in ranges), len(ranges)

        if property is Emoji_Sequence:
            count = len(self._emoji_sequences)
            return count, count

        attribute, _ = _PROPERTY_RANGES_AND_DEFAULT[property]
        ranges = getattr(self, attribute)
        return sum(len(r[0]) for r in ranges), len(ranges)

    # ----------------------------------------------------------------------------------
    # Emoji sequences

    def _to_codepoints(
        self, codepoints: CodePoint | CodePointSequence | str
    ) -> CodePoint | CodePointSequence:
        """
        Convert any string to a code point sequence and any sequence with only
        one code point to that code point.
        """
        if isinstance(codepoints, str):
            codepoints = CodePointSequence.from_string(codepoints)
        if codepoints.is_singleton():
            codepoints = codepoints.to_singleton()
        return codepoints

    def _to_emoji_info(
        self, codepoints: CodePoint | CodePointSequence
    ) -> None | tuple[None | str, None | Version]:
        """
        Retrieve the name and age of the emoji sequence, if the code points are
        such a sequence indeed. This method only works if the code points
        argument has been converted to the right types with `_to_codepoints()`.
        """
        result = self._emoji_sequences.get(codepoints)
        if result is not None or codepoints.is_singleton():
            return result
        codepoints = codepoints.to_sequence()  # Keep mypy happy
        if len(codepoints) != 2 or codepoints[1] != CodePoint.EMOJI_VARIATION_SELECTOR:
            return None
        return self._emoji_sequences.get(codepoints[0])

    def is_emoji_sequence(
        self, codepoints: CodePoint | CodePointSequence | str
    ) -> bool:
        """
        Determine whether the string or sequence of code points is an emoji.
        Unlike Unicode Emoji's files, this method recognizes code points that
        have emoji presentation and are followed by the emoji variation
        selector.
        """
        return self._to_emoji_info(self._to_codepoints(codepoints)) is not None

    def emoji_sequence_data(
        self, codepoints: CodePoint | CodePointSequence | str
    ) -> tuple[None | str, None | Version]:
        """
        Get the CLDR name and Unicode Emoji age for the emoji sequence.
        Unlike Unicode Emoji's files, this method recognizes code points that
        have emoji presentation and are followed by the emoji variation
        selector.
        """
        return self._to_emoji_info(self._to_codepoints(codepoints)) or (None, None)

    def extended_pictographic_ranges(self) -> Iterator[CodePointRange]:
        """
        Create an iterator over code point ranges that are extended
        pictographic.
        """
        for range in self._emoji_data[BinaryProperty.Extended_Pictographic.name]:
            yield range.to_range()

    # ----------------------------------------------------------------------------------
    # Binary Unicode properties

    @property
    def fullwidth_punctuation(self) -> Set[CodePoint]:
        """Fullwidth punctuation."""
        return _FULLWIDTH_PUNCTUATION

    @property
    def with_keycap(self) -> Set[CodePoint]:
        """All code points that can be combined with U+20E3 as keycaps."""
        return _COMBINE_WITH_ENCLOSING_KEYCAPS

    @property
    def with_emoji_variation(self) -> Set[CodePoint]:
        """
        All code points that participate with text and emoji variations, i.e.,
        can be displayed as more conventional black and white glyphs as well as
        colorful squarish emoji. This property is very much different from
        `with_selector`, which produces the code points triggering variations.
        """
        return self._emoji_variations

    # ----------------------------------------------------------------------------------
    # Width

    def width1(self, codepoint: CodePoint) -> int:
        """
        Determine [wcwidth](https://www.cl.cam.ac.uk/~mgk25/ucs/wcwidth.c) of a
        single code point.
        """
        category = self.resolve(codepoint, General_Category)

        if (
            codepoint == 0
            or category in (
                General_Category.Enclosing_Mark,
                General_Category.Nonspacing_Mark,
                General_Category.Format
            ) and codepoint != CodePoint.SOFT_HYPHEN
            or (
                CodePoint.HANGUL_JUNGSEONG_FILLER
                <= codepoint <= CodePoint.HANGUL_JONGSEONG_SSANGNIEUN
            )
        ):
            return 0

        if (
            category in (General_Category.Surrogate, General_Category.Private_Use)
            or codepoint < 32
            or CodePoint.DELETE <= codepoint < CodePoint.NO_BREAK_SPACE
        ):
            return -1

        return 1 + (
            self.resolve(codepoint, East_Asian_Width)
            in (East_Asian_Width.Fullwidth, East_Asian_Width.Wide)
        )

    def width(self, codepoints: str | CodePointSequence | CodePoint) -> int:
        codepoints = self._to_codepoints(codepoints)

        # First, check for emoji
        if self._to_emoji_info(codepoints) is not None:
            return 2

        # Second, add up East Asian Width.
        total_width = 0
        for codepoint in codepoints.to_sequence():
            width = self.width1(codepoint)
            if width == -1:
                return -1
            total_width += width
        return total_width
