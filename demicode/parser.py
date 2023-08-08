from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Callable, Literal, TypeAlias, TypeVar

from .codepoint import CodePoint, CodePointRange, CodePointSequence


T = TypeVar('T')
Tag: TypeAlias = None | Literal['default']
CodePoints: TypeAlias = CodePoint | CodePointRange | CodePointSequence
Properties: TypeAlias = tuple[str, ...]


def _parse_record(line: str) -> tuple[CodePoints, Properties]:
    line, _, _ = line.partition('#')
    codepoints, *properties = [f.strip() for f in line.strip().split(';')]
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
    lines: Iterable[str]
) -> Iterator[tuple[Tag, CodePoints, Properties]]:
    for line in lines:
        if line in ('', '\n'):
            continue
        elif line.startswith(_EOF):
            return
        elif line.startswith(_MISSING):
            yield  'default', *_parse_record(line[len(_MISSING):].strip())
        elif line[0] == '#':
            continue
        else:
            yield None, *_parse_record(line)


def collect(
    property_records: Iterable[tuple[Tag, CodePoints, Properties]],
    converter: Callable[[CodePoints, Properties], T],
) -> tuple[list[T], list[T]]:
    defaults: list[T] = []
    records: list[T] = []

    for tag, codepoints, properties in property_records:
        if tag is None:
            records.append(converter(codepoints, properties))
        else:
            defaults.append(converter(codepoints, properties))

    return defaults, records


def ingest(
    path: Path,
    converter: Callable[[CodePoints, Properties], T],
) -> tuple[list[T], list[T]]:
    with open(path, mode='r', encoding='utf8') as handle:
        return collect(parse_records(handle), converter)
