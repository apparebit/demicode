from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any, Callable, Literal, TypeAlias, TypeVar

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


def condense_ranges(
    range_data: Iterable[T],
    *,
    decompose: Callable[[T], tuple[CodePointRange, P]] = lambda rp: rp,
    compose: Callable[[CodePointRange, P], T] = lambda r, p: (r, p)
) -> list[T]:
    """
    Maximize ranges and hence minimize items in the given range-based data. The
    default `decompose` and `compose` work for range, value pairs.
    """
    fresh_range_data: list[T] = []
    current_range: None | CodePointRange = None
    current_properties: None | P = None

    for datum in range_data:
        range, properties = decompose(datum)
        if current_range is not None:
            if current_range.can_merge_with(range) and current_properties == properties:
                current_range = current_range.merge(range)
                continue

            fresh_range_data.append(compose(current_range, current_properties))

        current_range = range
        current_properties = properties

    if current_range is not None:
        fresh_range_data.append(compose(current_range, current_properties))
    return fresh_range_data
