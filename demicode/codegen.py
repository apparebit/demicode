from collections.abc import Iterator
from collections import defaultdict
from pathlib import Path
import re

from .mirror import mirror_unicode_data, retrieve_latest_ucd_version
from .model import ComplexProperty, Version
from .parser import ingest


def generate_code(root: Path) -> None:
    # We assume that obsolete property values won't be deleted (which is the
    # case for grapheme cluster breaking). Hence the most recent version of
    # Unicode is just the right version for enumerations of property values.
    property_values = retrieve_property_values(root, retrieve_latest_ucd_version(root))
    with open('demicode/_property.py', mode='w', encoding='utf8') as file:
        for line in generate_property_values(property_values):
            print(line, file=file)

    # Since algorithms may and do change, testing the results of a particular
    # algorithm is version-specific. Hence specifically targeted versions are
    # just the right versions for testing.
    v150 = Version(15, 0, 0)
    path150 = mirror_unicode_data(root, 'GraphemeBreakTest.txt', v150)

    with open('test/grapheme_clusters.py', mode='w', encoding='utf8') as file:
        print('# This module is machine-generated. Do not edit by hand.\n', file=file)
        for line in generate_grapheme_cluster_breaks(path150, v150):
            print(line, file=file)


# --------------------------------------------------------------------------------------
# Property Values


def retrieve_property_values(
    path: Path, version: Version
) -> dict[str, list[tuple[str, str]]]:
    path = mirror_unicode_data(path, 'PropertyValueAliases.txt', version)
    _, data = ingest(path, lambda _, p: p, with_codepoints=False)

    properties_of_interest = set()
    for complex_property in ComplexProperty:
        if not complex_property.is_manually_generated():
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
        if not property.is_manually_generated():
            yield f'    "{property.name.replace("_", "")}",'
    yield ')'
    yield ''
    yield ''

    for property in ComplexProperty:
        if not property.is_manually_generated():
            yield f'class {property.name.replace("_", "")}(StrEnum):'
            for name, short_name in property_values[property.value]:
                yield f'    {name} = "{short_name}"'
            yield ''
            yield ''


# --------------------------------------------------------------------------------------
# Grapheme Cluster Breaks


MARK = re.compile(r'[÷×]')

def generate_grapheme_cluster_breaks(path: Path, version: Version) -> Iterator[str]:
    # Convert into dictionary entries, ready for testing.
    # https://www.unicode.org/Public/UCD/latest/ucd/auxiliary/GraphemeBreakTest.txt
    yield f'GRAPHEME_CLUSTER_BREAKS_{version.major}_{version.minor} = {{'

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
