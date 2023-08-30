from bisect import bisect_right as stdlib_bisect_right
from collections import defaultdict
from collections.abc import Sequence, Set
import itertools
import json
import logging
from pathlib import Path
import re
import shutil
import tarfile as tar
import time
from typing import (
    Any,
    cast,
    IO,
    Literal,
    NamedTuple,
    overload,
    Self,
    TypeVar,
    TypeVarTuple,
)
from urllib.request import Request, urlopen

from .codepoint import (
    CodePoint,
    CodePointRange,
    CodePointSequence,
    RangeLimit,
)

from .parser import ingest
from .property import (
    Category,
    EastAsianWidth,
    BinaryProperty,
    CharacterData,
    GraphemeClusterBreak,
    EmojiSequence,
)
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
# Versions


class VersionError(Exception):
    pass


KNOWN_UCD_VERSIONS = tuple(v + (0,) for v in (
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

KNOWN_EMOJI_VERSIONS = tuple(v + (0,) for v in (
    (0, 0),
    (0, 6),
    (0, 7),
    (1, 0),
    (2, 0),
    (3, 0),
    (4, 0),
    (5, 0),
    (11, 0),
    (12, 0),
    (12, 1),
    (13, 0),
    (13, 1),
    (14, 0),
    (15, 0),
))


class Version(NamedTuple):
    """A version number."""

    major: int
    minor: int
    patch: int

    @classmethod
    def of(cls, text: str) -> 'Version':
        """
        Parse the string as a version number with at most three components. If
        the string has fewer components, pad the missing components with zero.
        """
        try:
            components = tuple(int(c) for c in text.split('.'))
        except:
            raise ValueError(f'malformed components in version "{text}"')

        count = len(components)
        if count < 3:
            components += (0,) * (3 - count)
        elif count > 3:
            raise ValueError(f'too many components in version "{text}"')

        return cls(*components)

    @property
    def short(self) -> str:
        return f'{self.major}.{self.minor}'

    @property
    def is_ucd(self) -> bool:
        """
        Test whether the version is a valid UCD version. This method only
        rejects versions that cannot possibly be valid because they don't
        identify an existing version but are smaller than the latest known
        version. For now, it also rejects versions before 4.1.0, since file
        mirroring does not yet support the necessary name wrangling.
        """
        if self <= KNOWN_UCD_VERSIONS[-1] and self not in KNOWN_UCD_VERSIONS:
            return False
        return True

    def ucd(self) -> 'Version':
        """Validate this version as a UCD version."""
        if self.is_ucd:
            return self
        raise ValueError(f'version {self} is not a valid UCD version')

    @property
    def is_emoji(self) -> bool:
        """
        Test whether the version is a valid emoji version. This method rejects
        only versions that cannot possibly be valid because they don't identify
        an existing version but are smaller than the latest known version.

        Even though this method accepts 0.0, 0.6, and 0.7, those versions are
        informal versions only, without corresponding normative files. You can
        use `is_v0()` to test for those versions, since there are no other valid
        emoji versions with zero as major version.
        """
        if self <= KNOWN_EMOJI_VERSIONS[-1] and self not in KNOWN_EMOJI_VERSIONS:
            return False
        return True

    @property
    def is_v0(self) -> bool:
        """Test whether the major version component is zero."""
        return self.major == 0

    def to_emoji(self) -> 'Version':
        """
        Convert this UCD version to the smallest corresponding Emoji version.
        This method returns 0.0, 0.6, and 0.7, even though those versions have
        no normative files.
        """
        if self.major < 6:
            return Version(0, 0, 0)
        if self.major == 6:
            return Version(0, 6, 0)
        if self.major == 7:
            return Version(0, 7, 0)
        if 8 <= self.major <= 10:
            return Version(1 + 2 * (self.major - 8), 0, 0)
        if self.major == 13:
            return Version(13, 0, 0)
        return self

    def __str__(self) -> str:
        return '.'.join(str(c) for c in self)


# --------------------------------------------------------------------------------------
# Local Mirroring of UCD Files

_AUXILIARY_DATA = ('GraphemeBreakProperty.txt',)
_EMOJI_CORE_DATA = ('emoji-data.txt', 'emoji-variation-sequences.txt')
_EMOJI_SEQUENCE_DATA = (
    'emoji-sequences.txt', 'emoji-test.txt', 'emoji-zwj-sequences.txt'
)

def _get_ucd_url(file: str, version: None | Version = None) -> str:
    """
    Get the URL for the given UCD file and version. If the version is `None`,
    this function uses the latest version thanks to the UCD's "latest" alias. If
    file is one of the emoji data files and the version is 10.0.0 or earlier,
    this function tries to map the version to the earliest available Emoji
    version. Alas, that works only for 10.0.0, 9.0.0, and 8.0.0, which map to
    5.0, 3.0, and 1.0, respectively. More complete support for early Emoji
    versions would require exposing the emoji version throughout the UCD code.
    """
    if file not in _EMOJI_CORE_DATA and file not in _EMOJI_SEQUENCE_DATA:
        aux = 'auxiliary/' if file in _AUXILIARY_DATA else ''
        if version is None:
            path = f'UCD/latest/{aux}{file}'
        else:
            path = f'{str(version)}/ucd/{aux}{file}'

    elif file in _EMOJI_CORE_DATA and (version is None or version >= (13, 0 ,0)):
        if version is None:
            path = f'UCD/latest/emoji/{file}'
        else:
            path = f'{str(version)}/ucd/{file}'

    else:
        if version is None:
            path = f'emoji/latest/{file}'
        else:
            emoji_version = version.to_emoji()
            if emoji_version.is_v0:
                raise VersionError(f'UCD {version} has no emoji data')

            path = f'emoji/{emoji_version.short}/{file}'

    return f'https://www.unicode.org/Public/{path}'


def _build_request(url: str, **kwargs: str) -> Request:
    return Request(url, None, {'User-Agent': f'demicode {__version__}'} | kwargs)


_ONE_WEEK = 7 * 24 * 60 * 60
_VERSION_PATTERN = (
    re.compile('Version (?P<version>\d+[.]\d+[.]\d+) of the Unicode Standard')
)


def retrieve_latest_ucd_version(root: Path) -> Version:
    """
    Determine the latest UCD version. To avoid network accesses for every
    invocation of demicode, this method uses the `latest-ucd-version.txt` file
    in the local mirror directory as a cache and only checks the Unicode
    Consortium's servers once a week.
    """
    stamp_path = root / 'latest-ucd-version.txt'
    if stamp_path.is_file() and stamp_path.stat().st_mtime + _ONE_WEEK > time.time():
        try:
            return Version.of(stamp_path.read_text('utf8')).ucd()
        except ValueError:
            pass

    url = _get_ucd_url('ReadMe.txt')
    logger.info('retrieving latest UCD version from "%s"', url)
    with urlopen(_build_request(url)) as response:
        text = response.read().decode('utf8')

    rematch = _VERSION_PATTERN.search(text)
    if rematch is None:
        logger.error('UCD\'s "ReadMe.txt" elides version number')
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
        logger.info('mirroring UCD file "%s" to "%s"', url, path)
        with (
            urlopen(_build_request(url)) as response,
            open(path, mode='wb') as file
        ):
            shutil.copyfileobj(response, file)
    return path


# What irony: The CLDR is distributed as XML. Thankfully, they also make JSON
# available, through JavaScript's primary package registry, NPM.
_CLDR_URL = 'https://registry.npmjs.org/cldr-annotations-modern'
_CLDR_ACCEPT = 'application/vnd.npm.install-v1+json; q=1.0, application/json; q=0.8'


def mirror_latest_cldr_annotations(root: Path) -> Path:
    annotations_path = root / 'annotations.json'
    stamp_path = root / 'latest-cldr-version.txt'

    # If the stamp file exists, we are done.
    local_version = None
    if stamp_path.is_file() and stamp_path.stat().st_mtime + _ONE_WEEK > time.time():
        try:
            local_version = Version.of(stamp_path.read_text('utf8'))
            return annotations_path
        except:
            pass

    logger.info('checking version of CLDR annotations at "%s"', _CLDR_URL)
    with urlopen(_build_request(_CLDR_URL, Accept=_CLDR_ACCEPT)) as response:
        metadata = json.load(response)

    latest_version = Version.of(metadata['dist-tags']['latest'])
    if local_version == latest_version:
        stamp_path.write_text(str(latest_version), encoding='utf8')
        return annotations_path

    url = metadata['versions'][str(latest_version)]['dist']['tarball']
    tarball = root / 'annotations.tgz'
    logger.info('downloading CLDR annotations from "%s" to "%s"', url, tarball)
    with (urlopen(_build_request(url)) as response, open(tarball, mode='wb') as file):
        shutil.copyfileobj(response, file)

    member_name = 'package/annotations/en/annotations.json'
    logger.info('extracting "%s" to "%s"', member_name, annotations_path)
    with tar.open(tarball) as archive:
        member = archive.getmember(member_name)
        if not member.isfile():
            raise ValueError(f'entry for "{member_name}" in CLDR archive is not a file')
        with (
            cast(IO[bytes], archive.extractfile(member)) as source,
            open(annotations_path, mode='wb') as target
        ):
            shutil.copyfileobj(source, target)

    tarball.unlink()
    stamp_path.write_text(str(latest_version), encoding='utf8')
    return annotations_path


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
            info_entries[codepoint] = name, Category(category)
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
            (CodePointRange.of(codepoint, codepoint2), stem, Category(category))
        )

    return info_ranges, info_entries


def _retrieve_grapheme_breaks(
    path: Path, version: Version
) -> tuple[GraphemeClusterBreak, list[tuple[CodePointRange, GraphemeClusterBreak]]]:
    file = 'GraphemeBreakProperty.txt'
    path = mirror_unicode_data(path, file, version)
    defaults, data = ingest(
        path, lambda cp, p: (cp.to_range(), GraphemeClusterBreak[p[0]]))
    if len(defaults) != 1:
        raise ValueError(f'"{file}" with {len(defaults)} instead of one')
    if defaults[0][0] != RangeLimit.ALL:
        raise ValueError(f'"{file}" with default that covers only {defaults[0][0]}')
    return GraphemeClusterBreak(defaults[0][1]), sorted(data, key=lambda d: d[0])


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
) -> tuple[EastAsianWidth, list[tuple[CodePointRange, EastAsianWidth]]]:
    path = mirror_unicode_data(path, 'EastAsianWidth.txt', version)
    defaults, data = ingest(path, lambda cp, p: (cp.to_range(), EastAsianWidth(p[0])))
    if len(defaults) != 1:
        raise ValueError(f'"EastAsianWidth.txt" with {len(defaults)} instead of one')
    if defaults[0][0] != RangeLimit.ALL:
        raise ValueError(
            f'"EastAsianWidth.txt" with default that covers only {defaults[0][0]}')
    return EastAsianWidth(defaults[0][1]), data


def _retrieve_emoji_data(
    path: Path, version: Version
) -> dict[str, list[CodePointRange]]:
    try:
        path = mirror_unicode_data(path, 'emoji-data.txt', version)
    except VersionError:
        logger.warning('skipping emoji data for UCD %s', version)
        return {}

    _, raw_data = ingest(path, lambda cp, p: (cp.to_range(), p[0]))

    data = defaultdict(list)
    for range, label in raw_data:
        data[label].append(range)

    return data


def _retrieve_emoji_variations(path: Path, version: Version) -> list[CodePoint]:
    try:
        path = mirror_unicode_data(path, 'emoji-variation-sequences.txt', version)
    except VersionError:
        logger.warning('skipping emoji variation sequences for UCD %s', version)
        return []

    _, data = ingest(path, lambda cp, _: cp.to_sequence()[0])
    return list(dict.fromkeys(data)) # Remove all duplicates while preserving order


def _retrieve_emoji_sequences(
    root: Path, version: Version
) -> list[tuple[CodePointSequence, EmojiSequence, None | str]]:
    try:
        path = mirror_unicode_data(root, 'emoji-sequences.txt', version)
    except VersionError:
        logger.warning('skipping emoji sequences for UCD %s', version)
        return []

    _, data1 = ingest(path, lambda cp, p: (cp, EmojiSequence(p[0]), p[1]))

    path = mirror_unicode_data(root, 'emoji-zwj-sequences.txt', version)
    _, data2 = ingest(path, lambda cp, p: (cp, EmojiSequence(p[0]), p[1]))

    result: list[tuple[CodePointSequence, EmojiSequence, None | str]] = []
    for codepoints, sequence_property, name in itertools.chain(data1, data2):
        if isinstance(codepoints, CodePoint):
            result.append((codepoints.to_sequence(), sequence_property, name))
        elif isinstance(codepoints, CodePointSequence):
            result.append((codepoints, sequence_property, name))
        else:
            # For basic emoji, emoji-sequences.txt contains ranges of code
            # points and of names. That means some sequence names are missing.
            range = cast(CodePointRange, codepoints)
            first_name, _, last_name = name.partition('..')
            for codepoint in range:
                if codepoint == range.start:
                    given_name: None | str = first_name
                elif codepoint == range.stop:
                    given_name = last_name
                else:
                    given_name = None
                result.append((codepoint.to_sequence(), sequence_property, given_name))
    return result


def _retrieve_cldr_annotations(path: Path) -> dict[str, str]:
    path = mirror_latest_cldr_annotations(path)
    with open(path, mode='r') as file:
        data = json.load(file)

    return { k: v['tts'][0] for k,v in data['annotations']['annotations'].items() }


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
        self._version = Version.of(version).ucd()

    def prepare(self, validate: bool = False) -> Self:
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
        logger.info('using UCD version %s', version)

        self._info_ranges, self._info_entries = _retrieve_general_info(path, version)
        self._block_ranges = _retrieve_blocks(path, version)
        self._age_ranges = _retrieve_ages(path, version)
        self._width_default, self._width_ranges = _retrieve_widths(path, version)
        self._grapheme_default, self._grapheme_breaks = (
            _retrieve_grapheme_breaks(path, version))
        self._emoji_data = _retrieve_emoji_data(path, version)
        self._emoji_variations = frozenset(_retrieve_emoji_variations(path, version))

        # emoji-sequences.txt contains ranges of basic emoji and their names,
        # which means that some names aren't listed, too. Worse, names aren't
        # UCD names but CLDR names. Hence to correctly fill 'em in, we need to
        # retrieve CLDR annotations. If you look at the mirroring code, you'll
        # find that we source the JSON data from NPM of all places! 😜
        annotations = _retrieve_cldr_annotations(path)
        emoji_sequences = _retrieve_emoji_sequences(path, version)
        emoji_sequence_names: dict[CodePointSequence, str] = {}
        for codepoints, _, name in emoji_sequences:
            if name is None:
                name = annotations.get(str(codepoints))
                assert name is not None, f'{codepoints!r} must have a CLDR name'
            emoji_sequence_names[codepoints] = name
        self._emoji_sequence_names = emoji_sequence_names

        misc_props = _retrieve_misc_props(path, version)
        self._whitespace = frozenset(misc_props[BinaryProperty.White_Space.name])
        self._dashes = frozenset(misc_props[BinaryProperty.Dash.name])
        self._noncharacters = frozenset(
            misc_props[BinaryProperty.Noncharacter_Code_Point.name])
        self._variation_selectors = frozenset(
            misc_props[BinaryProperty.Variation_Selector.name])
        self._is_prepared = True

        if not validate:
            return self

        invalid = False
        breaks = self._grapheme_breaks
        for range in self._emoji_data[BinaryProperty.Extended_Pictographic]:
            for codepoint in range.codepoints():
                entry = breaks[_bisect_ranges(breaks, codepoint)]
                if codepoint in entry[0]:
                    logger.error(
                        'extended pictograph %s %r has grapheme cluster break '
                        'class %s, not Other',
                        codepoint, codepoint, entry[1].name
                    )
                    invalid = False

        if invalid:
            raise AssertionError('UCD validation failed; see log messages')
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

    @overload
    def _resolve_info(
        self, codepoint: CodePoint, offset: Literal[0]
    ) -> None | str:
        ...
    @overload
    def _resolve_info(
        self, codepoint: CodePoint, offset: Literal[1]
    ) -> None | Category:
        ...
    def _resolve_info(
        self, codepoint: CodePoint, offset: Literal[0,1]
    ) -> None | str | Category:
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
        return Category.Unassigned if category is None else category

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
        return self._resolve(codepoint, self._width_ranges, self._width_default)

    def grapheme_cluster_break(self, codepoint: CodePoint) -> GraphemeClusterBreak:
        """Look up the code point's grapheme cluster break class."""
        if self.test_property(codepoint, BinaryProperty.Extended_Pictographic):
            return GraphemeClusterBreak.Extended_Pictographic
        return self._resolve(codepoint, self._grapheme_breaks, self._grapheme_default)

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

    def emoji_sequence_name(self, codepoints: CodePointSequence) -> None | str:
        return self._emoji_sequence_names.get(codepoints)

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

    def wcwidth(self, codepoints: CodePointSequence) -> int:
        if codepoints in self._emoji_sequence_names:
            return 2

        total_width = 0
        for codepoint in codepoints:
            unidata = self.lookup(codepoint)
            width = unidata.wcwidth()
            if width == -1:
                return -1
            total_width += width
        return total_width


UCD = UnicodeCharacterDatabase(Path.cwd() / 'ucd')
