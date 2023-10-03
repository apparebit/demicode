from typing import NamedTuple


class VersioningError(Exception):
    """
    An error indicating that some resource is not available for the requested
    version of Unicode. See `demicode.mirror.mirror_unicode_data()` for details.
    """
    pass


FIRST_SUPPORTED_VERSION: tuple[int, int, int] = (4, 1, 0)


KNOWN_UCD_VERSIONS: tuple[tuple[int, int, int], ...] = tuple([
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
    (15, 1),
))


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
            raise ValueError(f'malformed components in version "{v}"')

        count = len(components)
        if count < 3:
            components += (0,) * (3 - count)
        elif count > 3:
            raise ValueError(f'too many components in version "{v}"')

        return cls(*components)

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

    def to_ucd(self) -> 'Version':
        """Validate this version as a UCD version."""
        if self.is_ucd():
            return self
        raise ValueError(f'version {self} is not a valid UCD version')

    def to_supported_ucd(self) -> 'Version':
        """Validate this version as a supported UCD version."""
        if self.is_ucd() and self >= FIRST_SUPPORTED_VERSION:
            return self
        raise ValueError(f'version {self} is not a valid and supported UCD version')

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

    def in_short_format(self) -> str:
        return f'{self.major}.{self.minor}'

    def in_emoji_format(self) -> str:
        return f'E{self.major}.{self.minor}'

    def __str__(self) -> str:
        return '.'.join(str(c) for c in self)
