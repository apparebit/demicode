from bisect import bisect_right as stdlib_bisect_right
from collections import defaultdict
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
    extract_default,
    ingest,
    simplify_range_data,
    simplify_only_ranges,
    to_range_and_string,
)
from .mirror import (
    local_cache_directory,
    mirror_cldr_annotations,
    mirror_unicode_data,
    retrieve_latest_ucd_version,
)
from .model import (
    BinaryProperty,
    GeneralCategory,
    CharacterData,
    ComplexProperty,
    EastAsianWidth,
    EmojiSequence,
    GRAPHEME_CLUSTER_PATTERN,
    GraphemeCluster,
    Version,
    VersioningError,
)
from demicode import __version__


logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------------------
# Minor sets of code points


_COMBINE_WITH_ENCLOSING_KEYCAPS = frozenset(CodePoint.of(cp) for cp in '#*0123456789')

_FULLWIDTH_PUNCTUATION = frozenset(CodePoint.of(cp) for cp in (
    '\uFF01', '\uFF0C', '\uFF0E', '\uFF1A', '\uFF1B', '\uFF1F'
))

_LINE_BREAKS = frozenset(CodePoint.of(cp) for cp in (
    '\x0A', # LINE FEED
    '\x0B', # LINE TABULATION
    '\x0C', # FORM FEED
    '\x0D', # CARRIAGE RETURN
    '\x85', # NEXT LINE
    '\u2028', # LINE SEPARATOR (Zl)
    '\u2029', # PARAGRAPH SEPARATOR (Zp)
))


# --------------------------------------------------------------------------------------
# Retrieval of Specific Data


def _retrieve_general_info(
    path: Path, version: Version
) -> tuple[list[tuple[CodePointRange, str, str]], dict[CodePoint, tuple[str, str]]]:
    path = mirror_unicode_data(path, 'UnicodeData.txt', version)
    _, data = ingest(path, lambda cp, p: (cp.to_singleton(), p[0], p[1]))

    info_ranges: list[tuple[CodePointRange, str, str]] = []
    info_entries: dict[CodePoint, tuple[str, str]] = {}

    raw_entries = iter(data)
    while True:
        try:
            codepoint, name, category = next(raw_entries)
        except StopIteration:
            break
        if not name.endswith(', First>'):
            if codepoint in info_entries:
                raise ValueError(f'"UnicodeData.txt" contains duplicate {codepoint}')
            info_entries[codepoint] = name, GeneralCategory(category)
            continue

        try:
            codepoint2, name2, category2 = next(raw_entries)
        except StopIteration:
            raise ValueError(f'"UnicodeData.txt" contains "First" without "Last"')
        if category != category2:
            raise ValueError(
                '"UnicodeData.txt" contains "First" and "Last" with divergent '
                f'categories {category} and {category2}')
        stem, _, _ = name[1:].rpartition(',')
        stem2, _, _ = name2[1:].rpartition(',')
        if stem is None or stem != stem2:
            raise ValueError(
                '"UnicodeData.txt" contains "First" and "Last" with divergent '
                f'names {stem} and {stem2}')
        info_ranges.append(
            (CodePointRange.of(codepoint, codepoint2), stem, GeneralCategory(category))
        )

    return info_ranges, info_entries


def _retrieve_grapheme_cluster_properties(
    path: Path, version: Version
) -> tuple[
    GraphemeCluster,
    list[tuple[CodePointRange, GraphemeCluster]]
]:
    file = 'GraphemeBreakProperty.txt'
    path = mirror_unicode_data(path, file, version)
    defaults, data = ingest(
        path, lambda cp, p: (cp.to_range(), GraphemeCluster[p[0]]))
    return (
        extract_default(defaults, GraphemeCluster.Other, 'grapheme cluster break'),
        sorted(data, key=lambda d: d[0])
    )


def _retrieve_blocks(path: Path, version: Version) -> list[tuple[CodePointRange, str]]:
    path = mirror_unicode_data(path, 'Blocks.txt', version)
    _, data = ingest(path, to_range_and_string)
    return data


def _retrieve_ages(path: Path, version: Version) -> list[tuple[CodePointRange, str]]:
    path = mirror_unicode_data(path, 'DerivedAge.txt', version)
    _, data = ingest(path, to_range_and_string)
    return sorted(data, key=lambda d: d[0])


def _retrieve_default_ignorable(path: Path, version: Version) -> list[CodePointRange]:
    path = mirror_unicode_data(path, 'DerivedCoreProperties.txt', version)
    _, data = ingest(path, to_range_and_string)
    return [r for r, p in data if p == BinaryProperty.Default_Ignorable_Code_Point.name]


def _retrieve_widths(
    path: Path, version: Version
) -> tuple[EastAsianWidth, list[tuple[CodePointRange, EastAsianWidth]]]:
    path = mirror_unicode_data(path, 'EastAsianWidth.txt', version)
    defaults, data = ingest(path, lambda cp, p: (cp.to_range(), EastAsianWidth(p[0])))
    return (
        extract_default(defaults, EastAsianWidth.Neutral, 'East Asian width'),
        data
    )


def _retrieve_emoji_data(
    path: Path, version: Version
) -> dict[str, list[CodePointRange]]:
    try:
        path = mirror_unicode_data(path, 'emoji-data.txt', version)
    except VersioningError:
        logger.info('skipping emoji data for UCD %s', version)
        return defaultdict(list)

    _, raw_data = ingest(path, to_range_and_string)

    data = defaultdict(list)
    for range, label in raw_data:
        data[label].append(range)

    return data


def _retrieve_emoji_variations(path: Path, version: Version) -> list[CodePoint]:
    try:
        path = mirror_unicode_data(path, 'emoji-variation-sequences.txt', version)
    except VersioningError:
        logger.info('skipping emoji variation sequences for UCD %s', version)
        return []

    _, data = ingest(path, lambda cp, _: cp.to_sequence()[0])
    return list(dict.fromkeys(data)) # Remove all duplicates while preserving order


_EMOJI_VERSION = re.compile(r'E(\d+\.\d+)')

_EmojiSequenceEntry: TypeAlias = tuple[
    CodePoint | CodePointSequence, EmojiSequence, None | str, None | Version]

def _retrieve_emoji_sequences(
    root: Path, version: Version
) -> list[_EmojiSequenceEntry]:
    try:
        path = mirror_unicode_data(root, 'emoji-sequences.txt', version)
    except VersioningError:
        logger.info('skipping emoji sequences for UCD %s', version)
        return []

    _, data1 = ingest(
        path,
        lambda cp, p: (cp, EmojiSequence(p[0]), p[1], p[2]),
        with_comment=True,
    )

    path = mirror_unicode_data(root, 'emoji-zwj-sequences.txt', version)
    _, data2 = ingest(
        path,
        lambda cp, p: (cp, EmojiSequence(p[0]), p[1], p[2]),
        with_comment=True,
    )

    result: list[_EmojiSequenceEntry] = []
    for codepoints, prop, name, emoji_version in itertools.chain(data1, data2):
        match = _EMOJI_VERSION.match(emoji_version)
        age = None if match is None else Version.of(match.group(1))

        if isinstance(codepoints, (CodePoint, CodePointSequence)):
            result.append((codepoints, prop, name, age))
        else:
            # For basic emoji, emoji-sequences.txt contains ranges of code
            # points and of names. That means some sequence names are missing.
            first_name, _, last_name = name.partition('..')
            for codepoint in codepoints.codepoints():
                if codepoint == codepoints.start:
                    given_name: None | str = first_name
                elif codepoint == codepoints.stop:
                    given_name = last_name
                else:
                    given_name = None
                result.append((codepoint, prop, given_name, age))
    return result


_MISC_PROPS = ('White_Space', 'Dash', 'Noncharacter_Code_Point', 'Variation_Selector')

def _retrieve_misc_props(path: Path, version: Version) -> dict[str, set[CodePoint]]:
    path = mirror_unicode_data(path, 'PropList.txt', version)
    _, data = ingest(path, to_range_and_string)

    # It might be a good idea to actually measure performance and memory impact
    # of bisecting ranges versus hashing code points. Until such times, however,
    # I prefer the set-based interface.
    misc_props: dict[str, set[CodePoint]] = defaultdict(set)
    for datum in data:
        if (property := datum[1]) in _MISC_PROPS:
            codepoints = misc_props[property]
            for cp in datum[0].codepoints():
                codepoints.add(cp)
    return misc_props


def _retrieve_cldr_annotations(root: Path) -> dict[str, str]:
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
    idx = stdlib_bisect_right(ranges, codepoint, key=lambda range: range.stop)
    range_count = len(ranges)
    if 0 < idx <= range_count and ranges[idx - 1].stop == codepoint:
        idx -= 1
    return 0 <= idx < range_count and codepoint in ranges[idx]


def _bisect_range_data(
    range_data: Sequence[tuple[CodePointRange, *tuple[Any, ...]]], # type: ignore
    codepoint: CodePoint,
) -> int:
    idx = stdlib_bisect_right(range_data, codepoint, key=lambda rd: rd[0].stop)
    if 0 < idx <= len(range_data) and range_data[idx - 1][0].stop == codepoint:
        idx -= 1

    # Validate result
    if __debug__:
        if idx == len(range_data):
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


_T = TypeVar('_T')
_Ts = TypeVarTuple('_Ts')
_U = TypeVar('_U')

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

    def __init__(self, path: Path, version: None | str = None) -> None:
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

        self._info_ranges, self._info_entries = _retrieve_general_info(path, version)
        self._block_ranges = _retrieve_blocks(path, version)
        self._age_ranges = _retrieve_ages(path, version)
        self._default_ignorable = _retrieve_default_ignorable(path, version)
        self._width_default, self._width_ranges = _retrieve_widths(path, version)
        self._grapheme_default, self._grapheme_props = (
            _retrieve_grapheme_cluster_properties(path, version))
        self._emoji_data = _retrieve_emoji_data(path, version)
        self._emoji_variations = frozenset(_retrieve_emoji_variations(path, version))

        # emoji-sequences.txt contains ranges of basic emoji and their names,
        # which means that some names aren't listed. To make matters worse,
        # these aren't UCD code point names but CLDR emoji sequence names. While
        # it is tempting to fall back onto UCD names, CLDR names are not fixed
        # and thus may be more descriptive. The CLDR is distributed as XML,
        # though an official JSON distribution exists as well. Since those
        # packages are distributed through NPM, this module includes code to
        # download them—of course, written in Python. 😜
        invalid = False
        annotations = _retrieve_cldr_annotations(path)
        emoji_sequences: dict[
            CodePoint | CodePointSequence, tuple[str, None | Version]
        ] = {}
        for codepoints, _, name, age in _retrieve_emoji_sequences(path, version):
            if name is None:
                name = annotations.get(str(codepoints))
                if name is None:
                    logger.error('emoji sequence %r has no CLDR name', codepoints)
                    invalid = True
            # The cast is safe because raising of exception is only delayed.
            emoji_sequences[codepoints] = (cast(str, name), age)
        self._emoji_sequences = emoji_sequences
        if invalid:
            raise AssertionError('UCD is missing data; see log messages')

        # Fill in miscellaneous properties.
        misc_props = _retrieve_misc_props(path, version)
        self._whitespace = frozenset(misc_props[BinaryProperty.White_Space.name])
        self._dashes = frozenset(misc_props[BinaryProperty.Dash.name])
        self._noncharacters = frozenset(
            misc_props[BinaryProperty.Noncharacter_Code_Point.name])
        self._variation_selectors = frozenset(
            misc_props[BinaryProperty.Variation_Selector.name])

        self._is_prepared = True
        return self

    def optimize(self) -> Self:
        self.prepare()
        if self._is_optimized:
            return self

        self._grapheme_props = [*simplify_range_data(self._grapheme_props)]
        self._width_ranges = [*simplify_range_data(self._width_ranges)]
        self._default_ignorable = simplify_only_ranges(self._default_ignorable)
        for property in self._emoji_data:
            self._emoji_data[property] = (
                simplify_only_ranges(self._emoji_data[property]))
        self._is_optimized = True
        return self

    def validate(self) -> Self:
        self.prepare()
        invalid = False

        # Check that Extended_Pictographic code points have grapheme cluster
        # property Other only.
        grapheme_props = self._grapheme_props
        for range in self._emoji_data[BinaryProperty.Extended_Pictographic]:
            for codepoint in range.codepoints():
                entry = grapheme_props[_bisect_range_data(grapheme_props, codepoint)]
                if codepoint in entry[0]:
                    logger.error(
                        'extended pictograph %s %r has grapheme cluster break '
                        '%s, not Other',
                        codepoint, codepoint, entry[1].name
                    )
                    invalid = True

        # Check that the number of ingested emoji sequences is the same as the
        # sum of total counts in UCD files.
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

        # Check that code points that have emoji presentation but are not just
        # emoji components are also listed as valid emoji sequences. If they may
        # be combined with variation selectors, check that the sequence code
        # point, U+FE0F is not redundantly included amongst emoji sequences.
        emoji_selector = CodePoint.of(0xFE0F)
        for range in self._emoji_data['Emoji_Presentation']:
            for cp in range.codepoints():
                if not (0x1F1E6 <= cp <= 0x1F1FF) and cp not in self._emoji_sequences:
                    logger.error(
                        '%r %s has emoji presentation but is not amongst valid '
                        'emoji sequences', cp, cp
                    )
                    invalid = True
                if cp in self._emoji_variations:
                    redundant = CodePointSequence.of(cp, emoji_selector)
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
            category=self.category(codepoint),
            east_asian_width=self.east_asian_width(codepoint),
            age=self.age(codepoint),
            name=self.name(codepoint),
            block=self.block(codepoint),
            flags=frozenset(
                p for p in BinaryProperty if self.test_property(codepoint, p)
            ),
        )

    @overload
    def _resolve_info(
        self, codepoint: CodePoint, offset: Literal[0]
    ) -> None | str:
        ...
    @overload
    def _resolve_info(
        self, codepoint: CodePoint, offset: Literal[1]
    ) -> None | GeneralCategory:
        ...
    def _resolve_info(
        self, codepoint: CodePoint, offset: Literal[0,1]
    ) -> None | str | GeneralCategory:
        self.prepare()
        try:
            return self._info_entries[codepoint][offset]
        except KeyError:
            for range, *props in self._info_ranges:
                if codepoint in range:
                    return props[offset]
        return None

    def name(self, codepoint: CodePoint) -> None | str:
        """Look up the code point's name."""
        return self._resolve_info(codepoint, 0)

    def category(self, codepoint: CodePoint) -> GeneralCategory:
        """Look up the code point's category"""
        category = self._resolve_info(codepoint, 1)
        return GeneralCategory.Unassigned if category is None else category

    def _resolve(
        self,
        codepoint: CodePoint,
        ranges: Sequence[tuple[CodePointRange, *_Ts]], # type: ignore[valid-type]
        default: _U,
    ) -> _T | _U:
        self.prepare()
        record = ranges[_bisect_range_data(ranges, codepoint)]
        return record[1] if codepoint in record[0] else default

    def block(self, codepoint: CodePoint) -> None | str:
        """Look up the code point's block."""
        return self._resolve(codepoint, self._block_ranges, None)

    def age(self, codepoint: CodePoint) -> None | str:
        """Look up the code point's age, i.e., version when it was assigned."""
        return self._resolve(codepoint, self._age_ranges, None)

    def east_asian_width(self, codepoint: CodePoint) -> EastAsianWidth:
        """Look up the code point's East Asian width."""
        return self._resolve(codepoint, self._width_ranges, self._width_default)

    def grapheme_cluster_property(
        self, codepoint: CodePoint
    ) -> GraphemeCluster:
        """Look up the code point's grapheme cluster break class."""
        if self.test_property(codepoint, BinaryProperty.Extended_Pictographic):
            return GraphemeCluster.Extended_Pictographic
        return self._resolve(codepoint, self._grapheme_props, self._grapheme_default)

    def grapheme_cluster_properties(
        self, text: str | CodePointSequence
    ) -> str:
        if isinstance(text, str):
            text = CodePointSequence.from_string(text)
        return ''.join(self.grapheme_cluster_property(cp).value for cp in text)

    def grapheme_cluster_breaks(self, text: str | CodePointSequence) -> Iterator[int]:
        """
        Iterate over the grapheme cluster breaks for the given string or
        sequence of code points. The implementation has some startup cost
        because it first converts the entire string into a sequence of grapheme
        cluster property values. Thereafter, it uses a regular expression for
        iterating over the grapheme cluster breaks.
        """
        grapheme_cluster_props = self.grapheme_cluster_properties(text)
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

    def test_property(self, codepoint: CodePoint, property: BinaryProperty) -> bool:
        self.prepare()
        match property:
            case BinaryProperty.Dash:
                return codepoint in self._dashes
            case BinaryProperty.Default_Ignorable_Code_Point:
                return _is_in_range(codepoint, self._default_ignorable)
            case BinaryProperty.Noncharacter_Code_Point:
                return codepoint in self._noncharacters
            case BinaryProperty.Variation_Selector:
                return codepoint in self._variation_selectors
            case BinaryProperty.White_Space:
                return codepoint in self._whitespace
            case _:
                return _is_in_range(codepoint, self._emoji_data[property.name])

    def count_property_values(
        self,
        property: BinaryProperty | ComplexProperty,
    ) -> None | tuple[int, int]:
        """
        Count the number of code points that have a non-default property value.
        If the property is accessed by bisecting an ordered list of code point
        ranges, also count the number of distinct ranges. Otherwise, the second
        count is the same. `None` indicates that the property is not currently
        maintained.
        """
        self.prepare()

        def get_counts(
            ranges: Sequence[tuple[CodePointRange, *_Ts]]  # type: ignore[valid-type]
        ) -> tuple[int, int]:
            return sum(len(r[0]) for r in ranges), len(ranges)

        match property:
            case BinaryProperty.Dash:
                count = len(self._dashes)
                return count, count
            case BinaryProperty.Default_Ignorable_Code_Point:
                return (
                    sum(len(r) for r in self._default_ignorable),
                    len(self._default_ignorable),
                )
            case BinaryProperty.Noncharacter_Code_Point:
                count = len(self._noncharacters)
                return count, count
            case BinaryProperty.Variation_Selector:
                count = len(self._variation_selectors)
                return count, count
            case BinaryProperty.White_Space:
                count = len(self._whitespace)
                return count, count
            case BinaryProperty():
                return (
                    sum(len(r) for r in self._emoji_data[property.name]),
                    len(self._emoji_data[property.name]),
                )
            case ComplexProperty.Canonical_Combining_Class:
                return None
            case ComplexProperty.East_Asian_Width:
                return get_counts(self._width_ranges)
            case ComplexProperty.Emoji_Sequence:
                count = len(self._emoji_sequences)
                return count, count
            case ComplexProperty.General_Category:
                count = len(self._info_entries)
                return count, count
            case ComplexProperty.Grapheme_Cluster_Break:
                return get_counts(self._grapheme_props)
            case ComplexProperty.Indic_Syllabic_Category:
                return None
            case ComplexProperty.Script:
                return None

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
    ) -> None | tuple[str, None | Version]:
        """
        Retrieve the name and age of the emoji sequence, if the code points are
        such a sequence indeed. This method only works if the code points
        argument has been converted to the right types with `_to_codepoints()`.
        """
        result = self._emoji_sequences.get(codepoints)
        if result is not None or codepoints.is_singleton():
            return result
        codepoints = codepoints.to_sequence()  # Keep mypy happy
        if len(codepoints) != 2 or codepoints[1] != 0xFE0F:
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

    # ----------------------------------------------------------------------------------
    # Binary Unicode properties, implemented as sets for now

    @property
    def fullwidth_punctuation(self) -> Set[CodePoint]:
        """Fullwidth punctuation."""
        return _FULLWIDTH_PUNCTUATION

    @property
    def dashes(self) -> Set[CodePoint]:
        """All code points with Unicode's Dash property."""
        self.prepare()
        return self._dashes

    @property
    def with_keycap(self) -> Set[CodePoint]:
        """All code points that can be combined with U+20E3 as keycaps."""
        return _COMBINE_WITH_ENCLOSING_KEYCAPS

    @property
    def noncharacters(self) -> Set[CodePoint]:
        """All code points with Unicode's Noncharacter_Code_Point property."""
        self.prepare()
        return self._noncharacters

    @property
    def variation_selectors(self) -> Set[CodePoint]:
        """
        All code points with Unicode's Variation_Selector property. This
        property is very much different from `with_emoji_variation`. This
        property returns code points that trigger variations, whereas the other
        property returns code points that participate in variations.
        """
        self.prepare()
        return self._variation_selectors

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

    @property
    def whitespace(self) -> Set[CodePoint]:
        """All code points with Unicode's White_Space property."""
        self.prepare()
        return self._whitespace

    # ----------------------------------------------------------------------------------
    # Non-standard utilities

    def is_line_break(self, codepoint: CodePoint) -> bool:
        return codepoint in _LINE_BREAKS

    def width(self, codepoints: str | CodePointSequence | CodePoint) -> int:
        codepoints = self._to_codepoints(codepoints)

        # First, check for emoji
        if self._to_emoji_info(codepoints) is not None:
            return 2

        # Second, add up East Asian Width.
        total_width = 0
        for codepoint in codepoints.to_sequence():
            unidata = self.lookup(codepoint)
            width = unidata.wcwidth()
            if width == -1:
                return -1
            total_width += width
        return total_width


UCD = UnicodeCharacterDatabase(local_cache_directory())
