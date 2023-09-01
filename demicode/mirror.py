"""
Support for mirroring Unicode data on a user's machine.

This module contains the logic for discovering the latest versions of the
Unicode Character Database (UCD) and the Common Locale Data Repository (CLDR)
and for downloading necessary files from both. It also mirrors files from the
Unicode Emoji standard, treating them as part of the UCD.

The local mirror organizes UCD files by version and hence can easily cache the
files of more than one version. Since demicode only requires two CLDR files and
only for the names of emoji sequences, the local mirror only stores the latest
version of these two files.

To avoid generating excessive network traffic, the mirroring code ony queries
servers for the latest versions of UCD and CLDR once a week. If it finds that
the version has been updated, it eagerly loads all needed files.

By default, the local mirror uses the operating system's directory for caches.
"""
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


from .model import Version
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
    if file == 'ReadMe.txt':
        return 'https://www.unicode.org/Public/UCD/latest/ReadMe.txt'

    assert version is not None

    if file in _AUXILIARY_FILES:
        path = f'{version}/ucd/auxiliary'
    elif file in _CORE_EMOJI_FILES and version >= (13, 0, 0):
        path = f'{version}/ucd/emoji'
    elif file in _CORE_EMOJI_FILES or file in _ALSO_EMOJI_FILES:
        path = f'emoji/{version.in_short_format()}'
    else:
        path = f'{version}/ucd'

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
            return Version.of(stamp_path.read_text('utf8')).ucd()
        except ValueError:
            pass

    url = ucd_url_of('ReadMe.txt')
    logger.info('retrieving latest UCD version from "%s"', url)
    with urlopen(request_for(url)) as response:
        text = response.read().decode('utf8')

    rematch = _VERSION_PATTERN.search(text)
    if rematch is None:
        logger.error('UCD\'s "ReadMe.txt" elides version number')
        raise ValueError("""UCD's "ReadMe.txt" elides version number""")
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


def mirror_unicode_data(root: Path, filename: str, version: Version) -> Path:
    """Locally mirror a file from the Unicode Character Database."""
    version_root = root / str(version)
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

    logger.info('extracting "%s" to "%s"', member, path)
    with tar.open(tarball) as archive:
        member_info = archive.getmember(member)
        if not member_info.isfile():
            raise ValueError(
                f'entry for "{member}" in CLDR archive "{url}" is not a file')
        with (
            cast(IO[bytes], archive.extractfile(member_info)) as source,
            open(path, mode='wb') as target
        ):
            shutil.copyfileobj(source, target)

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
