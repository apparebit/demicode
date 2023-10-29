from collections.abc import Iterator
from contextlib import contextmanager
import dataclasses
from datetime import datetime, timedelta, timezone
from io import StringIO
import json
import logging
import os
from pathlib import Path
import re
import shutil
import sys
import tarfile
from typing import Any, Callable, cast, IO, Self
from urllib.request import Request, urlopen

from . import __version__
from .version import Version, VersionError


_logger = logging.getLogger(__name__)


_HTTP_USER_AGENT = (
    f'demicode/{__version__} (https://github.com/apparebit/demicode) '
    f'Python/{".".join(str(v) for v in sys.version_info[:3])}'
)
_HTTP_CLDR_ACCEPT = (
    'application/vnd.npm.install-v1+json; q=1.0, application/json; q=0.8'
)


def _make_request(url: str, **headers: str) -> Any:
    """Request the resource with the given URL and return the response."""
    return urlopen(Request(url, None, {'User-Agent': _HTTP_USER_AGENT} | headers))


# --------------------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class CLDR:
    version: Version
    annotations: str
    derived_annotations: str

    @staticmethod
    def retrieve_metadata(url: str) -> tuple[Version, str]:
        _logger.info('retrieving CLDR annotation metadata from "%s"', url)
        with _make_request(url, Accept=_HTTP_CLDR_ACCEPT) as response:
            metadata = json.load(response)
        version = metadata['dist-tags']['latest']
        url = metadata['versions'][version]['dist']['tarball']
        return Version.of(version), url

    @classmethod
    def from_registry(cls) -> Self:
        v1, source1 = CLDR.retrieve_metadata(
            'https://registry.npmjs.org/cldr-annotations-modern')
        v2, source2 = CLDR.retrieve_metadata(
            'https://registry.npmjs.org/cldr-annotations-derived-modern')
        if v1 != v2:
            raise VersionError('versions of CLDR annotations diverge: {v1} and {v2}')
        return cls(v1, source1, source2)

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> Self:
        return cls(
            Version.of(data['version']),
            data['annotations'],
            data['derived-annotations'],
        )

    def to_dict(self) -> dict[str, object]:
        return {
            'version': str(self.version),
            'annotations': self.annotations,
            'derived-annotations': self.derived_annotations,
        }

    def filename(self, stem: str, suffix: str) -> str:
        return f'{stem}-{self.version}{suffix}'

    def retrieve(self, url: str, member: str, root: Path, stem: str) -> Path:
        archive = root / self.filename(stem, '.tgz')
        _logger.info('retrieving CLDR component from "%s" to "%s"', url, archive)
        with _make_request(url) as response, open(archive, mode='wb') as file:
            shutil.copyfileobj(response, file)

        path = root / self.filename(stem, '.json')
        tmp = path.with_suffix('.next.json')
        _logger.info('extracting CLDR annotations "%s" to "%s"', member, path)
        with tarfile.open(archive) as tarball:
            # Make sure member is a file and not a symlink.
            member_info = tarball.getmember(member)
            if not member_info.isfile():
                raise ValueError(
                    f'member "{member}" of CLDR component "{url}" is not a file')

            with cast(IO[bytes], tarball.extractfile(member)) as source:
                with open(tmp, mode='wb') as target:
                    shutil.copyfileobj(source, target)

        tmp.replace(path)
        archive.unlink()
        return path

    def retrieve_all(self, root: Path) -> Iterator[Path]:
        for url, member, stem in (
            (
                self.annotations,
                'package/annotations/en/annotations.json',
                'annotations',
            ),
            (
                self.derived_annotations,
                'package/annotationsDerived/en/annotations.json',
                'derived-annotations',
            )
        ):
            if not (root / self.filename(stem, '.json')).is_file():
                yield self.retrieve(url, member, root, stem)


# --------------------------------------------------------------------------------------


_UCD_VERSION_PATTERN = (
    re.compile(r'Version (?P<version>\d+[.]\d+[.]\d+) of the Unicode Standard')
)


def _get_app_cache() -> Path:
    """Determine the operating system's cache directory for applications."""
    platform = sys.platform
    if platform == 'win32':
        raw_path = os.environ.get('LOCALAPPDATA', '')
        return Path(raw_path) if raw_path else Path.home()
    elif platform == 'darwin':
        return Path(os.path.expanduser('~/Library/Caches'))
    else:
        raw_path = os.environ.get('XDG_CACHE_HOME', '').strip()
        if not raw_path:
            raw_path = os.path.expanduser('~/.cache')
        return Path(raw_path)


def _to_manifest(mirror: Path) -> Path:
    return mirror.with_suffix('.manifest.json')


def _check_ucd_version(version: Version) -> None:
    if not version.is_ucd():
        raise VersionError(f'v{version} is not a valid UCD version')
    if not version.is_supported_ucd():
        raise VersionError(f'v{version} is not supported')


@dataclasses.dataclass(frozen=True, slots=True)
class Mirror:
    root: Path
    version: Version
    cldr: CLDR
    timestamp: datetime

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            raise ValueError(f'timestamp {self.timestamp} has no timezone')
        offset = timezone.utc.utcoffset(None)
        if offset.total_seconds() != 0:
            raise ValueError(f'timestamp {self.timestamp} is {offset} from UTC')
        if self.version != (0, 0, 0):
            _check_ucd_version(self.version)

    @property
    def manifest(self) -> Path:
        return _to_manifest(self.root)

    @property
    def files(self) -> 'FileManager':
        return FileManager(self)

    def younger_than(self, age: timedelta) -> bool:
        return (datetime.now(timezone.utc) - self.timestamp) < age

    def check_version(self, version: Version) -> None:
        _check_ucd_version(version)
        if version > self.version:
            raise VersionError(f'v{version} is from future')

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            Path(data['root']),
            Version.of(data['version']),
            CLDR.from_dict(data['cldr']),
            datetime.fromisoformat(data['timestamp'])
        )

    def to_dict(self) -> dict[str, object]:
        return {
            'root': str(self.root),
            'version': str(self.version),
            'cldr': self.cldr.to_dict(),
            'timestamp': self.timestamp.isoformat(),
        }

    @classmethod
    def from_manifest(cls, root: str | Path) -> Self:
        root = Path(root)
        if root.exists() and not root.is_dir():
            raise ValueError('"root" is not a directory')

        try:
            with open(_to_manifest(root), mode='rb') as file:
                return cls.from_dict(json.load(file))
        except:
            return cls(
                root,
                Version(0, 0, 0),
                CLDR(Version(0, 0, 0), '', ''),
                datetime.fromtimestamp(665, tz=timezone.utc),
            )

    @staticmethod
    def retrieve_ucd_version() -> Version:
        url = 'https://www.unicode.org/Public/UCD/latest/ReadMe.txt'
        _logger.info('retrieving latest UCD version from "%s"', url)
        with _make_request(url) as response:
            text = response.read().decode('utf8')

        if (match := _UCD_VERSION_PATTERN.search(text)) is None:
            msg = 'latest "ReadMe.txt" in UCD elides version number'
            raise VersionError(msg)

        version = Version.of(match.group('version'))
        assert version.is_supported_ucd()
        return version

    @classmethod
    def from_origin(cls, root: str | Path) -> Self:
        root = Path(root)
        return cls(
            root,
            Mirror.retrieve_ucd_version(),
            CLDR.from_registry(),
            datetime.now(timezone.utc),
        )

    def retrieve_data(
        self, previous: 'Mirror', tick: None | Callable[[], None] = None
    ) -> Self:
        tick = tick or (lambda: None)
        if self.version != previous.version:
            for _ in self.files.retrieve_version(self.version):
                tick()
        if self.cldr.version != previous.cldr.version:
            for _ in self.cldr.retrieve_all(self.root):
                tick()
        return dataclasses.replace(self, timestamp=datetime.now(timezone.utc))

    def save_manifest(self) -> Self:
        tmp = self.manifest.with_suffix('.next.json')
        with open(tmp, mode='w', encoding='utf8') as file:
            json.dump(self.to_dict(), file, indent=2)
        tmp.replace(self.manifest)
        return self

    @classmethod
    def setup(
        cls,
        mirror: None | str | Path = None,
        tick: None | Callable[[], None] = None
    ) -> Self:
        mirror = _get_app_cache() if mirror is None else Path(mirror)

        previous = cls.from_manifest(mirror)
        if previous.younger_than(timedelta(weeks=1)):
            return previous

        current = cls.from_origin(mirror)
        current = current.retrieve_data(previous, tick)
        return current.save_manifest()


# --------------------------------------------------------------------------------------


_CORE_EMOJI_FILES = ('emoji-data.txt', 'emoji-variation-sequences.txt')
_EMOJI_FILES = _CORE_EMOJI_FILES + (
    'emoji-sequences.txt',
    'emoji-test.txt',
    'emoji-zwj-sequences.txt',
)
_UCD_FILES = _EMOJI_FILES + (
    'Blocks.txt',
    'DerivedAge.txt',
    'DerivedCombiningClass.txt',
    'DerivedCoreProperties.txt',
    'DerivedGeneralCategory.txt',
    'EastAsianWidth.txt',
    'GraphemeBreakProperty.txt',
    'IndicSyllabicCategory.txt',
    'PropertyValueAliases.txt',
    'PropList.txt',
    'Scripts.txt',
    'UnicodeData.txt',
)


@dataclasses.dataclass(frozen=True, slots=True)
class FileManager:
    mirror: Mirror

    @property
    def root(self) -> Path:
        return self.mirror.root

    @property
    def version(self) -> Version:
        return self.mirror.version

    def url(self, filename: str, version: Version) -> None | str:
        """
        Determine the UCD URL for the given file and UCD version. This method
        raises an exception if the file or version are known to be invalid. It
        returns `None` if file and version are valid but the file has not been
        released for the UCD version.
        """
        _check_ucd_version(version)
        if version > self.mirror.version:
            raise VersionError(f'v{version} has not been released')
        elif filename in ('GraphemeBreakProperty.txt', 'GraphemeBreakTest.txt'):
            path = f'{version}/ucd/auxiliary'
        elif filename in ('DerivedCombiningClass.txt', 'DerivedGeneralCategory.txt'):
            path = f'{version}/ucd/extracted'
        elif filename in _CORE_EMOJI_FILES and version >= (13, 0, 0):
            path = f'{version}/ucd/emoji'
        elif filename in _EMOJI_FILES:
            emo_version = version.to_emoji()
            if (
                filename == 'emoji-variation-sequences.txt' and emo_version <= (4, 0, 0)
                or filename == 'emoji-test.txt' and emo_version <= (3, 0, 0)
                or filename != 'emoji-data.txt' and emo_version <= (1, 0, 0)
                or emo_version.major == 0
            ):
                return None

            path = f'emoji/{emo_version.in_short_format()}'
        elif filename == 'IndicSyllabicCategory.txt' and version < (6, 0, 0):
            # File was provisional in 6.0 and became normative in 7.0
            return None
        elif filename in _UCD_FILES:
            path = f'{version}/ucd'
        else:
            raise ValueError(f'"{filename}" is not a supported UCD file')

        return f'https://www.unicode.org/Public/{path}/{filename}'

    def path(self, filename: str, version: Version) -> Path:
        return self.root / str(version) / filename

    def retrieve(self, url: str, path: Path) -> Path:
        _logger.info('retrieving UCD file from "%s" to "%s"', url, path)
        path.parent.mkdir(exist_ok=True)
        with _make_request(url) as response, open(path, mode='wb') as file:
            shutil.copyfileobj(response, file)
        return path

    def retrieve_version(self, version: None | Version = None) -> Iterator[Path]:
        version = version or self.mirror.version
        for filename in _UCD_FILES:
            # Raises upon invalid version
            url = self.url(filename, version)
            if url is not None:
                path = self.path(filename, version)
                if not path.is_file():
                    yield self.retrieve(url, self.path(filename, version))

    def retrieve_all(self) -> Iterator[Path]:
        for version in Version.supported():
            yield from self.retrieve_version(version)

    @contextmanager
    def data(self, filename: str, version: Version) -> Iterator[IO[str]]:
        path = self.path(filename, version)
        if not path.is_file():
            # Raises upon invalid filename or version
            url = self.url(filename, version)
            if url is None:
                yield StringIO()
                return
            self.retrieve(url, path)
        with open(path, mode='r', encoding='utf8') as file:
            yield file
