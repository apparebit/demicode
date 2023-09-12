"""
Unicode code points.

This module defines demicode's representation for code points, ranges of code
points, and sequences of code points: `CodePoint`, `CodePointRange`, and
`CodePointSequence`. It also defines convenient type aliases for the union of
code points with ranges, with sequences, and with both ranges and sequences:
`CodePointOrRange`, `CodePointOrSequence`, and `CodePoints`. While the three
classes do *not* share a superclass, they do implement several, parameterless
methods:

    * `is_singleton()`
    * `to_singleton()`
    * `to_range()`
    * `to_sequence()`
    * `to_sequence_head()`
    * `codepoints()`
    * `__repr__()`
    * `__str__()`

Since all three classes implement these methods, a parameter or variable
declared with one of the three type aliases can still safely invoke any of them.

The first five methods help with parsing and processing UCD files: Demicode's
parsing code processes UCD files one line at a time and instantiates the least
complex representation for each line's code points. That is consistent with the
notation in those files and also conserves memory. At the same time, most
downstream code handles either only ranges or only sequences. The conversion
methods make integration seamless:

  * `to_range()` converts code points and degenerate sequences (with one
    element) to ranges, while also failing on unexpected full sequences.
  * Similarly, `to_sequence()` converts code points and degenerate ranges (with
    the same start and stop) to sequences, while also failing on unexpected full
    ranges.
  * `to_sequence_head()` optimizes a corner case, in which a sequence is
    expected but only the first element is needed, and avoids the creation of
    useless intermediate sequences for code points and degenerate ranges.
  * `is_singleton()` and `to_singleton()` help detect and convert degenerate
    instances.

`codepoints()` returns an iterator over the individual code points represented
by the object.

The `repr()` of all three classes uses Unicode `U+` notation for code points,
whereas `str()` shows actual characters.

Code point ranges `can_merge()` and `merge()` with each other. Two ranges are
mergeable if the union of all their code points can be represented by a single,
continuous range. As a convenience, code points implement the same two methods,
albeit they too return ranges, even for degenerate cases. To exclude degenerate
ranges (or sequences for that matter), iterate over the code point objects and
replace every object that `is_singleton()` with the result of `to_singleton()`.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from types import NotImplementedType
from typing import Any, ClassVar, Self, SupportsInt, SupportsIndex, TypeAlias


class CodePoint(int):

    MIN: 'ClassVar[CodePoint]'
    MAX: 'ClassVar[CodePoint]'

    SPACE: 'ClassVar[CodePoint]'
    DELETE: 'ClassVar[CodePoint]'
    PAD: 'ClassVar[CodePoint]'
    NO_BREAK_SPACE: 'ClassVar[CodePoint]'
    SOFT_HYPHEN: 'ClassVar[CodePoint]'
    HANGUL_JUNGSEONG_FILLER: 'ClassVar[CodePoint]'
    HANGUL_JONGSEONG_SSANGNIEUN: 'ClassVar[CodePoint]'
    ZERO_WIDTH_JOINER: 'ClassVar[CodePoint]'
    COMBINING_ENCLOSING_KEYCAP: 'ClassVar[CodePoint]'
    FULL_BLOCK: 'ClassVar[CodePoint]'
    LEFTWARDS_BLACK_ARROW: 'ClassVar[CodePoint]'
    RIGHTWARDS_BLACK_ARROW: 'ClassVar[CodePoint]'
    VARIATION_SELECTOR_1: 'ClassVar[CodePoint]'
    VARIATION_SELECTOR_2: 'ClassVar[CodePoint]'
    TEXT_VARIATION_SELECTOR: 'ClassVar[CodePoint]'
    EMOJI_VARIATION_SELECTOR: 'ClassVar[CodePoint]'
    REPLACEMENT_CHARACTER: 'ClassVar[CodePoint]'
    REGIONAL_INDICATOR_SYMBOL_LETTER_A: 'ClassVar[CodePoint]'
    REGIONAL_INDICATOR_SYMBOL_LETTER_Z: 'ClassVar[CodePoint]'

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
        if length == 2 and (
            CodePoint.VARIATION_SELECTOR_1
            <= ord(value[1]) <= CodePoint.EMOJI_VARIATION_SELECTOR
        ):
            return cls(ord(value[0]))
        if value.startswith('U+'):
            if not (6 <= length <= 8):
                raise ValueError(f'"U+" not followed by 4-6 hex digits in "{value}"')
            return cls(value[2:], base=16)
        if value.startswith('0x'):
            if not (4 <= length <= 8):
                raise ValueError(f'"0x" not followed by 2-6 hex digits in "{value}"')
            return cls(value[2:], base=16)
        if 4 <= length <= 6:
            return cls(value, base=16)

        raise ValueError(f'"{value}" does not consist of 4-6 hex digits')

    def can_merge(self, other: 'CodePoint | CodePointRange') -> bool:
        if isinstance(other, CodePoint):
            return other - 1 <= self <= other + 1
        else:
            return other.start - 1 <= self <= other.stop + 1

    def merge(self, other: 'CodePoint | CodePointRange') -> 'CodePointRange':
        match other:
            case CodePoint():
                if other - 1 <= self <= other + 1:
                    return CodePointRange(min(self, other), max(self, other))
            case _: # CodePointRange()
                if other.start - 1 <= self <= other.stop + 1:
                    return CodePointRange(min(self, other.start), max(self, other.stop))
        raise ValueError(f'{self!r} cannot possibly merge with {other!r}')

    def is_singleton(self) -> bool:
        return True

    def to_singleton(self) -> 'CodePoint':
        return self

    def to_range(self) -> 'CodePointRange':
        return CodePointRange(self, self)

    def to_sequence(self) -> 'CodePointSequence':
        return CodePointSequence((self,))

    def to_sequence_head(self) -> 'CodePoint':
        return self

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

    def __len__(self) -> int:
        return self.stop - self.start + 1

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

    def can_merge(self, other: 'CodePoint | CodePointRange') -> bool:
        if isinstance(other, CodePoint):
            return self.start - 1 <= other <= self.stop + 1
        else:
            # not (other.stop < self.start - 1 or self.stop + 1 < other.start)
            return self.start - 1 <= other.stop and other.start <= self.stop + 1

    def merge(self, other: 'CodePoint | CodePointRange') -> 'CodePointRange':
        match other:
            case CodePoint():
                if self.start - 1 <= other <= self.stop + 1:
                    return CodePointRange(min(self.start, other), max(self.stop, other))
            case _: # CodePointRange
                if self.start - 1 <= other.stop and other.start <= self.stop + 1:
                    return CodePointRange(
                        min(self.start, other.start),
                        max(self.stop, other.stop)
                    )
        raise ValueError(f'{self!r} cannot possibly merge with {other!r}')

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

    def to_sequence_head(self) -> 'CodePoint':
        if self.is_singleton():
            return self.start
        raise TypeError(f'Unable to treat range {self!r} as sequence')

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

    def to_sequence_head(self) -> CodePoint:
        return self[0]

    def codepoints(self) -> Iterator[CodePoint]:
        return self.__iter__()

    def __repr__(self) -> str:
        return ' '.join(repr(cp) for cp in self)

    def __str__(self) -> str:
        return ''.join(chr(cp) for cp in self)


# --------------------------------------------------------------------------------------

CodePoint.MIN = CodePoint(0)
CodePoint.MAX = CodePoint(0x10_FFFF)

CodePoint.SPACE = CodePoint(0x0020)
CodePoint.DELETE = CodePoint(0x007F)
CodePoint.PAD = CodePoint(0x0080)
CodePoint.NO_BREAK_SPACE = CodePoint(0x00A0)
CodePoint.SOFT_HYPHEN = CodePoint(0x00AD)
CodePoint.HANGUL_JUNGSEONG_FILLER = CodePoint(0x1160)
CodePoint.HANGUL_JONGSEONG_SSANGNIEUN = CodePoint(0x11FF)
CodePoint.ZERO_WIDTH_JOINER = CodePoint(0x200D)
CodePoint.COMBINING_ENCLOSING_KEYCAP = CodePoint(0x20E3)
CodePoint.FULL_BLOCK = CodePoint(0x2588)
CodePoint.LEFTWARDS_BLACK_ARROW = CodePoint(0x2B05)
CodePoint.RIGHTWARDS_BLACK_ARROW = CodePoint(0x2B95)
CodePoint.VARIATION_SELECTOR_1 = CodePoint(0xFE00)
CodePoint.VARIATION_SELECTOR_2 = CodePoint(0xFE01)
CodePoint.TEXT_VARIATION_SELECTOR = CodePoint(0xFE0E)
CodePoint.EMOJI_VARIATION_SELECTOR = CodePoint(0xFE0F)
CodePoint.REPLACEMENT_CHARACTER = CodePoint(0xFFFD)
CodePoint.REGIONAL_INDICATOR_SYMBOL_LETTER_A = CodePoint(0x1F1E6)
CodePoint.REGIONAL_INDICATOR_SYMBOL_LETTER_Z = CodePoint(0x1F1FF)

CodePointRange.ALL = CodePointRange(CodePoint.MIN, CodePoint.MAX)


CodePoints: TypeAlias = CodePoint | CodePointRange | CodePointSequence
CodePointOrRange: TypeAlias = CodePoint | CodePointRange
CodePointOrSequence: TypeAlias = CodePoint | CodePointSequence
