"""
Demicode's command line tool.
"""

import argparse
from collections.abc import Iterable, Sequence
import itertools
import logging
from pathlib import Path
import re
from textwrap import dedent
import traceback

from .codepoint import CodePoint, CodePointSequence
from .darkmode import is_darkmode
from .display import (
    add_presentation,
    format_grid_lines,
    format_legend,
    format_lines,
    page_lines,
)
from .model import BinaryProperty
from .render import Mode, Renderer, StyledRenderer
from .selection import *
from .ucd import local_cache_directory, UCD
from demicode import __version__


HEX_CODEPOINTS = re.compile(
    r"""
        (?: U[+] )?  [0-9A-Fa-f]{4,6}
        (?:
            \s+  (?: U[+] )?  [0-9A-Fa-f]{4,6}
        )*
    """,
    re.VERBOSE
)


def width_limited_formatter(prog: str) -> argparse.HelpFormatter:
    return argparse.RawTextHelpFormatter(prog, width=70)


def configure_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='demicode',
        description="""        "It's not just Unicode, it's hemi-semi-demicode!\"""",
        epilog=dedent("""
            Demicode's output is paged. Press <return> to advance to the next
            page. If you enter "q" or "quit" before the <return>, demicode
            terminates immediately. It does the same if you press <control-c>.

            If available, Demicode's grapheme-per-line mode shows the name of a
            code point or emoji sequence. NAMES IN ALL-CAPS denote code points,
            are from the UCD, and are immutable. names in lower-case (mostly)
            denote emoji sequences, originate from the CLDR, and may change over
            time. Age shows the Unicode version that first assigned a code point
            or when prefixed with E the Unicode Emoji version that first defined
            a sequence.

            Demicode requires Python 3.11 or later and a terminal that supports
            Ansi escape codes including 256 colors. Demicode is © 2023 Robert
            Grimm, licensed as open source under Apache 2.0.

                      <https://github.com/apparebit/demicode>
        """),
        formatter_class=width_limited_formatter,
    )

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~

    ucd_group = parser.add_argument_group('configure UCD')
    ucd_group.add_argument(
        '--ucd-path',
        help='use path for local UCD mirror instead of OS\n'
        'application cache directory',
    )
    ucd_group.add_argument(
        '--ucd-cwd',
        action='store_true',
        help='use "./ucd" as local UCD mirror instead of\n'
        'OS application cache directory',
    )
    ucd_group.add_argument(
        '--ucd-version',
        help='set UCD version from 4.1 onwards',
    )
    ucd_group.add_argument(
        '--ucd-validation',
        action='store_true',
        help='perform extra validation on UCD',
    )

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~

    cp_group = parser.add_argument_group('select code points')
    cp_group.add_argument(
        '--with-ucd-dashes',
        action='store_true',
        help='include codepoints with Unicode\'s Dash property',
    )
    cp_group.add_argument(
        '--with-ucd-emoji-variation',
        action='store_true',
        help='include all codepoints that have text and\nemoji variations'
    )
    cp_group.add_argument(
        '--with-ucd-keycaps',
        action='store_true',
        help='include codepoints that combine with U+20E3\ninto enclosing keycaps'
    )
    cp_group.add_argument(
        '--with-arrows',
        action='store_true',
        help='include codepoints for matching regular\nand long arrows',
    )
    cp_group.add_argument(
        '--with-lingchi',
        action='store_true',
        help='include several highlights for incoherent\nand inconsistent widths'
    )
    cp_group.add_argument(
        '--with-mad-dash',
        action='store_true',
        help ='include indistinguishable dashes'
    )
    cp_group.add_argument(
        '--with-taste-of-emoji',
        action='store_true',
        help ='include representative sample of emoji'
    )
    cp_group.add_argument(
        '--with-version-oracle',
        action='store_true',
        help='include emoji that date supported Unicode version'
    )
    cp_group.add_argument(
        '--with-curation',
        action='store_true',
        help='include curated selection of codepoints'
    )
    cp_group.add_argument(
        'graphemes',
        nargs='*',
        help=dedent("""\
            include graphemes provided as space-
            separated hex numbers of 4-6 digits, optionall
            prefixed with "U+" or as literal character strings
        """)
    )

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~

    out_group = parser.add_argument_group('control output')
    out_group.add_argument(
        '--in-grid', '-g',
        action='store_true',
        help='display as grid without further UCD information'
    )
    out_group.add_argument(
        '--in-dark-mode', '-d',
        default=None,
        action='store_true',
        help='use colors suitable for dark mode'
    )
    out_group.add_argument(
        '--in-light-mode', '-l',
        action='store_false',
        dest='in_dark_mode',
        help='use colors suitable for light mode',
    )
    out_group.add_argument(
        '--in-more-color', '-c',
        default=0,
        action='count',
        help='use brighter colors in output;\nmay be repeated once'
    )
    out_group.add_argument(
        '--in-plain-text', '-p',
        action='store_true',
        help='display plain text without ANSI escape codes'
    )
    out_group.add_argument(
        '--in-verbose', '-v',
        action='store_true',
        help='use verbose mode to enable instructive logging',
    )

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~

    about_group = parser.add_argument_group('about this tool')
    about_group.add_argument(
        '--stats',
        action='store_true',
        help='display summary statistics and exit'
    )
    about_group.add_argument(
        '--version',
        action='store_true',
        help='display the package version and exit'
    )

    return parser


# --------------------------------------------------------------------------------------


def run(arguments: Sequence[str]) -> int:
    # -------------------------- Parse the options and prepare console renderer
    parser = configure_parser()
    options = parser.parse_args(arguments[1:])

    logging.basicConfig(
        format='[%(levelname)s] %(name)s: %(message)s',
        level=logging.INFO if options.in_verbose else logging.WARNING,
    )

    if options.in_dark_mode is None:
        options.in_dark_mode = is_darkmode()

    new_renderer = Renderer if options.in_plain_text else StyledRenderer
    renderer = new_renderer(
        Mode.DARK if options.in_dark_mode else Mode.LIGHT,
        options.in_more_color
    )

    try:
        return process(options, renderer)
    except Exception as x:
        print(renderer.error(f'Error: {str(x)}'))
        if options.in_verbose:
            print('\n'.join(traceback.format_exception(x)))
        return 1


def process(options: argparse.Namespace, renderer: Renderer) -> int:
    # ---------------------------------------------- Set UCD path and/or version
    if options.ucd_path and options.ucd_cwd:
        raise ValueError(
            "can't use both path and current working directory as local UCD mirror")

    if options.ucd_path:
        UCD.use_path(Path(options.ucd_path))
    if options.ucd_cwd:
        UCD.use_path(Path.cwd() / 'ucd')
    if options.ucd_version:
        UCD.use_version(options.ucd_version)

    # ------------------------------------------------ Handle version and stats
    if options.version:
        print(renderer.very_strong(f' demicode {__version__} '))
        return 0

    # So UCD access logs don't separate heading from counts
    UCD.prepare(validate=options.ucd_validation)

    if options.stats:
        print()
        print(renderer.strong('Code Points with Given Property'))
        print()
        for property in BinaryProperty:
            print(f'    {property.name:<25} : {UCD.count_property(property):5,d}')
        print()
        return 0

    # ---------------------------------------- Determine code points to display
    codepoints: list[Iterable[CodePoint|CodePointSequence|str]] = []
    # Standard selections
    if options.with_ucd_dashes:
        codepoints.append(sorted(UCD.dashes))
    if options.with_ucd_emoji_variation:
        codepoints.append(sorted(UCD.with_emoji_variation))
    if options.with_ucd_keycaps:
        codepoints.append(sorted(UCD.with_keycap))

    # Non-standard selections
    if options.with_arrows:
        codepoints.append(ARROWS)
    if options.with_lingchi:
        codepoints.append(LINGCHI)
    if options.with_mad_dash:
        codepoints.append(MAD_DASH)
    if options.with_taste_of_emoji:
        codepoints.append(TASTE_OF_EMOJI)
    if options.with_version_oracle:
        codepoints.append(VERSION_ORACLE)
    if options.with_curation:
        codepoints.append(MAD_DASH)
        codepoints.append(TASTE_OF_EMOJI)
        codepoints.append(LINGCHI)
        codepoints.append(VERSION_ORACLE)

    for argument in options.graphemes:
        if HEX_CODEPOINTS.match(argument):
            cluster = CodePointSequence.of(*argument.split())
        else:
            cluster = CodePointSequence.from_string(argument)

        if not UCD.is_grapheme_cluster(cluster):
            raise ValueError(f'{cluster!r} is more than one grapheme cluster!')
        codepoints.append(
            [cluster.to_singleton() if cluster.is_singleton() else cluster])

    # -------------------------------- If there's nothing to display, help user
    if len(codepoints) == 0:
        raise ValueError(dedent("""\
            There are no codepoints to show.
            Maybe try again with "1F49D" as argument——
            or with "-h" to see all options.
        """))

    # ----------------------------------------------------- Display code points
    if options.in_grid:
        page_lines(
            renderer,
            None,
            format_grid_lines(
                renderer,
                add_presentation(
                    itertools.chain.from_iterable(codepoints),
                    headings=False
                ),
            ),
        )
    else:
        page_lines(
            renderer,
            format_legend(renderer),
            format_lines(
                renderer,
                add_presentation(itertools.chain.from_iterable(codepoints)),
            ),
        )

    # -------------------------------------------------------------------- Done
    return 0
