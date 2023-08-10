from bisect import bisect_right as stdlib_bisect_right
from collections.abc import Sequence, Set
from pathlib import Path
import re
import shutil
import time
from typing import Any, Self, TypeVar, TypeVarTuple
from urllib.request import Request, urlopen

from .codepoint import (
    CodePoint,
    CodePointRange,
    RangeLimit,
)

from .parser import ingest
from .property import Category, EastAsianWidth
from demicode import __version__

# --------------------------------------------------------------------------------------
# Curated Code Points


def prep(text: str) -> str | CodePoint:
    return text if text[0] == '\u0001' else CodePoint.of(text)

_MAD_DASH = tuple(prep(text) for text in (
    '\u0001A Mad Dash',
    '-',           # HYPHEN-MINUS
    '\u2212',      # MINUS SIGN
    '\u2013',      # EN DASH
    '\u2014',      # EM DASH
    '\uFF0D',      # FULLWIDTH HYPHEN-MINUS
    '\u2E3A',      # TWO EM DASH
    '\u2E3B',      # THREE EM DASH
))

_LINGCHI = tuple(prep(text) for text in (
    '\u0001Death by a Thousand Cuts',
    '\u200B',      # ZERO WIDTH SPACE
    ' ',           # SPACE
    '\u2588',      # FULL BLOCK
    '‱',
    '℃',
    '∫',
    '∬',
    '∭',
    '⨌',
    '\u21A6',      # rightwards arrow from bar
    '\u27FC',      # long rightwards arrow from bar
    '♀︎',
    '⚢',
    '♋︎',
    '凌',          # https://en.wikipedia.org/wiki/Lingchi
    '遲',
    '!',
    '\uFF01',      # FULLWIDTH EXCLAMATION MARK
    '\u2755',      # WHITE EXCLAMATION MARK ORNAMENT
    '\u2757',      # HEAVY EXCLAMATION MARK SYMBOL
    '\u2763',      # HEART HEART EXCLAMATION MARK ORNAMENT
    '#',           # NUMBER SIGN (Emoji 2.0, not part of Unicode update)
))

_VERSION_ORACLE = tuple(prep(text) for text in (
    '\u0001Emoji Version Oracle', # Comprising Emoji with Wide as East Asian Width
    # Nothing for 3.0 nor for 3.1
    '\u303D',      # PART ALTERNATION MARK, 3.2
    '\u26A1',      # HIGH VOLTAGE, 4.0
    '\u2693',      # ANCHOR, 4.1
    # Nothing for 5.0
    '\u2B50',      # STAR, 5.1
    '\u26D4',      # NO ENTRY, 5.2
    '\u23E9',      # BLACK RIGHT-POINTING DOUBLE TRIANGLE 6.0
    '\u23ED',      # BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR 6.0
    '\U0001F62C',  # GRIMACING FACE, 6.1
    '\U0001F596',  # VULCAN SALUTE, 7.0
    '\U0001F3DD',  # DESERT ISLAND, 7.0
    '\U0001F918',  # SIGN OF THE HORNS, 8.0 (Emoji 1.0, covering Unicode 1.1--8.0)
    # Emoji 2.0?
    '\U0001F991',  # SQUID, 9.0 (Emoji 3.0)
    # Emoji 4.0 added new ZWJ sequences only
    '\U0001F9DB',  # VAMPIRE, 10.0 (Emoji 5.0)
    # There are no Emoji 6--10. Versions align with Unicode thereafter
    '\U0001F973',  # PARTYING FACE, 11.0
    '\U0001F9A9',  # FLAMINGO, 12.0
    # 12.1 added new ZWJ sequences only and wasn't part of Unicode update
    '\U0001FA86',  # NESTING DOLLS, 13.0
    # 13.1 added new ZWJ sequences only and wasn't part of Unicode update
    '\U0001FAA9',  # MIRROR BALL, 14.0
    '\U0001FAE8',  # SHAKING FACE, 15.0
))

_ARROWS = tuple(prep(text) for text in (
    '\u0001An Arrow’s Flight',
    '\u2190', # leftwards arrow
    '\u27F5', # long leftwards arrow
    '\u2192', # rightwards arrow
    '\u27F6', # long rightwards arrow
    '\u2194', # left right arrow
    '\u27F7', # long left right arrow
    '\u21D0', # leftwards double arrow
    '\u27F8', # long leftwards double arrow
    '\u21D2', # rightwards double arrow
    '\u27F9', # long rightwards double arrow
    '\u21D4', # left right double arrow
    '\u27FA', # long left right double arrow
    '\u21A4', # leftwards arrow from bar
    '\u27FB', # long leftwards arrow from bar
    '\u21A6', # rightwards arrow from bar
    '\u27FC', # long rightwards arrow from bar
    '\u2906', # leftwards double arrow from bar
    '\u27FD', # long leftwards double arrow from bar
    '\u2907', # rightwards double arrow from bar
    '\u27FE', # long rightwards double arrow from bar
    '\u21DC', # leftwards squiggle arrow
    '\u2B33', # long leftwards squiggle arrow
    '\u21DD', # rightwards squiggle arrow
    '\u27FF', # long rightwards squiggle arrow
))

_EXTRA_TEST_POINTS = tuple(CodePoint.of(cp) for cp in (
    '\u0BF5', # TAMIL YEAR SIGN
    '\u0BF8', # TAMIL AS ABOVE SIGN
    ' ',
    '\u102A', # MYANMAR LETTER AU
    ' ',
    '\uA9C5', # JAVANESE PADA LUHUR
    ' ',
    '\uFDFD', # ARABIC LIGATURE BISMILLAH AR-RAHMAN AR-RAHEEM
    ' ',
    '\uFF23', # FULLWIDTH LATIN CAPITAL LETTER C
    '🟆',
    ' ',
    '\U00012219', # CUNEIFORM SIGN LUGAL OPPOSING LUGAL
    ' ',
    '\U0001242B', # CUNEIFORM NUMERIC SIGN NINE SHAR2
    ' ',
    '\U000130B8', # EGYPTIAN HIEROGLYPH D052
))


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


KNOWN_VERSIONS = (
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
)


def check_version(version: str) -> str:
    """
    Validate the given UCD version. UCD version numbers comprise a major, minor,
    and patch component. As of version 15.0.0, the latter is always zero. This
    function checks that the given version number adheres to that format. Though
    it also accepts version numbers with fewer components and automatically pads
    them with zero components. For version numbers smaller or equal to the
    latest known actual UCD version (15.1.0), this function also checks whether
    a version has actually been released, e.g., accepting 6.0, 6.1, 6.2, and
    6.3, but rejecting 6.4. To ensure that this module won't stop working for
    future releases, it always accepts well-formed larger version numbers.
    """

    # Convert to tuple[int]
    try:
        vrs = tuple(int(v) for v in version.split('.'))
    except ValueError:
        raise ValueError(f'malformed components in UCD version "{version}"')

    # Normalize to three components
    if (count := len(vrs)) < 3:
        vrs += (0,) * (3 - count)
    elif count > 3:
        raise ValueError(f'too many components in UCD version "{version}"')

    # If within range of known supported versions, validate version.
    v2, earliest, latest = vrs[:2], KNOWN_VERSIONS[0], KNOWN_VERSIONS[-1]
    if v2 < earliest:
        raise ValueError(f'UCD version "{version}" before first supported 4.1.0')
    if v2 < latest and vrs[-1] != 0:
        raise ValueError(f'invalid patch component in UCD version "{version}"')
    if v2 <= latest and v2 not in KNOWN_VERSIONS:
        raise ValueError(f'non-existent UCD version "{version}"')

    return '.'.join(str(v) for v in vrs)


# --------------------------------------------------------------------------------------
# Local Mirroring of UCD Files


def _get_ucd_url(file: str, version: None | str = None) -> str:
    """
    Get the URL for the given UCD file and version. If the version is `None`,
    this function uses the latest version thanks to the UCD's "latest" alias.
    """
    prefix = 'UCD/latest' if version is None else version
    match file:
        case 'ReadMe.txt':
            path = f'/{file}'
        case 'emoji-data.txt' | 'emoji-variation-sequences.txt':
            path = f'ucd/emoji/{file}'
        case _:
            path = f'ucd/{file}'

    return f'https://www.unicode.org/Public/{prefix}/{path}'


def _build_ucd_request(url: str) -> Request:
    return Request(url, None, {'User-Agent': f'demicode {__version__}'})


_ONE_WEEK = 7 * 24 * 60 * 60
_VERSION_PATTERN = re.compile('Version (?P<version>\d+[.]\d+[.]\d+)')

def retrieve_latest_ucd_version(root: Path) -> str:
    """
    Determine the latest UCD version. To avoid network accesses for every
    invocation of demicode, this method uses the `latest-version.txt` file in
    the local mirror directory as a cache and only checks the Unicode
    Consortium's servers once a week.
    """
    stamp_path = root / 'latest-version.txt'
    if stamp_path.is_file() and stamp_path.stat().st_mtime + _ONE_WEEK > time.time():
        try:
            return check_version(stamp_path.read_text('utf8'))
        except ValueError:
            pass

    url = _get_ucd_url('ReadMe.txt')
    with urlopen(_build_ucd_request(url)) as response:
        text = response.read().decode('utf8')
    rematch = _VERSION_PATTERN.search(text)
    if rematch is None:
        raise ValueError("""UCD's "ReadMe.txt" elides version number""")
    version = rematch.group('version')

    root.mkdir(parents=True, exist_ok=True)
    stamp_path.write_text(version, encoding='utf8')
    return version


def mirror_unicode_data(root: Path, filename: str, version: str) -> Path:
    """Locally mirror a file from the Unicode Character Database."""
    version_root = root / version
    path = version_root / filename
    if not path.exists():
        version_root.mkdir(parents=True, exist_ok=True)

        url = _get_ucd_url(filename, version=version)
        with (
            urlopen(_build_ucd_request(url)) as response,
            open(path, mode='wb') as file
        ):
            shutil.copyfileobj(response, file)
    return path


# --------------------------------------------------------------------------------------
# Retrieval of Specific Data


def _retrieve_general_info(
    path: Path, version: str
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


def _retrieve_blocks(path: Path, version: str) -> list[tuple[CodePointRange, str]]:
    path = mirror_unicode_data(path, 'Blocks.txt', version)
    _, data = ingest(path, lambda cp, p: (cp.to_range(), p[0]))
    return data


def _retrieve_ages(path: Path, version: str) -> list[tuple[CodePointRange, str]]:
    path = mirror_unicode_data(path, 'DerivedAge.txt', version)
    _, data = ingest(path, lambda cp, p: (cp.to_range(), p[0]))
    return sorted(data, key=lambda d: d[0])


def _retrieve_widths(
    path: Path, version: str
) -> tuple[str, list[tuple[CodePointRange, str]]]:
    path = mirror_unicode_data(path, 'EastAsianWidth.txt', version)
    defaults, data = ingest(path, lambda cp, p: (cp.to_range(), p[0]))
    if len(defaults) != 1:
        raise ValueError(f'"EastAsianWidth.txt" with {len(defaults)} instead of one')
    if defaults[0][0] != RangeLimit.ALL:
        raise ValueError(
            f'"EastAsianWidth.txt" with default that covers only {defaults[0][0]}')
    return defaults[0][1], data


def _retrieve_emoji_variations(path: Path, version: str) -> list[CodePoint]:
    # emoji-variation-sequences.txt became available with Unicode 13.0.0 only
    if version is not None and tuple(int(v) for v in version.split('.')) < (13,):
        return []

    path = mirror_unicode_data(path, 'emoji-variation-sequences.txt', version)
    _, data = ingest(path, lambda cp, _: cp.first)
    return list(dict.fromkeys(data)) # Remove all duplicates


def _retrieve_misc_props(path: Path, version: str) -> dict[str, set[CodePoint]]:
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

    This module defines an eagerly created global instance, `UCD`. As long as
    code doesn't perform any look-ups, `UCD` can still be configured with the
    `use_path()` and `use_version()` methods. The configuration is locked in
    with `prepare()`, which downloads necessary UCD files. While client code may
    explicitly invoke the method, that is not required.
    `UnicodeCharacterDatabase` automatically invokes the method as needed.
    """

    def __init__(self, path: Path, version: None | str = None) -> None:
        if version is not None:
            version = check_version(version)
        self._path = path
        self._version = version
        self._is_prepared: bool = False

    @property
    def path(self) -> Path:
        return self._path

    @property
    def version(self) -> None | str:
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
        self._version = check_version(version)

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

        self._info_ranges, self._info_entries = _retrieve_general_info(path, version)
        self._block_ranges = _retrieve_blocks(path, version)
        self._age_ranges = _retrieve_ages(path, version)
        self._width_default, self._width_ranges = _retrieve_widths(path, version)
        self._emoji_variations = frozenset(_retrieve_emoji_variations(path, version))
        misc_props = _retrieve_misc_props(path, version)
        self._whitespace = frozenset(misc_props['White_Space'])
        self._dashes = frozenset(misc_props['Dash'])
        self._noncharacters = frozenset(misc_props['Noncharacter_Code_Point'])
        self._selectors = frozenset(misc_props['Variation_Selector'])
        self._is_prepared = True

        return self

    # ----------------------------------------------------------------------------------
    # Sequences, ready for display

    @property
    def arrows(self) -> tuple[CodePoint | str,...]:
        """Matching short and long arrows."""
        return _ARROWS

    @property
    def mad_dash(self) -> tuple[CodePoint | str,...]:
        return _MAD_DASH

    @property
    def lingchi(self) -> tuple[CodePoint | str,...]:
        return _LINGCHI

    @property
    def version_oracle(self) -> tuple[CodePoint | str,...]:
        return _VERSION_ORACLE

    # ----------------------------------------------------------------------------------
    # Sets, ready for membership testing.

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
    def selectors(self) -> Set[CodePoint]:
        """
        All code points with Unicode's Variation_Selector property. This
        property is very much different from `with_emoji_variation`. This
        property returns code points that trigger variations, whereas the other
        property returns code points that participate in variations.
        """
        self.prepare()
        return self._selectors

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

    def category(self, codepoint: CodePoint) -> None | Category:
        """Look up the code point's category"""
        category = self._resolve_info(codepoint, 1)
        return None if category is None else Category(category)

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

    # ----------------------------------------------------------------------------------
    # Non-standard fixed width per https://www.cl.cam.ac.uk/~mgk25/ucs/wcwidth.c
    # and https://github.com/jquast/wcwidth

    def is_zero_width(self, codepoint: CodePoint) -> bool:
        """Determine whether the code point has zero width."""
        return (
            self.category(codepoint) in (
                Category.Enclosing_Mark,
                Category.Nonspacing_Mark,
                Category.Format
            ) and codepoint != 0x00AD
            or 0x1160 <= codepoint <= 0x11FF
            or codepoint == 0x200B
        )

    def fixed_width(self, codepoint: CodePoint) -> int:
        """Determine the fixed-width of the code point."""
        # https://www.cl.cam.ac.uk/~mgk25/ucs/wcwidth.c
        # https://github.com/jquast/wcwidth
        if codepoint == 0 or self.is_zero_width(codepoint):
            return 0
        if codepoint < 32 or 0x7F <= codepoint < 0xA0:
            return -1
        if self.east_asian_width(codepoint).is_wide:
            return 2

        return 1

    # ----------------------------------------------------------------------------------
    # Non-standard utilities

    def is_line_break(self, codepoint: CodePoint) -> bool:
        return codepoint in _LINE_BREAKS


UCD = UnicodeCharacterDatabase(Path.cwd() / 'ucd')
