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
from textwrap import dedent

from .mirror import mirrored_data, retrieve_latest_ucd_version
from .model import Property, Version
from .parser import parse


def generate_code(root: Path) -> None:
    # Define properties and their values based on the most recent version.
    # Thanks to Unicode's stability policy, it is the most comprehensive.
    property_values = retrieve_property_values(root, retrieve_latest_ucd_version(root))
    with open('demicode/_property.py', mode='w', encoding='utf8') as file:
        for line in generate_property_values(property_values):
            print(line, file=file)

    # Algorithms can and do change. So tests always are version-specific.
    # For now, we test grapheme breaks for 15.0 only. That should change.
    v15_0 = Version(15, 0, 0)
    v15_1 = Version(15, 1, 0)

    with open('test/grapheme_clusters.py', mode='w', encoding='utf8') as file:
        print('# This module is machine-generated. Do not edit by hand.\n', file=file)
        with mirrored_data('GraphemeBreakTest.txt', v15_0, root) as lines:
            for line in grapheme_cluster_breaks(lines, v15_0):
                print(line, file=file)

        print('\n', file=file)
        with mirrored_data('GraphemeBreakTest.txt', v15_1, root) as lines:
            for line in grapheme_cluster_breaks(lines, v15_1):
                print(line, file=file)
        print(dedent("""

            GRAPHEME_CLUSTER_BREAKS = {
                '15.0': _GRAPHEME_CLUSTER_BREAKS_15_0,
                '15.1': _GRAPHEME_CLUSTER_BREAKS_15_1,
            }
        """), file=file)

# --------------------------------------------------------------------------------------
# Property Values


def retrieve_property_values(
    root: Path, version: Version
) -> dict[str, list[tuple[str, str]]]:
    properties_of_interest = set()
    for complex_property in Property:
        if not complex_property.is_manually_generated():
            properties_of_interest.add(complex_property.value)

    result = defaultdict(list)
    with mirrored_data('PropertyValueAliases.txt', version, root) as lines:
        records = parse(lines, lambda _, p: p, with_codepoints=False)
        for property, short_name, name, *_ in records:
            if property not in properties_of_interest:
                continue
            result[property].append((name, short_name))

    # Patch provisional property value Consonant_Repha back in.
    values = result[Property.Indic_Syllabic_Category.value]
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

    properties = [p for p in Property if not p.is_manually_generated()]

    yield '__all__ = ('
    for property in properties:
        yield f'    "{property.name.replace("_", "")}",'
    yield ')'

    for property in properties:
        yield ''
        yield ''
        ccc = property is Property.Canonical_Combining_Class
        parent = 'IntEnum' if ccc else 'StrEnum'
        yield f'class {property.name.replace("_", "")}({parent}):'
        for name, short_name in property_values[property.value]:
            value = str(short_name) if ccc else f'"{short_name}"'
            yield f'    {"None_" if name == "None" else name} = {value}'


# --------------------------------------------------------------------------------------
# Grapheme Cluster Breaks


MARK = re.compile(r'[÷×]')

def grapheme_cluster_breaks(lines: Iterator[str], version: Version) -> Iterator[str]:
    # Convert into dictionary entries, ready for testing.
    # https://www.unicode.org/Public/UCD/latest/ucd/auxiliary/GraphemeBreakTest.txt
    yield f'_GRAPHEME_CLUSTER_BREAKS_{version.major}_{version.minor} = {{'

    for spec in parse(lines, lambda _, p: p[0].replace(' ', ''), with_codepoints=False):
        codepoints = ', '.join(f'0x{cp}' for cp in MARK.split(spec) if cp)
        breaks = ', '.join(
            str(idx) for idx, mark in enumerate(MARK.findall(spec)) if mark == '÷'
        )
        yield f'    ({codepoints}): ({breaks}),'

    yield '}'
