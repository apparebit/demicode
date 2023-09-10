from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import Callable, cast, Literal, TypeAlias, TypeVar

from .codepoint import CodePoint, CodePointRange, CodePointSequence


T = TypeVar('T')
P = TypeVar('P')
Tag: TypeAlias = None | Literal['default']
CodePoints: TypeAlias = CodePoint | CodePointRange | CodePointSequence
Properties: TypeAlias = tuple[str, ...]


def _parse_record(
    line: str,
    *,
    with_codepoints: bool = True,
    with_comment: bool = False,
) -> tuple[CodePoints, Properties]:
    """
    Parse a record from a UCD file. If `with_codepoints` is `False`, the
    returned code points are code point 0 and the first field in the input
    becomes just another property. If `with_comment` is `True`, this function
    includes the value of the comment as the last property.
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

def parse_records(
    lines: Iterable[str],
    *,
    with_codepoints: bool = True,
    with_comment: bool = False,
) -> Iterator[tuple[Tag, CodePoints, Properties]]:
    """
    Parse the lines of a UCD file into structured records. This function returns
    a stream of triples:

      * The tag distinguishes between defaults, `"default"`, and regular
        records, `None`.
      * The code points are the first of the semicolon-separated fields, with
        single code points represented as `CodePoint`.
      * The properties are the remaining fields as a tuple.

    Individual values of properties are stripped of whitespace but otherwise
    remain unprocessed. This implies that empty fields become empty strings.
    """
    for line in lines:
        if line in ('', '\n'):
            continue
        elif line.startswith(_EOF):
            return
        elif line.startswith(_MISSING):
            yield  'default', *_parse_record(
                line[len(_MISSING):].strip(),
                with_codepoints=with_codepoints,
                with_comment=with_comment,
            )
        elif line[0] == '#':
            continue
        else:
            yield None, *_parse_record(
                line,
                with_codepoints=with_codepoints,
                with_comment=with_comment,
            )


def collect(
    property_records: Iterable[tuple[Tag, CodePoints, Properties]],
    intern: Callable[[CodePoints, Properties], T],
) -> tuple[list[T], list[T]]:
    """
    Convert the stream of parsed triples into a list of defaults and regular
    records. To avoid repeated iteration over triples, this function takes a
    converter callback that should convert pair of code points and properties
    into the desired representation.
    """
    defaults: list[T] = []
    records: list[T] = []

    for tag, codepoints, properties in property_records:
        if tag is None:
            records.append(intern(codepoints, properties))
        else:
            defaults.append(intern(codepoints, properties))

    return defaults, records


def ingest(
    path: Path,
    intern: Callable[[CodePoints, Properties], T],
    *,
    with_codepoints: bool = True,
    with_comment: bool = False,
) -> tuple[list[T], list[T]]:
    with open(path, mode='r', encoding='utf8') as handle:
        return collect(
            parse_records(
                handle,
                with_codepoints=with_codepoints,
                with_comment=with_comment,
            ),
            intern,
        )


# --------------------------------------------------------------------------------------
# Helpful Callbacks (for ingest() etc)


def to_range(record: tuple[CodePointRange, T]) -> CodePointRange:
    """Retrieve the range from a parsed record"""
    return record[0]


def to_range_and_string(
    codepoints: CodePoints,
    properties: Properties
) -> tuple[CodePointRange, str]:
    """Normalize a parsed record to a code point range and single string."""
    return codepoints.to_range(), properties[0]


def to_sequence(codepoints: CodePoints) -> CodePoint | CodePointSequence:
    if codepoints.is_singleton():
        return codepoints.to_singleton()
    if isinstance(codepoints, CodePointSequence):
        return codepoints
    raise TypeError(f'code point range {codepoints!r} where none expected')


# --------------------------------------------------------------------------------------
# Extract Default (With Error Checking)


def extract_default(
    defaults: Sequence[tuple[CodePoints, P]],
    fallback: P,
    label: str,
) -> P:
    length = len(defaults)
    if length == 0:
        return fallback
    if length == 1:
        r, p = defaults[0]
        if r == CodePointRange.ALL:
            return p
        raise ValueError(f'Default {label} covers only {r!r}')
    raise ValueError(f'Default {label} comprises {length} entries')


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
            if range_accumulator.can_merge_with(range) and props_accumulator == props:
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
