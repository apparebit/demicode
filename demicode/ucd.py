from bisect import bisect_right as stdlib_bisect_right
from collections import defaultdict
from collections.abc import Sequence, Set
import logging
from pathlib import Path
import re
import shutil
import time
from typing import Any, NamedTuple, Self, TypeVar, TypeVarTuple
from urllib.request import Request, urlopen

from .codepoint import (
    CodePoint,
    CodePointRange,
    RangeLimit,
)

from .parser import ingest
from .property import Category, EastAsianWidth, BinaryProperty, CharacterData
from demicode import __version__


logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------------------
# More or less based on Unicode standard

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
# UCD Versions


KNOWN_VERSIONS = tuple(v + (0,) for v in (
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


class Version(NamedTuple):
    """
    A UCD Version. The Unicode Character Database includes version strings with
    two and three components. Hence this class models three components.
    """

    major: int
    minor: int
    patch: int

    @classmethod
    def of(cls, text: str) -> 'Version':
        """
        Parse the string as a UCD version number. This method pads versions with
        too few components by adding 0 components. For versions that fall into
        the range of known and supported UCD versions, 4.1 - 15.1, it also
        validates that the version actually exists. It rejects earlier versions
        and it allows later versions to ensure that code won't stop working in
        the future.
        """
        # Parse components
        try:
            components = tuple(int(c) for c in text.split('.'))
        except:
            raise ValueError(f'malformed components in version "{text}"')

        # Normalize to three components
        count = len(components)
        if count < 3:
            components += (0,) * (3 - count)
        elif count > 3:
            raise ValueError(f'too many components in version "{text}"')

        # Validate existing versions while allowing future versions
        if components < KNOWN_VERSIONS[0]:
            raise ValueError(f'unsupported version "{text}"')
        if components < KNOWN_VERSIONS[-1] and components[-1] != 0:
            raise ValueError(f'invalid patch number in version "{text}"')
        if components < KNOWN_VERSIONS[-1] and components not in KNOWN_VERSIONS:
            raise ValueError(f'non-existent version "{text}"')

        return cls(*components)

    @property
    def short(self) -> str:
        return f'{self.major}.{self.minor}'

    def __str__(self) -> str:
        return '.'.join(str(c) for c in self)


# --------------------------------------------------------------------------------------
# Local Mirroring of UCD Files

_NORMATIVE_EMOJI = ('emoji-data.txt', 'emoji-variation-sequences.txt')
_AUXILIARY_EMOJI = ('emoji-sequences.txt', 'emoji-test.txt', 'emoji-zwj-sequences.txt')

def _get_ucd_url(file: str, version: None | Version = None) -> str:
    """
    Get the URL for the given UCD file and version. If the version is `None`,
    this function uses the latest version thanks to the UCD's "latest" alias.
    """
    if (
        (file in _NORMATIVE_EMOJI and version is not None and version < (13, 0, 0))
        or file in _AUXILIARY_EMOJI
    ):
        path = f'emoji/{"latest" if version is None else version.short}/{file}'

    else:
        prefix = "UCD/latest/" if version is None else f'{str(version)}/ucd/'
        path = prefix + (f'emoji/{file}' if file in _NORMATIVE_EMOJI else file)

    return f'https://www.unicode.org/Public/{path}'


def _build_ucd_request(url: str) -> Request:
    return Request(url, None, {'User-Agent': f'demicode {__version__}'})


_ONE_WEEK = 7 * 24 * 60 * 60
_VERSION_PATTERN = (
    re.compile('Version (?P<version>\d+[.]\d+[.]\d+) of the Unicode Standard')
)

def retrieve_latest_ucd_version(root: Path) -> Version:
    """
    Determine the latest UCD version. To avoid network accesses for every
    invocation of demicode, this method uses the `latest-version.txt` file in
    the local mirror directory as a cache and only checks the Unicode
    Consortium's servers once a week.
    """
    stamp_path = root / 'latest-version.txt'
    if stamp_path.is_file() and stamp_path.stat().st_mtime + _ONE_WEEK > time.time():
        try:
            return Version.of(stamp_path.read_text('utf8'))
        except ValueError:
            pass

    url = _get_ucd_url('ReadMe.txt')
    logger.info('Retrieving latest UCD version from "%s"', url)
    with urlopen(_build_ucd_request(url)) as response:
        text = response.read().decode('utf8')
    rematch = _VERSION_PATTERN.search(text)
    if rematch is None:
        raise ValueError("""UCD's "ReadMe.txt" elides version number""")
    version = Version.of(rematch.group('version'))

    root.mkdir(parents=True, exist_ok=True)
    stamp_path.write_text(str(version), encoding='utf8')
    return version


def mirror_unicode_data(root: Path, filename: str, version: Version) -> Path:
    """Locally mirror a file from the Unicode Character Database."""
    version_root = root / str(version)
    path = version_root / filename
    if not path.exists():
        version_root.mkdir(parents=True, exist_ok=True)

        url = _get_ucd_url(filename, version=version)
        logger.info('Mirroring UCD file "%s" to "%s"', url, path)
        with (
            urlopen(_build_ucd_request(url)) as response,
            open(path, mode='wb') as file
        ):
            shutil.copyfileobj(response, file)
    return path


# --------------------------------------------------------------------------------------
# Retrieval of Specific Data


def _retrieve_general_info(
    path: Path, version: Version
) -> tuple[list[tuple[CodePointRange, str, str]], dict[CodePoint, tuple[str, str]]]:
    path = mirror_unicode_data(path, 'UnicodeData.txt', version)
    _, data = ingest(path, lambda cp, p: (cp.first, p[0], p[1]))

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
            info_entries[codepoint] = name, category
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
        info_ranges.append((CodePointRange.of(codepoint, codepoint2), stem, category))

    return info_ranges, info_entries


def _retrieve_blocks(path: Path, version: Version) -> list[tuple[CodePointRange, str]]:
    path = mirror_unicode_data(path, 'Blocks.txt', version)
    _, data = ingest(path, lambda cp, p: (cp.to_range(), p[0]))
    return data


def _retrieve_ages(path: Path, version: Version) -> list[tuple[CodePointRange, str]]:
    path = mirror_unicode_data(path, 'DerivedAge.txt', version)
    _, data = ingest(path, lambda cp, p: (cp.to_range(), p[0]))
    return sorted(data, key=lambda d: d[0])


def _retrieve_widths(
    path: Path, version: Version
) -> tuple[str, list[tuple[CodePointRange, str]]]:
    path = mirror_unicode_data(path, 'EastAsianWidth.txt', version)
    defaults, data = ingest(path, lambda cp, p: (cp.to_range(), p[0]))
    if len(defaults) != 1:
        raise ValueError(f'"EastAsianWidth.txt" with {len(defaults)} instead of one')
    if defaults[0][0] != RangeLimit.ALL:
        raise ValueError(
            f'"EastAsianWidth.txt" with default that covers only {defaults[0][0]}')
    return defaults[0][1], data


def _retrieve_emoji_data(
    path: Path, version: Version
) -> dict[str, list[CodePointRange]]:
    path = mirror_unicode_data(path, 'emoji-data.txt', version)
    _, raw_data = ingest(path, lambda cp, p: (cp.to_range(), p[0]))

    data = defaultdict(list)
    for range, label in raw_data:
        data[label].append(range)

    return data


def _retrieve_emoji_variations(path: Path, version: Version) -> list[CodePoint]:
    path = mirror_unicode_data(path, 'emoji-variation-sequences.txt', version)
    _, data = ingest(path, lambda cp, _: cp.first)
    return list(dict.fromkeys(data)) # Remove all duplicates


def _retrieve_misc_props(path: Path, version: Version) -> dict[str, set[CodePoint]]:
    path = mirror_unicode_data(path, 'PropList.txt', version)
    _, data = ingest(path, lambda cp, p: (cp.to_range(), p[0]))

    # It might be a good idea to actually measure performance and memory impact
    # of bisecting ranges versus hashing code points. Until such times, however,
    # I prefer the set-based interface.

    misc_props: dict[str, set[CodePoint]] = {
        'White_Space': set(),
        'Dash': set(),
        'Noncharacter_Code_Point': set(),
        'Variation_Selector': set(),
    }

    for datum in data:
        if datum[1] in misc_props:
            codepoints = misc_props[datum[1]]
            for cp in datum[0].codepoints():
                codepoints.add(cp)

    return misc_props


# --------------------------------------------------------------------------------------
# Look Up


def _bisect_ranges(
    range_data: Sequence[tuple[CodePointRange, *tuple[Any, ...]]], # type: ignore
    codepoint: CodePoint,
) -> int:
    idx = stdlib_bisect_right(range_data, codepoint, key=lambda rd: rd[0].stop)
    if idx > 0 and range_data[idx - 1][0].stop == codepoint:
        idx -= 1

    # Validate result
    if __debug__:
        range = range_data[idx][0]
        if codepoint not in range:
            assert codepoint < range.start, f'{codepoint} should come before {range}'
            if idx > 0:
                range = range_data[idx-1][0]
                assert range.stop < codepoint, f'{codepoint} should come after {range}'

    return idx


# --------------------------------------------------------------------------------------
# The UCD


_T = TypeVar('_T')
_Ts = TypeVarTuple('_Ts')
_U = TypeVar('_U')

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

    @property
    def path(self) -> Path:
        return self._path

    @property
    def version(self) -> None | Version:
        return self._version

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
        self._version = Version.of(version)

    def prepare(self) -> Self:
        """
        Prepare the UCD for active use. This method locks in the current
        configuration and locally mirrors any required UCD files. Repeated
        invocations have no effect.
        """
        if self._is_prepared:
            return self
        path, version = self._path, self._version
        if version is None:
            self._version = version = retrieve_latest_ucd_version(self._path)
        logger.info('Using UCD version %s', version)

        self._info_ranges, self._info_entries = _retrieve_general_info(path, version)
        self._block_ranges = _retrieve_blocks(path, version)
        self._age_ranges = _retrieve_ages(path, version)
        self._width_default, self._width_ranges = _retrieve_widths(path, version)
        self._emoji_data = _retrieve_emoji_data(path, version)
        self._emoji_variations = frozenset(_retrieve_emoji_variations(path, version))
        misc_props = _retrieve_misc_props(path, version)
        self._whitespace = frozenset(misc_props[BinaryProperty.White_Space.name])
        self._dashes = frozenset(misc_props[BinaryProperty.Dash.name])
        self._noncharacters = frozenset(
            misc_props[BinaryProperty.Noncharacter_Code_Point.name])
        self._variation_selectors = frozenset(
            misc_props[BinaryProperty.Variation_Selector.name])
        self._is_prepared = True

        return self

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

    def _resolve_info(self, codepoint: CodePoint, offset: int) -> None | str:
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

    def category(self, codepoint: CodePoint) -> Category:
        """Look up the code point's category"""
        category = self._resolve_info(codepoint, 1)
        return Category.Unassigned if category is None else Category(category)

    def _resolve(
        self,
        codepoint: CodePoint,
        ranges: Sequence[tuple[CodePointRange, *_Ts]], # type: ignore[valid-type]
        default: _U,
    ) -> _T | _U:
        self.prepare()
        record = ranges[_bisect_ranges(ranges, codepoint)]
        return record[1] if codepoint in record[0] else default

    def block(self, codepoint: CodePoint) -> None | str:
        """Look up the code point's block."""
        return self._resolve(codepoint, self._block_ranges, None)

    def age(self, codepoint: CodePoint) -> None | str:
        """Look up the code point's age, i.e., version when it was assigned."""
        return self._resolve(codepoint, self._age_ranges, None)

    def east_asian_width(self, codepoint: CodePoint) -> EastAsianWidth:
        """Look up the code point's East Asian width."""
        w = self._resolve(codepoint, self._width_ranges, self._width_default)
        return EastAsianWidth(w)

    def test_property(self, codepoint: CodePoint, property: BinaryProperty) -> bool:
        self.prepare()
        match property:
            case BinaryProperty.Dash:
                return codepoint in self._dashes
            case BinaryProperty.Noncharacter_Code_Point:
                return codepoint in self._noncharacters
            case BinaryProperty.Variation_Selector:
                return codepoint in self._variation_selectors
            case BinaryProperty.White_Space:
                return codepoint in self._whitespace
            case _:
                ranges = self._emoji_data[property.name]
                idx = stdlib_bisect_right(ranges, codepoint, key=lambda r: r.stop)
                if idx > 0 and ranges[idx - 1].stop == codepoint:
                    idx -= 1
                return 0 <= idx < len(ranges) and codepoint in ranges[idx]

    def count_property(self, property: BinaryProperty) -> int:
        self.prepare()
        match property:
            case BinaryProperty.Dash:
                return len(self._dashes)
            case BinaryProperty.Noncharacter_Code_Point:
                return len(self._noncharacters)
            case BinaryProperty.Variation_Selector:
                return len(self._variation_selectors)
            case BinaryProperty.White_Space:
                return len(self._whitespace)
            case _:
                return sum(len(r) for r in self._emoji_data[property.name])

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


UCD = UnicodeCharacterDatabase(Path.cwd() / 'ucd')
