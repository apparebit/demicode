from collections.abc import Iterable, Iterator
from contextlib import AbstractContextManager, contextmanager
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
from typing import Any, Callable, cast, ClassVar, IO, overload, Self
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

    def retrieve_all(
        self,
        root: Path,
        tick: None | Callable[[], None] = None
    ) -> None:
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
                self.retrieve(url, member, root, stem)
                if tick:
                    tick()


# --------------------------------------------------------------------------------------


_UCD_VERSION_PATTERN = (
    re.compile(r'Version (?P<version>\d+[.]\d+[.]\d+) of the Unicode Standard')
)


def _to_manifest_path(mirror: Path) -> Path:
    return mirror.with_suffix('.manifest.json')


def _check_mirror_path(mirror: Path) -> None:
    if mirror.exists() and not mirror.is_dir():
        raise NotADirectoryError(str(mirror))


def _check_ucd_version(version: Version) -> None:
    if not version.is_ucd():
        raise VersionError(f'v{version} is not a valid UCD version')
    if not version.is_supported_ucd():
        raise VersionError(f'v{version} is not supported')


@dataclasses.dataclass(frozen=True, slots=True)
class Manifest:
    """
    Manifest of mirrored Unicode files. The manifest tracks the latest Unicode
    and CLDR versions as well as which UCD files have been mirrored.

    The schema ID is a concise mechanism for tracking which files are mirrored
    for each Unicode version, i.e., the ones listed in _UCD_FILES. Hence the
    schema ID must be incremented whenever the value of _UCD_FILES changes.
    Hence files must not be mirrored individually but always at the granularity
    of UCD versions, i.e., all files for a given version. Schema ID 0 identifies
    a void manifest, which prevents the mirroring of files and cannot be
    persisted. It simply provides the initial manifest when (re)initializing a
    mirror.
    """

    schema: int
    mirror: Path
    ucd: Version
    versions: tuple[Version, ...]
    cldr: CLDR
    timestamp: datetime

    VOID: ClassVar[int] = 0
    SCHEMA: ClassVar[int] = 1

    def __post_init__(self) -> None:
        if self.schema < self.VOID or self.schema > self.SCHEMA:
            raise ValueError(f'invalid schema ID {self.schema}')

        _check_mirror_path(self.mirror)
        if not self.mirror.is_absolute():
            raise AssertionError(f'"{self.mirror}" is not absolute')

        if self.schema == self.VOID:
            if (
                self.ucd != (0, 0, 0)
                or len(self.versions) != 0
                or self.cldr.version != (0, 0, 0)
                or self.cldr.annotations != ''
                or self.cldr.derived_annotations != ''
            ):
                raise AssertionError('void manifest has invalid attributes')
        else:
            if (
                self.ucd == (0, 0, 0)
                # During mirror setup, versions may be empty.
                or self.cldr.version == (0, 0, 0)
                or self.cldr.annotations == ''
                or self.cldr.derived_annotations == ''
            ):
                raise AssertionError('non-void manifest has void attributes')

            _check_ucd_version(self.ucd)
            for version in self.versions:
                if not version.is_supported_ucd() or version > self.ucd:
                    raise ValueError(
                        f'invalid mirrored version {version} (UCD {self.ucd})')

        if self.timestamp.tzinfo is None:
            raise AssertionError(f'timestamp {self.timestamp} without timezone')
        offset = self.timestamp.tzinfo.utcoffset(None)
        if offset is not None and offset.total_seconds() != 0:
            raise AssertionError(
                f'timestamp {self.timestamp} has offset {offset} from UTC')

    def check_not_void(self) -> None:
        if self.schema == self.VOID:
            raise AssertionError(
                'void manifest cannot be modified or saved, '
                'does not provide file access'
            )

    @property
    def path(self) -> Path:
        return _to_manifest_path(self.mirror)

    @property
    def files(self) -> 'FileManager':
        self.check_not_void()
        return FileManager(self.mirror, self.ucd)

    def younger_than(self, age: timedelta) -> bool:
        return (datetime.now(timezone.utc) - self.timestamp) < age

    def check_version(self, version: Version) -> None:
        _check_ucd_version(version)
        self.check_not_void()
        if version > self.ucd:
            raise VersionError(f'v{version} is from future')

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            data['schema'],
            Path(data['mirror']),
            Version.of(data['ucd']),
            tuple(sorted(Version.of(v) for v in data['versions'])),
            CLDR.from_dict(data['cldr']),
            datetime.fromisoformat(data['timestamp'])
        )

    def to_dict(self) -> dict[str, object]:
        return {
            'schema': self.schema,
            'mirror': str(self.mirror),
            'ucd': str(self.ucd),
            'versions': [str(v) for v in self.versions],
            'cldr': self.cldr.to_dict(),
            'timestamp': self.timestamp.isoformat(),
        }

    @classmethod
    def from_file(cls, mirror: str | Path) -> Self:
        mirror = Path(mirror).resolve()
        _check_mirror_path(mirror)

        try:
            with open(_to_manifest_path(mirror), mode='rb') as file:
                return cls.from_dict(json.load(file))
        except:
            return cls(
                cls.VOID,
                mirror,
                Version(0, 0, 0),
                (),
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
    def from_origin(cls, mirror: str | Path) -> Self:
        mirror = Path(mirror).resolve()
        _check_mirror_path(mirror)
        ucd = Manifest.retrieve_ucd_version()
        ts = datetime.now(timezone.utc)

        return cls(cls.SCHEMA, mirror, ucd, (), CLDR.from_registry(), ts)

    def with_inventory(self, *versions: Version) -> Self:
        self.check_not_void()
        return dataclasses.replace(
            self,
            versions=tuple(sorted(versions)),
            timestamp=datetime.now(timezone.utc),
        )

    def sync(
        self, previous: 'Manifest', tick: None | Callable[[], None] = None
    ) -> Self:
        # Upon creation of a new mirror, the previous manifest is void.
        self.check_not_void()
        if self.mirror != previous.mirror:
            raise ValueError(
                f'different mirror directories "{self.mirror}" and "{previous.mirror}"')

        # Only sync files if mirror and previous manifest disagree on versions.
        file_manager = self.files
        versions = file_manager.scan_retrieved_versions()
        if set(previous.versions) != set(versions):
            file_manager.retrieve_all(versions, tick)

        # Eagerly mirror latest UCD version.
        if self.ucd not in versions:
            versions.append(self.ucd)
            file_manager.retrieve_all(self.ucd, tick)

        if self.cldr.version != previous.cldr.version:
            self.cldr.retrieve_all(self.mirror, tick)

        return self.with_inventory(*versions)

    def save_manifest(self) -> Self:
        self.check_not_void()

        tmp = self.path.with_suffix('.next.json')
        with open(tmp, mode='w', encoding='utf8') as file:
            json.dump(self.to_dict(), file, indent=2)
        tmp.replace(self.path)

        return self

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~

    @classmethod
    def setup(
        cls,
        mirror: str | Path,
        tick: None | Callable[[], None] = None
    ) -> Self:
        # Both from_file() and from_origin() do this, too. But that leaves a
        # tiny window for a file system mutation to produce inconsistent
        # results. So it's better to just lock in the path.
        mirror = Path(mirror).resolve()

        # If no manifest exists, previous will be a void manifest with a
        # timestamp surprisingly close to the start of the epoch.
        previous = cls.from_file(mirror)
        if previous.younger_than(timedelta(weeks=1)):
            return previous

        # Resulting manifest may differ from self!
        return (
            cls.from_origin(mirror)
            .sync(previous, tick)
            .save_manifest()
        )

    def require(
        self,
        version: Version,
        tick: None | Callable[[], None] = None
    ) -> Self:
        self.check_not_void()
        self.check_version(version)
        if version in self.versions:
            return self

        self.files.retrieve_all(version, tick)
        return self.with_inventory(version, *self.versions).save_manifest()


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

_LOOSE_VERSION_PATTERN = re.compile(r'[0-9]+[.][0-9]+([.][0-9]+)')
_STRICT_VERSION_PATTERN = re.compile(r'[1-9][0-9]*[.](0|[1-9][0-9]*)[.](0|[1-9][0-9]*)')


@dataclasses.dataclass(frozen=True, slots=True)
class FileManager:
    """
    The mirror's file manager. This class is responsible for retrieving files
    from origin servers and scanning the mirror for inventory.
    """

    mirror: Path
    ucd: Version

    def url(self, filename: str, version: Version) -> None | str:
        """
        Determine the UCD URL for the given file and UCD version. This method
        raises an exception if the file or version are known to be invalid. It
        returns `None` if file and version are valid but the file has not been
        released for the UCD version.
        """
        _check_ucd_version(version)
        if version > self.ucd:
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
        return self.mirror / str(version) / filename

    def retrieve(self, url: str, path: Path) -> Path:
        _logger.info('retrieving UCD file from "%s" to "%s"', url, path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with _make_request(url) as response, open(path, mode='wb') as file:
            shutil.copyfileobj(response, file)
        return path

    @overload
    def retrieve_all(
        self, __version: Iterable[Version], __tick: None | Callable[[], None] = None
    ) -> None: ...

    @overload
    def retrieve_all(
        self, __version: Version, __tick: None | Callable[[], None] = None
    ) -> None: ...

    @overload
    def retrieve_all(
        self, __tick: None | Callable[[], None] = None
    ) -> None: ...

    def retrieve_all(
        self,
        __version: None | Version | Iterable[Version] | Callable[[], None] = None,
        __tick: None | Callable[[], None] = None,
    ) -> None:
        """Retrieve all files for one version, several versions, or all versions."""
        if __version is None:
            versions = Version.all_supported()
        elif callable(__version):
            versions = Version.all_supported()
            __tick = __version
        elif isinstance(__version, Version):
            versions = iter([__version])
        else:
            versions = iter(__version)

        tick = __tick or (lambda: None)

        for version in versions:
            for filename in _UCD_FILES:
                url = self.url(filename, version)
                if url is not None:
                    path = self.path(filename, version)
                    if not path.is_file():
                        self.retrieve(url, path)
                        tick()

    def scan_retrieved_versions(self) -> list[Version]:
        """
        Scan mirror for retrieved versions. Since this method does not check for
        a version's files, consider invoking retrieve_all() on the result.
        """
        result: list[Version] = []
        for entry in self.mirror.iterdir():
            if not _LOOSE_VERSION_PATTERN.match(entry.name):
                continue
            if not _STRICT_VERSION_PATTERN.match(entry.name):
                raise VersionError(
                    f'unexpected entry "{entry.name}" in mirror '
                    f'directory "{self.mirror}"; please remove'
                )
            if not entry.is_dir():
                raise VersionError(
                    f'entry "{entry.name}" in mirror directory "{self.mirror}" '
                    'is not a directory; please remove'
                )

            version = Version.of(entry.name)
            if not version.is_supported_ucd() or version > self.ucd:
                raise VersionError(
                    f'entry "{entry.name}" in mirror directory "{self.mirror}" '
                    'is not a valid UCD version; please remove'
                )

            result.append(version)

        return result

    @contextmanager
    def data(self, filename: str, version: Version) -> Iterator[IO[str]]:
        path = self.path(filename, version)
        if not path.is_file():
            # Raises upon invalid filename or version
            url = self.url(filename, version)
            if url is None:
                yield StringIO()
                return
            # We used to self.retrieve(url, path) here. But now we support only
            # versions appearing in manifest. So we let open() raise an error.
        with open(path, mode='r', encoding='utf8') as file:
            yield file


# --------------------------------------------------------------------------------------


class Mirror:
    """
    Manager for locally mirroring UCD and CLDR files. This class largely is a
    thin veneer over `Manifest` that provides reasonable defaults for the
    mirror's directory and current version and otherwise only exposes the
    functionality for accessing the data.
    """

    @classmethod
    def ci(cls) -> bool:
        """Determine whether demicode is running in CI."""
        return os.getenv('CI') == 'true'

    @classmethod
    def app_cache_path(cls) -> Path:
        """Determine the path to the operating system's application cache."""
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

    @classmethod
    def default_path(cls) -> Path:
        """Determine the default path for the mirror"""
        if cls.ci():
            return Path.cwd() / 'ucd'
        else:
            return cls.app_cache_path() / 'demicode' / 'ucd'

    def __init__(
        self,
        root: None | str | Path = None,
        version: None | str | Version = None,
        tick: None | Callable[[], None] = None,
    ) -> None:
        if root is not None:
            root = Path(root)
            _check_mirror_path(root)
        if version is not None:
            version = Version.of(version)
            _check_ucd_version(version)

        self._manifest = Manifest.setup(root or self.default_path(), tick)
        if version is not None:
            self._manifest = self._manifest.require(version, tick)
        self._version = version or self._manifest.ucd
        self._file_manager = self._manifest.files

    @property
    def root(self) -> Path:
        return self._manifest.mirror

    @property
    def version(self) -> Version:
        return self._version

    @property
    def cldr(self) -> Self:
        return self

    def cldr_filename(self, stem: str, suffix: str) -> str:
        return self._manifest.cldr.filename(stem, suffix)

    def url(self, filename: str, version: Version) -> None | str:
        return self._file_manager.url(filename, version)

    def retrieve_all(self, tick: None | Callable[[], None] = None) -> None:
        return self._file_manager.retrieve_all(tick)

    def data(self, filename: str, version: Version) -> AbstractContextManager[IO[str]]:
        return self._file_manager.data(filename, version)
