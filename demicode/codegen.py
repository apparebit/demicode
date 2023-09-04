from collections.abc import Iterator
from collections import defaultdict
from pathlib import Path
import re

from .mirror import mirror_unicode_data
from .model import ComplexProperty, Version
from .parser import ingest


def generate_code(root: Path, version: Version) -> None:
    property_values = retrieve_property_values(root, version)
    with open('demicode/_property.py', mode='w', encoding='utf8') as file:
        for line in generate_property_values(property_values):
            print(line, file=file)

    with open('test/grapheme_clusters.py', mode='w', encoding='utf8') as file:
        for line in generate_grapheme_clusters(root, version):
            print(line, file=file)


def retrieve_property_values(
    path: Path, version: Version
) -> dict[str, list[tuple[str, str]]]:
    path = mirror_unicode_data(path, 'PropertyValueAliases.txt', version)
    _, data = ingest(path, lambda _, p: p, with_codepoints=False)

    properties_of_interest = set()
    for complex_property in ComplexProperty:
        if complex_property is not ComplexProperty.Grapheme_Cluster_Break:
            properties_of_interest.add(complex_property.value)

    result = defaultdict(list)
    for property, short_name, name, *_ in data:
        if property not in properties_of_interest:
            continue
        result[property].append((name, short_name))
    return result


def generate_property_values(
    property_values: dict[str, list[tuple[str, str]]]
) -> Iterator[str]:
    yield '# This module is machine-generated. Do not edit by hand.'
    yield ''
    yield 'from enum import StrEnum'
    yield ''
    yield ''

    yield '__all__ = ('
    for property in ComplexProperty:
        if property is not ComplexProperty.Grapheme_Cluster_Break:
            yield f'    "{property.name.replace("_", "")}",'
    yield ')'
    yield ''
    yield ''

    for property in ComplexProperty:
        if property is not ComplexProperty.Grapheme_Cluster_Break:
            yield f'class {property.name.replace("_", "")}(StrEnum):'
            for name, short_name in property_values[property.value]:
                yield f'    {name} = "{short_name}"'
            yield ''
            yield ''


MARK = re.compile(r'[÷×]')

def generate_grapheme_clusters(root: Path, version: Version) -> Iterator[str]:
    # Convert into dictionary entries, ready for testing.
    # https://www.unicode.org/Public/UCD/latest/ucd/auxiliary/GraphemeBreakTest.txt
    path = mirror_unicode_data(root, 'GraphemeBreakTest.txt', version)

    yield '# This module is machine-generated. Do not edit by hand.'
    yield ''
    yield ''
    yield 'GRAPHEME_CLUSTERS = {'

    with open(path, mode='r', encoding='utf8') as file:
        for line in file:
            if line.startswith('#'):
                continue
            spec, _, _ = line.partition('#')
            spec = spec.strip().replace(' ', '')

            codepoints = ', '.join(f'0x{cp}' for cp in MARK.split(spec) if cp)
            marks = ', '.join(
                str(idx) for idx, mark in enumerate(MARK.findall(spec)) if mark == '÷')

            yield f'    ({codepoints}): ({marks}),'

    yield '}'
    yield ''
    yield ''
