"""
Generate Python code based on Unicode UCD data.

Thanks to the [Unicode stability
policy](https://www.unicode.org/policies/stability_policy.html), we can
generally assume that obsolete property values won't be deleted. That implies
that the most recent version is the best version to base code generation on,
since it includes all values from past as well as recent Unicode versions.

Alas, Unicode 6.0 included Indic_Syllabic_Category as a provisional property
only, which is not subject to the stability policy. Then Unicode 7.0 replaced
the Consonant_Repha value with Consonant_Preceding_Repha and
Consonant_Succeeding_Repha. To still be able to ingest the provisional
Indic_Syllabic_Category from Unicode 6.0, we manually patch the provisional
value back in.

Since tests are specific to a version of an algorithm, we do not use the most
recent version for generating Python code from test data. Instead, we do so for
a locked version.
"""

from collections.abc import Iterator
from collections import defaultdict
from pathlib import Path
import re

from .mirror import mirror_unicode_data, retrieve_latest_ucd_version
from .model import ComplexProperty, Version
from .parser import ingest


def generate_code(root: Path) -> None:
    # Define properties and their values based on the most recent version.
    # Thanks to Unicode's stability policy, it is the most comprehensive.
    property_values = retrieve_property_values(root, retrieve_latest_ucd_version(root))
    with open('demicode/_property.py', mode='w', encoding='utf8') as file:
        for line in generate_property_values(property_values):
            print(line, file=file)

    # Algorithms can and do change. So tests always are version-specific.
    # For now, we test grapheme breaks for 15.0 only. That should change.
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

    # Patch provisional property value Consonant_Repha back in.
    values = result[ComplexProperty.Indic_Syllabic_Category.value]
    values.append(('Consonant_Repha', 'Consonant_Repha'))
    values.sort()

    return result


def generate_property_values(
    property_values: dict[str, list[tuple[str, str]]]
) -> Iterator[str]:
    yield '# This module is machine-generated. Do not edit by hand.'
    yield ''
    yield 'from enum import IntEnum, StrEnum'
    yield ''
    yield ''

    properties = [p for p in ComplexProperty if not p.is_manually_generated()]

    yield '__all__ = ('
    for property in properties:
        yield f'    "{property.name.replace("_", "")}",'
    yield ')'

    for property in properties:
        yield ''
        yield ''
        ccc = property is ComplexProperty.Canonical_Combining_Class
        parent = 'IntEnum' if ccc else 'StrEnum'
        yield f'class {property.name.replace("_", "")}({parent}):'
        for name, short_name in property_values[property.value]:
            value = str(short_name) if ccc else f'"{short_name}"'
            yield f'    {name} = {value}'


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
