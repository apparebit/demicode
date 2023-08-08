from bisect import bisect_right as stdlib_bisect_right
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
import re
import shutil
from typing import Any, Callable, Literal, Tuple, TypeAlias, TypeVar, TypeVarTuple
from urllib.request import urlopen

from .codepoint import (
    CodePoint,
    CodePointRange,
    CodePointSequence,
    RangeLimit,
)

from .property import Category, EastAsianWidth

# --------------------------------------------------------------------------------------
# Curated Code Points


_KEYCAPS = frozenset(CodePoint.of(cp) for cp in '#*0123456789')
_CURATED_SELECTION = tuple(CodePoint.of(cp) for cp in (
    ' ',
    '\u2588',
    '\u200B',  # ZERO WIDTH SPACE
    '#',
    '‱',
    '℃',
    '∫',
    '∬',
    '∭',
    '⨌',
    '♀︎',
    '⚢',
    '♋︎',
    '\u27FF', # LONG RIGHTWARDS SQUIGGLE ARROW
    '\u23E9', # BLACK RIGHT-POINTING DOUBLE TRIANGLE 6.0
    '\u23ED', # BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR 6.0
    '-',      # HYPHEN-MINUS
    '\u2212', # MINUS SIGN
    '\u2013', # EN DASH
    '\u2014', # EM DASH
    '\u2E3A', # TWO EM DASH
    '\u2E3B', # THREE EM DASH
    '凌',
    '遲',
    '\U0001F0BF',  # PLAYING CARD RED JOKER, 7.0
    '｟',
    '\U0001F918',  # SIGN OF THE HORNS, 8.0
    '\U0001F9DB',  # VAMPIRE, 10.0
    '\U0001F991',  # SQUID, 9.0
    '｠',
    '©',
    '\U0001F12F',  # COPYLEFT SYMBOL, 11.0
    '\u2BFF',      # HELLSCHREIBER PAUSE SYMBOL, 12.0
    # (proposal http://www.unicode.org/L2/L2017/17151r-hell-pause-char.pdf)
    '\U0001FBF6',  # SEGMENTED DIGIT SIX, 13.0
    '\U0001F7F0',  # HEAVY EQUALS SIGN, 14.0
    '\U0001FAE8',  # SHAKING FACE, 15.0
))

_ARROWS = tuple(CodePoint.of(cp) for cp in (
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

_LINE_BREAKS = tuple(CodePoint.of(cp) for cp in (
    '\x0A', # LINE FEED
    '\x0B', # LINE TABULATION
    '\x0C', # FORM FEED
    '\x0D', # CARRIAGE RETURN
    '\x85', # NEXT LINE
    '\u2028', # LINE SEPARATOR (Zl)
    '\u2029', # PARAGRAPH SEPARATOR (Zp)
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


# --------------------------------------------------------------------------------------
# Local Mirroring of UCD Files


def _get_ucd_url(
    file: str,
    *,
    version: None | str = None
) -> str:
    """
    Get the URL for the given UCD file and version. If the version is `None`,
    this function extracts the concrete number from the latest version's
    `ReadMe.txt`.
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


_VERSION_PATTERN = re.compile('Version (?P<version>\d+[.]\d+[.]\d+)')

def _get_ucd_version() -> str:
    with urlopen(_get_ucd_url('ReadMe.txt')) as response:
        text = response.read().decode('utf8')
    rematch = _VERSION_PATTERN.search(text)
    if rematch is None:
        raise ValueError("UCD's ReadMe.txt elides version number")
    return rematch.group('version')


def _mirror_unicode_data(
    file: str,
    root: Path,
    *,
    version: None | str = None,
) -> Path:
    """Locally mirror a file from the Unicode Character Database."""

    effective_version = _get_ucd_version() if version is None else version
    version_root = root / effective_version
    version_root.mkdir(parents=True, exist_ok=True)

    path = version_root / file
    if not path.exists():
        url = _get_ucd_url(file, version=version)
        with urlopen(url) as response, open(path, mode='wb') as local_file:
            shutil.copyfileobj(response, local_file)

    return path


# --------------------------------------------------------------------------------------
# Parsing UCD Files


_T = TypeVar('_T')
_U = TypeVar('_U')
_Ts = TypeVarTuple('_Ts')
_Tag: TypeAlias = None | Literal['default']
_CodePoints: TypeAlias = CodePoint | CodePointRange | CodePointSequence
_Properties: TypeAlias = tuple[str, ...]


def _parse_record(line: str) -> tuple[_CodePoints, _Properties]:
    line, _, _ = line.partition('#')
    codepoints, *properties = [f.strip() for f in line.strip().split(';')]
    first_codepoint, *more_codepoints = codepoints.split()

    if len(more_codepoints) == 0:
        start, _, stop = first_codepoint.partition('..')
        if stop:
            return CodePointRange.of(start, stop), tuple(properties)
        else:
            return CodePoint.of(start), tuple(properties)

    sequence = CodePointSequence.of(first_codepoint, *more_codepoints)
    return sequence, tuple(properties)


_EOF = '# EOF'
_MISSING = '# @missing:'

def _parse_records(
    lines: Iterable[str]
) -> Iterator[tuple[_Tag, _CodePoints, _Properties]]:
    for line in lines:
        if line in ('', '\n'):
            continue
        elif line.startswith(_EOF):
            return
        elif line.startswith(_MISSING):
            yield  'default', *_parse_record(line[len(_MISSING):].strip())
        elif line[0] == '#':
            continue
        else:
            yield None, *_parse_record(line)


def _collect(
    property_records: Iterable[tuple[_Tag, _CodePoints, _Properties]],
    converter: Callable[[_CodePoints, _Properties], _T],
) -> tuple[list[_T], list[_T]]:
    defaults: list[_T] = []
    records: list[_T] = []

    for tag, codepoints, properties in property_records:
        if tag is None:
            records.append(converter(codepoints, properties))
        else:
            defaults.append(converter(codepoints, properties))

    return defaults, records


def _ingest(
    version: None | str,
    file: str,
    path: Path,
    converter: Callable[[_CodePoints, _Properties], _T],
) -> tuple[list[_T], list[_T]]:
    path = _mirror_unicode_data(file, path, version=version)
    with open(path, mode='r', encoding='utf8') as handle:
        return _collect(_parse_records(handle), converter)


# --------------------------------------------------------------------------------------
# Retrieval of Specific Data


def _retrieve_general_info(
    path: Path, version: None | str = None
) -> tuple[list[tuple[CodePointRange, str, str]], dict[CodePoint, tuple[str, str]]]:
    _, data = _ingest(
        version, 'UnicodeData.txt', path, lambda cp, p: (cp.first, p[0], p[1]))

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


def _retrieve_blocks(
    path: Path, version: None | str = None
) -> list[tuple[CodePointRange, str]]:
    _, data = _ingest(
        version, 'Blocks.txt', path, lambda cp, p: (cp.to_range(), p[0]))
    return data


def _retrieve_ages(
    path: Path, version: None | str = None
) -> list[tuple[CodePointRange, str]]:
    _, data = _ingest(
        version, 'DerivedAge.txt', path, lambda cp, p: (cp.to_range(), p[0]))
    return sorted(data, key=lambda d: d[0])


def _retrieve_widths(
    path: Path, version: None | str = None
) -> tuple[str, list[tuple[CodePointRange, str]]]:
    defaults, data = _ingest(
        version, 'EastAsianWidth.txt', path, lambda cp, p: (cp.to_range(), p[0]))
    if len(defaults) != 1:
        raise ValueError(f'"EastAsianWidth.txt" with {len(defaults)} instead of one')
    if defaults[0][0] != RangeLimit.ALL:
        raise ValueError(
            f'"EastAsianWidth.txt" with default that covers only {defaults[0][0]}')
    return defaults[0][1], data


def _retrieve_variations(path: Path, version: None | str = None) -> list[CodePoint]:
    _, data = _ingest(
        version, 'emoji-variation-sequences.txt', path, lambda cp, _: cp.first)
    return list(dict.fromkeys(data))


def _retrieve_misc_props(
    path: Path, version: None | str = None
) -> dict[str, set[CodePoint]]:
    _, data = _ingest(
        version, 'PropList.txt', path, lambda cp, p: (cp.to_range(), p[0]))

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
    range_data: Sequence[tuple[CodePointRange, *Tuple[Any, ...]]], # type: ignore
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


class UnicodeCharacterDatabase:
    """
    A convenient interface to interrogating the Unicode Character Database.

    By default, the data used this class is the latest released version of the
    UCD. Since file formats have hardly changed, this class can use older
    versions of the UCD just the same. In either case, it downloads the
    necessary files upon first use and thereafter utilizes the locally mirrored
    versions. Just like the Unicode website has distinct directories for each
    version, the local mirror uses version-specific directories.

    Currently, the UCD instance used by this package is a global singleton that
    is eagerly created. At the same time, the singleton does not load the
    necessary data until needed, making it possible to update path and version
    through the `use_path` and `use_version` methods.
    """

    VERSIONS = (
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
    )

    @classmethod
    def check_version(cls, version: None | str) -> None | str:
        if version is None:
            return None

        # Convert to tuple[int]
        try:
            vrs = tuple(int(v) for v in version.split('.'))
        except ValueError:
            raise ValueError(f'malformed UCD version "{version}"')

        # Normalize to three components
        if (count := len(vrs)) < 3:
            vrs += (0,) * (3 - count)
        elif count > 3:
            raise ValueError(f'malformed UCD version "{version}"')

        # If within range of known supported versions, validate version.
        first, next_major = cls.VERSIONS[0], cls.VERSIONS[-1][0]
        if vrs[:2] < first:
            raise ValueError(f'UCD version {version} before first supported 4.1')
        if vrs[0] < next_major and (vrs[-1] != 0 or vrs[:2] not in cls.VERSIONS):
            raise ValueError(f'nonexistent UCD version "{version}"')

        return '.'.join(str(v) for v in vrs)

    def __init__(self, path: Path, version: None | str = None) -> None:
        self._path = path
        self._version = version
        self._is_prepared: bool = False

    @property
    def path(self) -> Path:
        return self._path

    @property
    def version(self) -> str:
        return self._version

    def use_path(self, path: Path) -> None:
        if self._is_prepared:
            raise ValueError('trying to update UCD path after UCD has been ingested')
        if not path.exists():
            raise ValueError(f'UCD path "{path}" does not exist')
        if not path.is_dir():
            raise ValueError(f'UCD path "{path}" is not a directory')
        self._path = path

    def use_version(self, version: str) -> None:
        if self._is_prepared:
            raise ValueError('trying to update UCD version after UCD has been ingested')
        self._version = self.check_version(version)


    def prepare(self) -> None:
        if self._is_prepared:
            return
        path, version = self.path, self.version

        self._info_ranges, self._info_entries = _retrieve_general_info(path, version)
        self._block_ranges = _retrieve_blocks(path, version)
        self._age_ranges = _retrieve_ages(path, version)
        self._width_default, self._width_ranges = _retrieve_widths(path, version)
        self._variations = frozenset(_retrieve_variations(path, version))
        misc_props = _retrieve_misc_props(path, version)
        self._whitespace = frozenset(misc_props['White_Space'])
        self._dash = frozenset(misc_props['Dash'])
        self._noncharacter = frozenset(misc_props['Noncharacter_Code_Point'])
        self._selector = frozenset(misc_props['Variation_Selector'])
        self._is_prepared = True

    @property
    def curated_selection(self) -> tuple[CodePoint,...]:
        """
        Some code points to show off the current abysmal fixed-width state.
        Obviously, this is not a Unicode standard property.
        """
        return _CURATED_SELECTION

    @property
    def with_arrow(self) -> tuple[CodePoint,...]:
        """Matching short and long arrows."""
        return _ARROWS

    @property
    def with_dash(self) -> Set[CodePoint]:
        """All code points with Unicode's Dash property."""
        self.prepare()
        return self._dash

    @property
    def with_keycap(self) -> Set[CodePoint]:
        """All code points that can be modified with U+20E3 as keycaps."""
        return _KEYCAPS

    @property
    def with_noncharacter(self) -> Set[CodePoint]:
        """All code points with Unicode's Noncharacter_Code_Point property."""
        self.prepare()
        return self._noncharacter

    @property
    def with_selector(self) -> Set[CodePoint]:
        """
        All code points with Unicode's Variation_Selector property. This
        property is very much different from `with_variation`. This property
        returns code points that trigger variations, whereas the other property
        returns code points that participate in variations.
        """
        self.prepare()
        return self._selector

    @property
    def with_variation(self) -> Set[CodePoint]:
        """
        All code points that participate with text and emoji variations, i.e.,
        can be displayed as more conventional black and white glyphs as well as
        colorful squarish emoji. This property is very much different from
        `with_selector`, which produces the code points triggering variations.
        """
        self.prepare()
        return self._variations

    @property
    def with_whitespace(self) -> Set[CodePoint]:
        """All code points with Unicode's White_Space property."""
        self.prepare()
        return self._whitespace

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
        ranges: Sequence[tuple[CodePointRange, *_Ts]],  # type: ignore
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
