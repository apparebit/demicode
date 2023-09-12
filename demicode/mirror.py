"""
Support for mirroring Unicode data on the local machine.

This module contains the logic for discovering the latest versions of the
Unicode Character Database (UCD) and the Common Locale Data Repository (CLDR)
and for downloading necessary files from both. It also mirrors files from the
Unicode Emoji standard. By default, the local mirror uses the operating system's
directory for application caches.

This module downloads UCD and Unicode Emoji files from Unicode's servers at
https://www.unicode.org/Public/. It downloads CLDR data in JSON format through
the Unicode Consortium's official distribution at https://registry.npmjs.org.
The local cache directory contains `latest-ucd-version.txt` and
`latest-cldr-version.txt`, which store the most recent version of the UCD and
CLDR. This module uses each file's last modified time to throttle server
accesses, checking for new versions only after a week.

To accommodate more than one Unicode version, the local mirror organizes
downloaded files into subdirectories named after the Unicode version. It does
not maintain nested subdirectories as found in the UCD.

Files from the Unicode Emoji standard are not stored separately but with the
corresponding UCD files. The `demicode.model` module implements the version
logic equating Unicode 8.0 with Emoji 1.0, 9.0 with E3.0, and 10.0 with E5.0.
Starting with Unicode 11.0, Unicode Emoji are released on the same schedule and
use the same version numbers. Starting with Unicode 13.0, the UCD includes
several emoji files that were previously part of the Unicode Emoji files.

Since demicode only requires two CLDR files and only for the names of emoji
sequences, the local mirror keeps only the latest version of these two files as
`annotations1.json` and `annotations2.json` in the cache directory.
"""
from collections.abc import Iterator
from contextlib import contextmanager
import json
import logging
import os
from pathlib import Path
import re
import sys
import shutil
import tarfile as tar
import time
from typing import Any, cast, IO, Literal, overload
from urllib.request import Request, urlopen


from .model import Version, VersioningError
from demicode import __version__


logger = logging.getLogger(__name__)


_USER_AGENT = (
    f'demicode/{__version__} (https://github.com/apparebit/demicode) '
    f'Python/{".".join(str(v) for v in sys.version_info[:3])}'
)

def request_for(url: str, **headers: str) -> Request:
    """
    Build a request for the given URL and headers. By default, this function
    only ensures a User-Agent that appropriately discloses this tool.
    """
    return Request(url, None, {'User-Agent': _USER_AGENT} | headers)


# --------------------------------------------------------------------------------------
# UCD


_AUXILIARY_FILES = ('GraphemeBreakProperty.txt', 'GraphemeBreakTest.txt')
_EXTRACTED_FILES = (
    'DerivedCombiningClass.txt',
    'DerivedGeneralCategory.txt'
)
_CORE_EMOJI_FILES = ('emoji-data.txt', 'emoji-variation-sequences.txt')
_ALSO_EMOJI_FILES = ('emoji-sequences.txt', 'emoji-test.txt', 'emoji-zwj-sequences.txt')

@overload
def ucd_url_of(file: Literal['ReadMe.txt'], version: Literal[None] = None) -> str:
    ...
@overload
def ucd_url_of(file: str, version: Version) -> str:
    ...
def ucd_url_of(file: str, version: None | Version = None) -> str:
    """
    Get the URL for the given UCD file and version.

    If the file is `ReadMe.txt`, the version is ignored since we only ever
    access that file to determine the latest version. For all other files, the
    version must be a valid version.

    A varying number of emoji data files (depending on version) are not part of
    the Unicode standard itself but belong to the Unicode Emoji standard, which
    is also known as [Unicode Technical Standard
    #51](https://unicode.org/reports/tr51/). With Unicode version 11.0, Unicode
    Emoji started using the same version number as the Unicode standard. But
    prior versions need to be mapped, with me preferring the earliest available
    Unicode Emoji version to approximate release dates. Alas, that works only
    for Unicode versions 10.0, 9.0, and 8.0, which map to E5.0, E3.0, and E1.0,
    respectively. Earlier Unicode versions must do without emoji data.
    """
    # ReadMe for latest version
    if file == 'ReadMe.txt':
        return 'https://www.unicode.org/Public/UCD/latest/ReadMe.txt'

    assert version is not None

    # Extended UCD files
    if file in _AUXILIARY_FILES:
        path = f'{version}/ucd/auxiliary'
    elif file in _EXTRACTED_FILES:
        path = f'{version}/ucd/extracted'
    elif file in _CORE_EMOJI_FILES and version >= (13, 0, 0):
        path = f'{version}/ucd/emoji'

    # Indic_Syllabic_Category was provisional in 6.0, became normative in 7.0.
    elif (
        file == 'IndicSyllabicCategory.txt' and version < (6, 0, 0)
    ):
        raise VersioningError(f'UCD {version} does not include {file}')

    # Core UCD files
    elif file not in _CORE_EMOJI_FILES and file not in _ALSO_EMOJI_FILES:
        path = f'{version}/ucd'

    # Unicode Emoji files (which took way too many iterations to get right)
    else:
        emoji_version = version.to_emoji()
        if (
            file == 'emoji-variation-sequences.txt' and emoji_version <= (4, 0, 0)
            or file == 'emoji-test.txt' and emoji_version <= (3, 0, 0)
            or file != 'emoji-data.txt' and emoji_version <= (1, 0, 0)
            or emoji_version.is_v0()
        ):
            raise VersioningError(
                f'UCD {version} or Emoji {emoji_version} does not include {file}')

        path = f'emoji/{emoji_version.in_short_format()}'

    return f'https://www.unicode.org/Public/{path}/{file}'


_VERSION_PATTERN = (
    re.compile('Version (?P<version>\d+[.]\d+[.]\d+) of the Unicode Standard')
)

_ONE_WEEK = 7 * 24 * 60 * 60

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
            return Version.of(stamp_path.read_text('utf8')).to_ucd()
        except ValueError:
            pass

    url = ucd_url_of('ReadMe.txt')
    logger.info('retrieving latest UCD version from "%s"', url)
    with urlopen(request_for(url)) as response:
        text = response.read().decode('utf8')

    rematch = _VERSION_PATTERN.search(text)
    if rematch is None:
        msg = '"ReadMe.txt" in latest UCD elides version number'
        logger.error(msg)
        raise ValueError(msg)
    version = Version.of(rematch.group('version'))

    root.mkdir(parents=True, exist_ok=True)
    stamp_path.write_text(str(version), encoding='utf8')
    return version


def local_cache_directory() -> Path:
    """Determine the operating system's cache directory."""
    platform = sys.platform
    if platform == 'win32':
        raw_path = os.environ.get('LOCALAPPDATA', '')
        if raw_path:
            path = Path(raw_path)
        else:
            path = Path.home()
    elif platform == 'darwin':
        path = Path(os.path.expanduser('~/Library/Caches'))
    else:
        raw_path = os.environ.get('XDG_CACHE_HOME', '').strip()
        if not raw_path:
            raw_path = os.path.expanduser('~/.cache')
        path = Path(raw_path)

    return Path(path) / 'demicode'


def mirror_unicode_data(filename: str, version: Version, cache: Path) -> Path:
    """
    Locally mirror a file from the Unicode Character Database. This method
    raises a `VersioningError` if the requested file does not yet exist for the
    requested Unicode version. In particular, that may happen for files with
    emoji data. Callers should be prepared to gracefully recover from this
    exception.
    """
    version_root = cache / str(version)
    path = version_root / filename
    if not path.exists():
        version_root.mkdir(parents=True, exist_ok=True)

        url = ucd_url_of(filename, version=version)
        logger.info('mirroring UCD file "%s" to "%s"', url, path)
        with (
            urlopen(request_for(url)) as response,
            open(path, mode='wb') as file
        ):
            shutil.copyfileobj(response, file)
    return path


@contextmanager
def mirrored_data(
    filename: str, version: Version, cache: Path
) -> Iterator[Iterator[str]]:
    """
    Create a new context manager that provides an iterator over the lines of a
    locally mirrored UCD file. Since the lines are not buffered, they must be
    consumed before leaving the context manager's scope. If the UCD version does
    not include the file, the context manager intercepts the resulting
    versioning error and offers an empty iterator instead. If the file has not
    been mirrored before, the context manager retrieves it from the Unicode
    Consortium's server.
    """
    try:
        path = mirror_unicode_data(filename, version, cache)
    except VersioningError:
        logger.info('skipping non-existent "%s" for UCD %s', filename, version)
        yield iter(())
        return
    with open(path, mode='r', encoding='utf8') as data:
        yield data


# --------------------------------------------------------------------------------------
# CLDR, or Let's Reimplement NPM in Python 😳


_CLDR_URL1 = 'https://registry.npmjs.org/cldr-annotations-modern'
_CLDR_URL2 = 'https://registry.npmjs.org/cldr-annotations-derived-modern'
_CLDR_ACCEPT = 'application/vnd.npm.install-v1+json; q=1.0, application/json; q=0.8'


def _load_cldr_metadata(url: str) -> dict[str, Any]:
    logger.info('loading metadata for CLDR annotations from "%s"', url)
    with urlopen(request_for(url, Accept=_CLDR_ACCEPT)) as response:
        return json.load(response)


def _load_cldr_annotations(
    root: Path, metadata: dict[str, Any], version: Version, member: str, path: Path
) -> None:
    url = metadata['versions'][str(version)]['dist']['tarball']
    tarball = root / 'annotations.tgz'
    logger.info('downloading CLDR annotations from "%s" to "%s"', url, tarball)
    with (
        urlopen(request_for(url)) as response,
        open(tarball, mode='wb') as file
    ):
        shutil.copyfileobj(response, file)

    # Extract via temporary file so that user isn't left with no file upon failure.
    tmp = path.with_suffix('.next.json')

    logger.info('extracting "%s" to "%s"', member, path)
    with tar.open(tarball) as archive:
        member_info = archive.getmember(member)
        if not member_info.isfile():
            raise ValueError(
                f'entry for "{member}" in CLDR archive "{url}" is not a file')
        with (
            cast(IO[bytes], archive.extractfile(member_info)) as source,
            open(tmp, mode='wb') as target
        ):
            shutil.copyfileobj(source, target)
    tmp.replace(path)

    tarball.unlink()


def mirror_cldr_annotations(root: Path) -> tuple[Path, Path]:
    annotations1 = root / 'annotations1.json'
    annotations2 = root / 'annotations2.json'
    stamp_path = root / 'latest-cldr-version.txt'

    local_version = None
    if annotations1.exists() and annotations2.exists():
        if (
            stamp_path.is_file()
            and stamp_path.stat().st_mtime + _ONE_WEEK > time.time()
        ):
            try:
                local_version = Version.of(stamp_path.read_text('utf8'))
                return annotations1, annotations2
            except:
                pass

    metadata = _load_cldr_metadata(_CLDR_URL1)
    latest_version = Version.of(metadata['dist-tags']['latest'])
    if (
        annotations1.exists()
        and annotations2.exists()
        and local_version == latest_version
    ):
        stamp_path.write_text(str(latest_version), encoding='utf8')
        return annotations1, annotations1

    member = 'package/annotations/en/annotations.json'
    _load_cldr_annotations(root, metadata, latest_version, member, annotations1)

    metadata = _load_cldr_metadata(_CLDR_URL2)
    member = 'package/annotationsDerived/en/annotations.json'
    _load_cldr_annotations(root, metadata, latest_version, member, annotations2)

    stamp_path.write_text(str(latest_version), encoding='utf8')
    return annotations1, annotations2
