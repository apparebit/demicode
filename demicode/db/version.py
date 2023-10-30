from collections.abc import Iterator
from typing import NamedTuple


class VersionError(Exception):
    """An error indicating a missing, inconsistent, or invalid version."""
    pass


class Version(NamedTuple):
    """A version number."""

    major: int
    minor: int
    patch: int

    @classmethod
    def of(cls, v: 'str | Version') -> 'Version':
        """
        Parse the string as a version number with at most three components. If
        the string has fewer components, pad the missing components with zero.
        """
        if isinstance(v, Version):
            return v

        try:
            components = tuple(int(c) for c in v.split('.'))
        except:
            raise VersionError(f'malformed components in version "{v}"')

        count = len(components)
        if count < 3:
            components += (0,) * (3 - count)
        elif count > 3:
            raise VersionError(f'too many components in version "{v}"')

        return cls(*components)

    def is_ucd(self) -> bool:
        """Determine whether this version is a valid UCD version."""
        return self in KNOWN_UCD_VERSIONS or self > KNOWN_UCD_VERSIONS[-1]

    def is_supported_ucd(self) -> bool:
        """Determine whether this version is a supported UCD version."""
        return self.is_ucd() and self >= FIRST_SUPPORTED_VERSION

    def is_emoji(self) -> bool:
        """
        Determine whether this version is a valid emoji version. This method
        accepts 0.0, 0.6, and 0.7, which have no associated files.
        """
        return self in KNOWN_EMOJI_VERSIONS or self > KNOWN_EMOJI_VERSIONS[-1]

    def to_emoji(self) -> 'Version':
        """Get the emoji version corresponding to this UCD version."""
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

    def in_short_format(self) -> str:
        return f'{self.major}.{self.minor}'

    def in_emoji_format(self) -> str:
        return f'E{self.major}.{self.minor}'

    def __str__(self) -> str:
        return '.'.join(str(c) for c in self)

    @staticmethod
    def all_supported() -> 'Iterator[Version]':
        for version in KNOWN_UCD_VERSIONS:
            if version >= FIRST_SUPPORTED_VERSION:
                yield version


FIRST_SUPPORTED_VERSION = Version(4, 1, 0)
KNOWN_UCD_VERSIONS = tuple(Version(*vs) for vs in [
    (1, 1, 0),
    (2, 0, 0),
    (2, 1, 0),
    (3, 0, 0),
    (3, 1, 0),
    (3, 2, 0),
    (4, 0, 0),
    (4, 1, 0),
    (5, 0, 0),
    (5, 1, 0),
    (5, 2, 0),
    (6, 0, 0),
    (6, 1, 0),
    (6, 2, 0),
    (6, 3, 0),
    (7, 0, 0),
    (8, 0, 0),
    (9, 0, 0),
    (10, 0, 0),
    (11, 0, 0),
    (12, 0, 0),
    (12, 1, 0),
    (13, 0, 0),
    (14, 0, 0),
    (15, 0, 0),
    (15, 1, 0),
])

KNOWN_EMOJI_VERSIONS = tuple(Version(*vs) for vs in (
    (0, 0, 0),
    (0, 6, 0),
    (0, 7, 0),
    (1, 0, 0),
    (2, 0, 0),
    (3, 0, 0),
    (4, 0, 0),
    (5, 0, 0),
    (11, 0, 0),
    (12, 0, 0),
    (12, 1, 0),
    (13, 0, 0),
    (13, 1, 0),
    (14, 0, 0),
    (15, 0, 0),
    (15, 1, 0),
))
