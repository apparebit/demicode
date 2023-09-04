from collections.abc import Iterator
from collections import defaultdict
from pathlib import Path

from .mirror import mirror_unicode_data
from .model import ComplexProperty, Version
from .parser import ingest


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


def generate_property_model(
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
