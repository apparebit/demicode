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
    cast,
    Literal,
    Never,
    overload,
    Self,
    TypeAlias,
    TypeVar,
    TypeVarTuple,
)

from .codepoint import (
    CodePoint,
    CodePointRange,
    CodePointSequence,
)

from .parser import (
    get_range,
    no_range,
    parse,
    simplify_range_data,
    simplify_only_ranges,
    to_range_and_string,
)
from .mirror import (
    mirror_cldr_annotations,
    mirrored_data,
    retrieve_latest_ucd_version,
)
from .model import (
    BinaryProperty,
    GeneralCategory,
    CharacterData,
    EastAsianWidth,
    GRAPHEME_CLUSTER_PATTERN,
    GraphemeClusterBreak,
    IndicConjunctBreak,
    IndicSyllabicCategory,
    Property,
    PropertyValueTypes,
    Script,
    Version,
)
from demicode import __version__


logger = logging.getLogger(__name__)


OverlapCounter: TypeAlias = Counter[
    tuple[None | IndicConjunctBreak, None | GraphemeClusterBreak]
]


_T = TypeVar('_T')
_Ts = TypeVarTuple('_Ts')
_U = TypeVar('_U')


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
    root: Path, version: Version,
) -> Sequence[_EmojiSequenceEntry]:
    assert version == (8, 0, 0)
    with mirrored_data('emoji-data.txt', version, root) as lines:
        return [*parse(lines, lambda cp, _: (no_range(cp), None, None))]


_EMOJI_VERSION = re.compile(r'E(\d+\.\d+)')

def _load_emoji_sequences(
    root: Path, version: Version,
) -> Sequence[_EmojiSequenceEntry]:
    with mirrored_data('emoji-sequences.txt', version, root) as lines:
        data1 = [*parse(lines, lambda cp, p: (cp, p), with_comment=True)]
    with mirrored_data('emoji-zwj-sequences.txt', version, root) as lines:
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


def _load_cldr_annotations(root: Path) -> dict[str, str]:
    path1, path2 = mirror_cldr_annotations(root)
    with open(path1, mode='r') as file:
        raw = json.load(file)
    data1 = {
        k: v['tts'][0] for k,v in raw['annotations']['annotations'].items()
    }
    with open(path2, mode='r') as file:
        raw = json.load(file)
    data2 = {
        k: v['tts'][0] for k,v in raw['annotationsDerived']['annotations'].items()
    }
    return data1 | data2


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


_TOTAL_ELEMENTS_PATTERN = re.compile('# Total elements: (\d+)')


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

    def __init__(self, path: Path, version: None | str | Version = None) -> None:
        self._path = path
        self._version = None if version is None else Version.of(version)
        self._is_prepared: bool = False
        self._is_optimized: bool = False

    def use_path(self, path: Path) -> None:
        """
        Use the given path for locally mirroring UCD files. It is an error to
        invoke this method after this instance has been prepared.
        """
        if self._is_prepared:
            raise ValueError('trying to update UCD path after UCD has been ingested')
        if not path.exists():
            raise ValueError(f'UCD path "{path}" does not exist')
        if not path.is_dir():
            raise ValueError(f'UCD path "{path}" is not a directory')
        self._path = path

    def use_version(self, version: str) -> None:
        """
        Use the given UCD version. It is an error to invoke this method after
        this instance has been prepared.
        """
        if self._is_prepared:
            raise ValueError('trying to update UCD version after UCD has been ingested')
        self._version = Version.of(version).to_ucd()

    # ----------------------------------------------------------------------------------
    # Prepare, Optimize, Validate

    def prepare(self) -> Self:
        """
        Prepare the UCD for active use. This method locks in the current
        configuration and locally mirrors any required UCD as well as CLDR
        files. Repeated invocations have no effect.
        """
        if self._is_prepared:
            return self
        path, version = self._path, self._version
        if version is None:
            self._version = version = retrieve_latest_ucd_version(self._path)
        logger.info('using UCD version %s', version)

        with mirrored_data('DerivedAge.txt', version, path) as lines:
            self._age = sorted(parse(lines, to_range_and_string), key=get_range)
        with mirrored_data('Blocks.txt', version, path) as lines:
            self._block = [*parse(lines, to_range_and_string)]
        with mirrored_data('DerivedCombiningClass.txt', version, path) as lines:
            self._combining_class = sorted(parse(
                lines, lambda cp, p: (cp.to_range(), int(p[0]))
            ), key=get_range)
        with mirrored_data('DerivedCoreProperties.txt', version, path) as lines:
            self._default_ignorable = [*parse(lines, lambda cp, p: (
                cp.to_range()
                if p[0] == BinaryProperty.Default_Ignorable_Code_Point.name
                else None
            ))]
        with mirrored_data('EastAsianWidth.txt', version, path) as lines:
            self._east_asian_width = [*parse(lines, lambda cp, p: (
                cp.to_range(), EastAsianWidth(p[0])
            ))]
        if version != (8, 0, 0):
            self._emoji_data: dict[str, list[CodePointRange]] = defaultdict(list)
            with mirrored_data('emoji-data.txt', version, path) as lines:
                for range, label in parse(lines, to_range_and_string):
                    self._emoji_data[label].append(range)
        else:
            # Make sure that look-ups don't fail.
            self._emoji_data = { p.name: [] for p in BinaryProperty }
        with mirrored_data('emoji-variation-sequences.txt', version, path) as lines:
            self._emoji_variations = frozenset(dict.fromkeys(parse(
                lines, lambda cp, _: cp.to_sequence_head()
            )))
        with mirrored_data('DerivedGeneralCategory.txt', version, path) as lines:
            # The file covers *all* Unicode code points, so we drop Unassigned.
            # That's consistent with the default category for UnicodeData.txt.
            # Also, Cn accounts for 825,345 out of 1,114,112 code points.
            self._general_category = sorted(parse(
                lines, lambda cp, p: (
                    None if p[0] == 'Cn' else (cp.to_range(), GeneralCategory(p[0]))
                )
            ), key=get_range)
        with mirrored_data('GraphemeBreakProperty.txt', version, path) as lines:
            self._grapheme_break = sorted(parse(
                lines, lambda cp, p: (cp.to_range(), GraphemeClusterBreak[p[0]])
            ), key=get_range)
        with mirrored_data('DerivedCoreProperties.txt', version, path) as lines:
            self._indic_conjunct_break = sorted(parse(lines, lambda cp, p: (
                (cp.to_range(), IndicConjunctBreak(p[1]))
                if p[0] == Property.Indic_Conjunct_Break.value
                else None
            )))
        with mirrored_data('IndicSyllabicCategory.txt', version, path) as lines:
            self._indic_syllabic = sorted(parse(
                lines, lambda cp, p: (cp.to_range(), IndicSyllabicCategory[p[0]])
            ), key=get_range)
        with mirrored_data('UnicodeData.txt', version, path) as lines:
            self._name = dict(parse(lines, lambda cp, p: (
                None if p[0].startswith('<') else (cp.to_singleton(), p[0])
            )))
        with mirrored_data('Scripts.txt', version, path) as lines:
            self._script = sorted(parse(
                lines, lambda cp, p: (cp.to_range(), Script[p[0]])
            ), key=get_range)

        # Load list of emoji sequences. UCD 8.0 / E1.0 has no emoji sequence
        # files, but `emoji-data.txt` is so different it is more suitable as a
        # replacement sequence file without name or age. UCD 9.0 / E3.0 and
        # later do contain sequence files, which provide CLDR names for most
        # sequences but not all. Since they are not covered by Unicode's
        # stability policy, they may be more accurate and hence are preferable.
        if version == (8, 0, 0):
            sequences = _load_emoji_data_as_sequences(path, version)
        else:
            sequences = _load_emoji_sequences(path, version)

        # Also load CLDR annotations with names for emoji sequences. While the
        # primary distribution format for the CLDR is XML, JSON is officially
        # supported through several NPM packages as well. Alas, that means
        # executing NPM's version resolution and download logic in Python. 😜
        annotations = _load_cldr_annotations(path)

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
                    logger.error('emoji sequence %r has no CLDR name', codepoints)
                    invalid = True
            self._emoji_sequences[codepoints] = (name, age)
        if invalid:
            raise AssertionError('UCD is missing data; see log messages')

        self._is_prepared = True
        return self

    def optimize(self) -> Self:
        self.prepare()
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
        self._is_optimized = True
        return self

    def validate(self) -> Self:
        self.prepare()
        invalid = False

        # Check that the number of ingested emoji sequences is the sum of the
        # total counts given in comments in the corresponding files.
        ucd = self.path / str(self.version)
        text = (ucd / 'emoji-sequences.txt').read_text('utf8')
        entries = sum(int(c) for c in _TOTAL_ELEMENTS_PATTERN.findall(text))
        text = (ucd / 'emoji-zwj-sequences.txt').read_text('utf8')
        entries += sum(int(c) for c in _TOTAL_ELEMENTS_PATTERN.findall(text))
        if len(self._emoji_sequences) != entries:
            logger.error(
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
                    logger.error(
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
                    logger.error(
                        '%r %s has emoji presentation but is not amongst valid '
                        'emoji sequences', cp, cp
                    )
                    invalid = True
                if cp in self._emoji_variations:
                    redundant = CodePointSequence.of(
                        cp, CodePoint.EMOJI_VARIATION_SELECTOR
                    )
                    if redundant in self._emoji_sequences:
                        logger.error(
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
    def path(self) -> Path:
        self.prepare()
        return self._path

    @property
    def version(self) -> Version:
        self.prepare()
        return cast(Version, self._version)

    @property
    def is_optimized(self) -> bool:
        return self._is_optimized

    # ----------------------------------------------------------------------------------
    # Property Lookup

    def lookup(self, codepoint: CodePoint) -> CharacterData:
        return CharacterData(
            codepoint=codepoint,
            category=self.resolve(codepoint, Property.General_Category),
            east_asian_width=self.resolve(codepoint, Property.East_Asian_Width),
            age=self._resolve(codepoint, self._age, None),
            name=self._name.get(codepoint),
            block=self._resolve(codepoint, self._block, None),
            flags=frozenset(p for p in BinaryProperty if self.test(codepoint, p)),
        )

    def grapheme_cluster(self, codepoint: CodePoint) -> GraphemeClusterBreak:
        """Look up the code point's grapheme cluster."""
        if self.test(codepoint, BinaryProperty.Extended_Pictographic):
            return GraphemeClusterBreak.Extended_Pictographic
        if codepoint != CodePoint.ZERO_WIDTH_JOINER:
            match self._resolve(codepoint, self._indic_conjunct_break, None):
                case IndicConjunctBreak.Consonant:
                    return GraphemeClusterBreak.InCB_Consonant
                case IndicConjunctBreak.Extend:
                    return GraphemeClusterBreak.InCB_Extend
                case IndicConjunctBreak.Linker:
                    return GraphemeClusterBreak.InCB_Linker
        return self._resolve(
            codepoint, self._grapheme_break, GraphemeClusterBreak.Other
        )

    def count_break_overlap(self) -> OverlapCounter:
        counters: OverlapCounter = Counter()
        for range, icb in self._indic_conjunct_break:
            # All code points in range have Indic_Conjunct_Break other than None
            for codepoint in range.codepoints():
                gcb = self._resolve(codepoint, self._grapheme_break, None)
                counters[(icb, gcb)] += 1
        for range, gcb in self._grapheme_break:
            if gcb is not GraphemeClusterBreak.Extend:
                continue
            counters[(None, gcb)] += len(range)

        return counters

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
        self.prepare()
        if property is BinaryProperty.Default_Ignorable_Code_Point:
            return _is_in_range(codepoint, self._default_ignorable)
        return _is_in_range(codepoint, self._emoji_data[property.name])

    def _ranges_default(
        self, property: Property
    ) -> tuple[list[tuple[CodePointRange, Any]], Any]:
        self.prepare()
        match property:
            case Property.Canonical_Combining_Class:
                return self._combining_class, 0
            case Property.East_Asian_Width:
                return self._east_asian_width, EastAsianWidth.Neutral
            case Property.Emoji_Sequence:
                raise NotImplementedError()
            case Property.General_Category:
                return self._general_category, GeneralCategory.Unassigned
            case Property.Grapheme_Cluster_Break:
                return self._grapheme_break, GraphemeClusterBreak.Other
            case Property.Indic_Conjunct_Break:
                return self._indic_conjunct_break, IndicConjunctBreak.None_
            case Property.Indic_Syllabic_Category:
                return self._indic_syllabic, IndicSyllabicCategory.Other
            case Property.Script:
                return self._script, Script.Common

    def _resolve(
        self,
        codepoint: CodePoint,
        ranges: Sequence[tuple[CodePointRange, _T]],
        default: _T,
    ) -> _T:
        self.prepare()
        index = _bisect_range_data(ranges, codepoint)
        if not (0 <= index < len(ranges)):
            return default
        record = ranges[index]
        return record[1] if codepoint in record[0] else default

    @overload
    def resolve(
        self, codepoint: CodePoint, property: Literal[Property.Canonical_Combining_Class]
    ) -> int:
        ...
    @overload
    def resolve(
        self, codepoint: CodePoint, property: Literal[Property.East_Asian_Width]
    ) -> EastAsianWidth:
        ...
    @overload
    def resolve(
        self, codepoint: CodePoint, property: Literal[Property.Emoji_Sequence]
    ) -> Never:
        ...
    @overload
    def resolve(
        self, codepoint: CodePoint, property: Literal[Property.General_Category]
    ) -> GeneralCategory:
        ...
    @overload
    def resolve(
        self, codepoint: CodePoint, property: Literal[Property.Grapheme_Cluster_Break]
    ) -> GraphemeClusterBreak:
        ...
    @overload
    def resolve(
        self, codepoint: CodePoint, property: Literal[Property.Indic_Conjunct_Break]
    ) -> IndicConjunctBreak:
        ...
    @overload
    def resolve(
        self, codepoint: CodePoint, property: Literal[Property.Indic_Syllabic_Category]
    ) -> IndicSyllabicCategory:
        ...
    @overload
    def resolve(
        self, codepoint: CodePoint, property: Literal[Property.Script]
    ) -> Script:
        ...
    @overload
    def resolve(
        self, codepoint: CodePoint, property: Property
    ) -> PropertyValueTypes | Never:
        ...
    def resolve(
        self, codepoint: CodePoint, property: Property
    ) -> Any:
        """Resolve the codepoint's property."""
        self.prepare()
        if property is Property.Emoji_Sequence:
            return self.emoji_sequence_data(codepoint)
        else:
            ranges, default = self._ranges_default(property)
            return self._resolve(codepoint, ranges, default)

    def combine(
        self, *properties: BinaryProperty | Property
    ) -> list[tuple[CodePointRange, dict[str, PropertyValueTypes]]]:
        """
        Combine the internal range data for the given properties into a single
        list of ranges and mappings containing the properties. The latter is
        used in lieu of dataclasses so that this method can be used for
        exploratory analysis of arbitrary properties.
        """
        # Collect properties by code point
        by_codepoint: list[dict[str, PropertyValueTypes]] = [
            dict() for _ in CodePointRange.ALL.codepoints()
        ]

        for codepoint in CodePointRange.ALL.codepoints():
            property_values = by_codepoint[codepoint]

            for property in properties:
                match property:
                    case BinaryProperty():
                        value: PropertyValueTypes = self.test(codepoint, property)
                        property_values[property] = value
                    case Property():
                        value = self.resolve(codepoint, property)
                        property_values[property] = value

        # Compress properties per code point into consecutive ranges.
        start: CodePoint = CodePoint.MIN
        stop: CodePoint = CodePoint.MIN
        pending: None | dict[str, PropertyValueTypes] = None
        by_range: list[tuple[CodePointRange, dict[str, PropertyValueTypes]]] = []
        for codepoint in CodePointRange.ALL.codepoints():
            current = by_codepoint[codepoint]
            if pending == current:
                stop = codepoint
                continue
            if pending is not None:
                by_range.append((CodePointRange(start, stop), pending))
            start = stop = codepoint
            pending = current

        if pending is not None:
            by_range.append((CodePointRange(start, stop), pending))

        # Validate the resulting data.
        discontinuities = 0
        prev: None | CodePointRange = None
        for range, property_values in by_range:
            if prev is None or prev.stop + 1 == range.start:
                prev = range
                continue
            discontinuities += 1
            logger.error('{0!r} does not abut {1!r}', prev.stop, range.start)
            prev = range

        if discontinuities > 0:
            raise ValueError(
                f'range compression left {discontinuities} discontinuities')

        return by_range

    def count_values(
        self,
        property: BinaryProperty | Property,
    ) -> tuple[int, int]:
        """
        Count the number of code points that have a non-default property value.
        If the property is accessed by bisecting an ordered list of code point
        ranges, also count the number of distinct ranges. Otherwise, the second
        count is the same. `None` indicates that the property is not currently
        maintained.
        """
        self.prepare()
        match property:
            case BinaryProperty.Default_Ignorable_Code_Point:
                return (
                    sum(len(r) for r in self._default_ignorable),
                    len(self._default_ignorable),
                )
            case BinaryProperty():
                return (
                    sum(len(r) for r in self._emoji_data[property.name]),
                    len(self._emoji_data[property.name]),
                )
            case Property.Emoji_Sequence:
                count = len(self._emoji_sequences)
                return count, count
            case Property():
                ranges, _ = self._ranges_default(property)
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
        self.prepare()
        return self._emoji_variations

    # ----------------------------------------------------------------------------------
    # Width

    def width1(self, codepoint: CodePoint) -> int:
        """
        Determine [wcwidth](https://www.cl.cam.ac.uk/~mgk25/ucs/wcwidth.c) of a
        single code point.
        """
        category = self.resolve(codepoint, Property.General_Category)

        if (
            codepoint == 0
            or category in (
                GeneralCategory.Enclosing_Mark,
                GeneralCategory.Nonspacing_Mark,
                GeneralCategory.Format
            ) and codepoint != CodePoint.SOFT_HYPHEN
            or (
                CodePoint.HANGUL_JUNGSEONG_FILLER
                <= codepoint <= CodePoint.HANGUL_JONGSEONG_SSANGNIEUN
            )
        ):
            return 0

        if (
            category in (GeneralCategory.Surrogate, GeneralCategory.Private_Use)
            or codepoint < 32
            or CodePoint.DELETE <= codepoint < CodePoint.NO_BREAK_SPACE
        ):
            return -1

        return 1 + (
            self.resolve(codepoint, Property.East_Asian_Width)
            in (EastAsianWidth.Fullwidth, EastAsianWidth.Wide)
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
