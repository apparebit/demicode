"""
Unicode code points.

This module defines demicode's representation for code points, ranges of code
points, and sequences of code points. It tries to remain lightweight and simple
while still providing useful object-oriented features. Hence this module defines
abstractions for code points, ranges, and sequences alike but does not introduce
a common base or separate mixins for shared functionality. Instead, all three
classes simply implement methods with the same name and signature. Not all of
them actually make sense across all three classes. Notably, that is the case for
`CodePointRange.to_sequence()` and `CodePointSequence.to_range()`, since ranges
and sequences simply cannot be converted into each other in the general case.
They nonetheless exist because the shared interface simplifies type annotations
and implementation of the UCD parser.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum
from types import NotImplementedType
from typing import Any, ClassVar, Self, SupportsInt, SupportsIndex


class CodePoint(int):

    MIN: 'ClassVar[CodePoint]'
    MAX: 'ClassVar[CodePoint]'

    __slots__ = ()

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        value = super().__new__(cls, *args, **kwargs)
        if not (0 <= value <= 0x10_FFFF):
            raise ValueError(f'{value:04x} is out of range')
        return value

    @classmethod
    def of(cls, value: str | SupportsInt | SupportsIndex) -> Self:
        """Convert the given value into a code point."""
        if isinstance(value, cls):
            return value
        elif not isinstance(value, str):
            return cls(value)

        length = len(value)
        if length == 1:
            return cls(ord(value))
        if length == 2 and value[1] in ('\uFE0E', '\uFE0F'):
            return cls(ord(value[0]))
        if 6 <= length <= 8 and value.startswith('U+'):
            return cls(value[2:], base=16)
        if 4 <= length <= 6:
            return cls(value, base=16)

        codepoints = ' '.join(str(CodePoint.of(c)) for c in value)
        raise ValueError(
            f'string of {codepoints} is not a valid code point representation')

    def is_singleton(self) -> bool:
        return True

    def to_singleton(self) -> 'CodePoint':
        return self

    def to_range(self) -> 'CodePointRange':
        return CodePointRange(self, self)

    def to_sequence(self) -> 'CodePointSequence':
        return CodePointSequence((self,))

    def codepoints(self) -> 'Iterator[CodePoint]':
        yield self

    def __repr__(self) -> str:
        return f'U+{self:04X}'

    def __str__(self) -> str:
        return chr(self)


# --------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CodePointRange:

    ALL: 'ClassVar[CodePointRange]'

    start: CodePoint
    stop: CodePoint

    @classmethod
    def of(
        cls,
        start: str | SupportsInt | SupportsIndex,
        stop: None | str | SupportsInt | SupportsIndex = None,
    ) -> 'CodePointRange':
        if stop is None:
            stop = start
        return CodePointRange(CodePoint.of(start), CodePoint.of(stop))

    def __contains__(self, codepoint: Any) -> bool:
        try:
            return self.start <= CodePoint.of(codepoint) <= self.stop
        except:
            return False

    def __lt__(self, other: object) -> NotImplementedType | bool:
        if isinstance(other, CodePoint):
            return self.stop < other
        elif isinstance(other, CodePointRange):
            return self.stop < other.start
        else:
            return NotImplemented

    def __gt__(self, other: object) -> NotImplementedType | bool:
        if isinstance(other, CodePoint):
            return other < self.start
        elif isinstance(other, CodePointRange):
            return other.stop < self.start
        else:
            return NotImplemented

    def can_merge_with(self, other: 'CodePoint | CodePointRange') -> bool:
        if isinstance(other, CodePoint):
            return self.start - 1 <= other <= self.stop + 1
        else:
            # not (other.stop < self.start - 1 or self.stop + 1 < other.start)
            return self.start - 1 <= other.stop and other.start <= self.stop + 1

    def merge(self, other: 'CodePoint | CodePointRange') -> 'CodePointRange':
        if isinstance(other, CodePoint):
            if self.start - 1 <= other <= self.stop + 1:
                return CodePointRange(min(self.start, other), max(self.stop, other))
        elif self.start - 1 <= other.stop and other.start <= self.stop + 1:
            return CodePointRange(
                min(self.start, other.start),
                max(self.stop, other.stop)
            )
        raise ValueError(f'{self!r} is apart from {other!r}')

    def __len__(self) -> int:
        return self.stop - self.start + 1

    def is_singleton(self) -> bool:
        return self.start == self.stop

    def to_singleton(self) -> 'CodePoint':
        if self.is_singleton():
            return self.start
        raise TypeError(f"Unable to convert range {self!r} to code point")

    def to_range(self) -> 'CodePointRange':
        return self

    def to_sequence(self) -> 'CodePointSequence':
        if self.is_singleton():
            return CodePointSequence([self.start])
        raise TypeError(f'Unable to convert range {self!r} to sequence')

    def codepoints(self) -> Iterator[CodePoint]:
        cursor = self.start
        yield cursor
        while cursor < self.stop:
            cursor = CodePoint(cursor + 1)
            yield cursor

    def __repr__(self) -> str:
        return f'{self.start!r}..{self.stop!r}'

    def __str__(self) -> str:
        return f'{self.start}..{self.stop}'


# --------------------------------------------------------------------------------------


class CodePointSequence(tuple[CodePoint,...]):

    __slots__ = ()

    def __init__(self, *args, **kwargs) -> None:
        if len(self) == 0:
            raise ValueError('a code point sequence must not be empty')

    @classmethod
    def of(cls, *codepoints: str | SupportsInt | SupportsIndex) -> 'CodePointSequence':
        return cls(CodePoint.of(cp) for cp in codepoints)

    @classmethod
    def from_string(cls, text: str) -> 'CodePointSequence':
        return cls(CodePoint.of(ord(c)) for c in text)

    def is_singleton(self) -> bool:
        return len(self) == 1

    def to_singleton(self) -> 'CodePoint':
        if self.is_singleton():
            return self[0]
        raise TypeError(f"Unable to convert sequence {self!r} to code point")

    def to_range(self) -> 'CodePointRange':
        if self.is_singleton():
            return CodePointRange(self[0], self[0])
        raise TypeError(f'Unable to convert sequence {self!r} to range')

    def to_sequence(self) -> 'CodePointSequence':
        return self

    def codepoints(self) -> Iterator[CodePoint]:
        return self.__iter__()

    def __repr__(self) -> str:
        return ' '.join(repr(cp) for cp in self)

    def __str__(self) -> str:
        return ''.join(chr(cp) for cp in self)


# --------------------------------------------------------------------------------------

CodePoint.MIN = CodePoint(0)
CodePoint.MAX = CodePoint(0x10_FFFF)
CodePointRange.ALL = CodePointRange(CodePoint.MIN, CodePoint.MAX)
