"""
Demicode's command line tool.
"""

import argparse
from collections.abc import Iterable, Sequence
from contextlib import AbstractContextManager
import itertools
import logging
from pathlib import Path
import re
from textwrap import dedent
import traceback
from types import TracebackType
from typing import cast

from .codegen import generate_code
from .codepoint import CodePoint, CodePointSequence
from .darkmode import is_darkmode
from .display import display
from .model import BinaryProperty, ComplexProperty
from .render import Mode, Renderer, StyledRenderer
from .selection import *
from .ucd import UCD
from demicode import __version__


# The regular expression is more permissive than CodePoint.of()
# to avoid treating such malformed inputs as literal strings.
HEX_CODEPOINTS = re.compile(
    r"""
        (?: U[+] | 0x )?  [0-9A-Fa-f]+
        (?:
            \s+  (?: U[+] | 0x )?  [0-9A-Fa-f]+
        )*
    """,
    re.VERBOSE
)


# --------------------------------------------------------------------------------------


class UserError(Exception):
    """
    An error indicating invalid user input. When code raises this error, it
    probably is *not* helpful to print an exception trace.
    """


class user_error(AbstractContextManager):
    """
    A context manager to turn one or more exceptions into a user error. If the
    context manager tries to exit with one of the listed exception types, it
    instead raises a `UserError` with the message `msg.format(*args, **kwargs)`.
    """

    def __init__(
        self,
        exc_types: type[BaseException] | Sequence[type[BaseException]],
        msg: str,
        *args: object,
        **kwargs: object,
    ) -> None:
        if isinstance(exc_types, type):
            exc_types = (exc_types,)

        self._exc_types = exc_types
        self._msg = msg
        self._args = args
        self._kwargs = kwargs

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        _: TracebackType | None,
    ) -> None:
        if exc_type in self._exc_types:
            msg = self._msg.format(*self._args, **self._kwargs)
            raise UserError(msg) from exc_value


# --------------------------------------------------------------------------------------


def width_limited_formatter(prog: str) -> argparse.HelpFormatter:
    return argparse.RawTextHelpFormatter(prog, width=70)


def configure_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='demicode',
        description="""        "It's not just Unicode, it's hemi-semi-demicode!\"""",
        epilog=dedent("""
            Demicode pages its output and, after displaying a page, waits for
            your input on what to do next. On Linux and macOS, use the left and
            right cursor keys to go backward and forward one page. Use <escape>,
            <q>, or <x> to terminate demicode instead. On all other operating
            systems, enter a command and then confirm it with <return>:

              * "b", "back", "backward", "p", and "previous" go backward one page.
              * "", "f", "forward", "n", and "next" go forward one page.
              * "q", "quit", "x", and "exit" terminate demicode.

            Linux and macOS recognize the single letter commands as well.

            If available, Demicode's grapheme-per-line mode shows the name of a
            code point or emoji sequence. NAMES IN ALL-CAPS denote code points,
            are from the UCD, and are immutable. names in lower-case (mostly)
            denote emoji sequences, originate from the CLDR, and may change over
            time. Age shows the Unicode version that first assigned a code point
            or when prefixed with E the Unicode Emoji version that first defined
            a sequence.

            Demicode requires Python 3.11 or later and a terminal that supports
            ANSI escape codes including 256 colors. Demicode is © 2023 Robert
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
        '--ucd-version',
        help='set UCD version from 4.1 onwards',
    )
    ucd_group.add_argument(
        '--ucd-optimize',
        action=argparse.BooleanOptionalAction,
        default=True,
        help='optimize UCD data (default is to optimize)',
    )
    ucd_group.add_argument(
        '--ucd-validate',
        action='store_true',
        help='validate UCD data',
    )

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~

    cp_group = parser.add_argument_group('select code points')
    cp_group.add_argument(
        '--with-ucd-dashes',
        action='store_true',
        help='include code points with Unicode\'s Dash property',
    )
    cp_group.add_argument(
        '--with-ucd-emoji-variation',
        action='store_true',
        help='include all code points that have text and\nemoji variations'
    )
    cp_group.add_argument(
        '--with-ucd-keycaps',
        action='store_true',
        help='include code points that combine with U+20E3\ninto enclosing keycaps'
    )
    cp_group.add_argument(
        '--with-arrows',
        action='store_true',
        help='include code points for matching regular and\nlong arrows',
    )
    cp_group.add_argument(
        '--with-chevrons',
        action='store_true',
        help='include a sample of code points representing\nrightward-pointing chevrons'
    )
    cp_group.add_argument(
        '--with-lingchi',
        action='store_true',
        help='include several highlights for incoherent and\ninconsistent widths'
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
        help='include curated selection of code points'
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
        help='use brighter colors in output; may be used twice'
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
    about_group.add_argument(
        '--generate-code',
        action='store_true',
        help='generate Python modules based on Unicode\ndata files and exit',
    )

    return parser


# --------------------------------------------------------------------------------------


def show_statistics(renderer: Renderer, is_optimized: bool) -> None:
    qualifier = '(optimized)' if is_optimized else '(not optimized)'
    title = renderer.strong(
        f'Code Points / Ranges with Non-Default Property Values {qualifier}'
    )
    print(f'\n{title}\n')

    def show_heading(text: str) -> None:
        print(renderer.heading(text))
        print()

    total_points = total_ranges = 0

    def show_counts(property: BinaryProperty | ComplexProperty) -> None:
        nonlocal total_points, total_ranges
        points, ranges = cast(tuple[int, int], UCD.count_property_values(property))
        print(f'     {property.name:<28} : {points:7,d} / {ranges:6,d}')
        total_points += points
        total_ranges += ranges

    def show_total() -> None:
        print('    ' + renderer.hint('–' * (1 + 28 + 13 + 6 + 1)))
        print(
            f'     {"Totals":<28} : '
            + f'{total_points:7,d} / {total_ranges:6,d}'
        )
        print('\n')

    show_heading('Binary Emoji Properties:')
    for property in (
        BinaryProperty.Emoji,
        BinaryProperty.Emoji_Component,
        BinaryProperty.Emoji_Modifier,
        BinaryProperty.Emoji_Modifier_Base,
        BinaryProperty.Emoji_Presentation,
        BinaryProperty.Extended_Pictographic,
    ):
        show_counts(property)
    show_total()

    show_heading('Or, Emoji Enumeration:')
    show_counts(ComplexProperty.Emoji_Sequence)
    print('\n')

    show_heading('Also Needed, Complex Properties:')
    total_points = total_ranges = 0
    for property in (
        ComplexProperty.East_Asian_Width,
        ComplexProperty.Grapheme_Cluster_Break,
    ):
        show_counts(property)
    show_total()

    show_heading('Also Needed, Ages and Names:')
    show_counts(ComplexProperty.General_Category)
    print('\n')

    show_heading('Miscellaneous Properties:')
    show_counts(BinaryProperty.Default_Ignorable_Code_Point)
    print('\n')

    q1 = 'no-' if is_optimized else ''
    q2 = 'before' if is_optimized else 'after'
    hint = f'Use --{q1}ucd-optimize to see range counts {q2} optimization'
    print(renderer.hint(hint))
    print()


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
    except UserError as x:
        print(renderer.error(x.args[0]))
        if x.__context__:
            print(f'In particular: {x.__context__.args[0]}')
        return 1
    except Exception as x:
        print(renderer.error(
            'Demicode encountered an unexpected error. For details, please see the\n'
            'exception trace below. If you can exclude your system as cause, please\n'
            'file an issue at https://github.com/apparebit/demicode/issues.\n'
        ))
        print('\n'.join(traceback.format_exception(x)))
        return 1


def process(options: argparse.Namespace, renderer: Renderer) -> int:
    # ------------------------------------------------------------ Handle version
    if options.version:
        print(renderer.very_strong(f' demicode {__version__} '))
        return 0

    # --------------------------------------------------------------- Prepare UCD
    if options.ucd_path:
        with user_error(
            ValueError, '"{}" is not a valid UCD directory', options.ucd_path
        ):
            UCD.use_path(Path(options.ucd_path))
    if options.ucd_version:
        with user_error(
            ValueError, '"{}" is not a valid UCD version ', options.ucd_version
        ):
            UCD.use_version(options.ucd_version)
    UCD.prepare()

    if options.ucd_optimize:
        UCD.optimize()
    if options.ucd_validate:
        UCD.validate()

    # -------------------------------------------------------------- Leverage UCD
    if options.generate_code:
        assert UCD.version is not None
        generate_code(UCD.path)
        return 0

    if options.stats:
        show_statistics(renderer, options.ucd_optimize)
        return 0

    # ----------------------------------------- Determine code points to display
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
    if options.with_chevrons:
        codepoints.append(CHEVRONS)
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
        codepoints.append(CHEVRONS)

    for argument in options.graphemes:
        with user_error(
            ValueError, '"{}" is not a valid code point sequence', argument
        ):
            if HEX_CODEPOINTS.match(argument):
                cluster = CodePointSequence.of(*argument.split())
            else:
                cluster = CodePointSequence.from_string(argument)

        if not UCD.is_grapheme_cluster(cluster):
            raise UserError(f'{cluster!r} is more than one grapheme cluster!')
        codepoints.append(
            [cluster.to_singleton() if cluster.is_singleton() else cluster])

    # -------------------------------- If there's nothing to display, help user
    if len(codepoints) == 0:
        raise UserError(dedent("""\
            There are no code points to show.
            Maybe try again with "1F49D" as argument——
            or with "-h" to see all options.
        """))

    # ----------------------------------------------------- Display code points
    display(
        renderer,
        itertools.chain.from_iterable(codepoints),
        in_grid=options.in_grid
    )

    # -------------------------------------------------------------------- Done
    return 0
