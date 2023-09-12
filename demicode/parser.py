from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import Callable, cast, Literal, TypeAlias, TypeVar

from .codepoint import (
    CodePoint,
    CodePointOrSequence,
    CodePointRange,
    CodePoints,
    CodePointSequence,
)


T = TypeVar('T')
P = TypeVar('P')
Tag: TypeAlias = None | Literal['default']
Properties: TypeAlias = tuple[str, ...]


def _parse_line(
    line: str,
    *,
    with_codepoints: bool = True,   # convert first field to code points
    with_comment: bool = False,     # include comment as final field
) -> tuple[CodePoints, Properties]:
    """
    Parse a UCD file line. `with_codepoints`, which defaults to `True`, converts
    the first field to a code point, range, or sequence. `with_comment`, which
    defaults to `False`, includes the comment as the final field.
    """
    line, _, comment = line.partition('#')
    properties = [f.strip() for f in line.strip().split(';')]
    if with_comment:
        properties.append(comment.strip())
    if not with_codepoints:
        return CodePoint.MIN, tuple(properties)

    codepoints, *properties = properties
    first_codepoint, *more_codepoints = codepoints.split()

    if len(more_codepoints) == 0:
        start, _, stop = first_codepoint.partition('..')
        if stop:
            return CodePointRange.of(start, stop), tuple(properties)
        else:
            return CodePoint.of(start), tuple(properties)

    sequence = CodePointSequence.of(first_codepoint, *more_codepoints)
    return sequence, tuple(properties)


_EOF = '# EOF'
_MISSING = '# @missing:'

def parse_lines(
    lines: Iterable[str],
    *,
    with_codepoints: bool = True,
    with_comment: bool = False,
) -> Iterator[tuple[Tag, CodePoints, Properties]]:
    """
    Parse the lines of a UCD file into structured records. This function
    processes all lines of a UCD file including comments. It parses comments
    marked as `@missing`, setting the tag to `"default"` while leaving it `None`
    for regular lines. When `with_codepoints` is enabled, which is the default,
    it parses the first field as a code point, code point range, or code point
    sequence. When `with_comment` is enabled, it parses the comment as the final
    field. It does not process fields beyond stripping leading and trailing
    white space. As a result, empty fields have empty strings as values.
    """
    for line in lines:
        if line in ('', '\n'):
            continue
        elif line.startswith(_EOF):
            return
        elif line.startswith(_MISSING):
            yield  'default', *_parse_line(
                line[len(_MISSING):].strip(),
                with_codepoints=with_codepoints,
                with_comment=with_comment,
            )
        elif line[0] == '#':
            continue
        else:
            yield None, *_parse_line(
                line,
                with_codepoints=with_codepoints,
                with_comment=with_comment,
            )


def parse(
    lines: Iterable[str],
    constructor: Callable[[CodePoints, Properties], None | T],
    *,
    with_codepoints: bool = True,
    with_comment: bool = False,
) -> Iterator[T]:
    """
    Parse the lines of a UCD file into application-specific records. This
    function uses `parse_lines()` to parse lines into generic tuples, ignores
    default values, converts tuples to application-specific records, and yields
    the non-`None` results.
    """
    for tag, codepoints, properties in parse_lines(
        lines,
        with_codepoints=with_codepoints,
        with_comment=with_comment,
    ):
        if tag is None:
            record = constructor(codepoints, properties)
            if record is not None:
                yield record


# --------------------------------------------------------------------------------------
# Helpful Callbacks (for parse(), sorted(), ...)


def to_range_and_string(
    codepoints: CodePoints,
    properties: Properties
) -> tuple[CodePointRange, str]:
    """Normalize a parsed record to a code point range and single string."""
    return codepoints.to_range(), properties[0]


def no_range(codepoints: CodePoints) -> CodePointOrSequence:
    """
    Return the least complex representation for the input while also rejecting
    any code point ranges.
    """
    if codepoints.is_singleton():
        return codepoints.to_singleton()
    if isinstance(codepoints, CodePointSequence):
        return codepoints
    raise TypeError(f'code point range {codepoints!r} where none expected')


def get_range(record: tuple[CodePointRange, T]) -> CodePointRange:
    """Retrieve the range from a parsed record"""
    return record[0]


# --------------------------------------------------------------------------------------
# Optimization of Range Records


def simplify_range_data(
    data: Iterable[tuple[CodePointRange, P]]
) -> Iterator[tuple[CodePointRange, P]]:
    """Simplify records by combining adjacent ranges with equal properties."""
    range_accumulator: None | CodePointRange = None
    props_accumulator: None | P = None

    for range, props in data:
        if range_accumulator is not None:
            if range_accumulator.can_merge(range) and props_accumulator == props:
                range_accumulator = range_accumulator.merge(range)
                continue
            yield range_accumulator, cast(P, props_accumulator)

        range_accumulator = range
        props_accumulator = props

    if range_accumulator is not None:
        yield range_accumulator, cast(P, props_accumulator)


def simplify_only_ranges(data: Iterable[CodePointRange]) -> list[CodePointRange]:
    """Combine adjacent ranges."""
    return [r for r, _ in simplify_range_data((r, None) for r in data)]
