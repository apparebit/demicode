from enum import Enum
from types import NotImplementedType
from typing import Any, NamedTuple, Self, SupportsInt, SupportsIndex


# --------------------------------------------------------------------------------------


class CodePoint(int):

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

    @property
    def first(self) -> 'CodePoint':
        return self

    def to_range(self) -> 'CodePointRange':
        return CodePointRange(self, self)

    def to_sequence(self) -> 'CodePointSequence':
        return CodePointSequence((self,))

    def __repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return f'U+{self:04X}'


# --------------------------------------------------------------------------------------


class CodePointRange(NamedTuple):

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

    @property
    def first(self) -> CodePoint:
        return self.start

    @property
    def last(self) -> CodePoint:
        return self.stop

    def to_range(self) -> 'CodePointRange':
        return self

    def to_sequence(self) -> 'CodePointSequence':
        raise TypeError(f'Unable to convert range {self} to sequence')

    def __repr__(self) -> str:
        return f'CodePointRange({self.start}, {self.stop})'

    def __str__(self) -> str:
        return f'{self.start}..{self.stop}'


# --------------------------------------------------------------------------------------


class CodePointSequence(tuple[CodePoint,...]):

    def __init__(self, *args, **kwargs) -> None:
        if len(self) == 0:
            raise ValueError('A code point sequence must not be empty')

    @classmethod
    def of(cls, *codepoints: str | SupportsInt | SupportsIndex) -> 'CodePointSequence':
        return cls(CodePoint.of(cp) for cp in codepoints)

    @property
    def first(self) -> CodePoint:
        return self[0]

    @property
    def last(self) -> CodePoint:
        return self[-1]

    def to_range(self) -> 'CodePointRange':
        raise TypeError(f'Unable to convert sequence {self} to range')

    def to_sequence(self) -> 'CodePointSequence':
        return self

    def __str__(self) -> str:
        return ' '.join(str(cp) for cp in self)


# --------------------------------------------------------------------------------------


class Limit(CodePoint, Enum):
    MIN = CodePoint(0)
    MAX = CodePoint(0x10_FFFF)

class RangeLimit(CodePointRange, Enum):
    ALL = CodePointRange(Limit.MIN, Limit.MAX)
