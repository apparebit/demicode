import sys

from .ansi import Ansi

if sys.version_info < (3, 11, 0):
    version = '.'.join(str(v) for v in sys.version_info[:3])
    print(f'{Ansi.ERROR}Error: You are trying to run demicode with Python {version},')
    print(f'but demicode requires at least Python 3.11.0 or later')
    print(f'Please try again after upgrading your Python installation.{Ansi.RESET}')
    sys.exit(1)

import argparse
from collections.abc import Iterable, Sequence
import itertools
import os
import re
import sys
from textwrap import dedent

from .codepoint import CodePoint
from .ucd import UCD
from .display import page_lines, format_grid_lines, format_legend, format_lines
from demicode import __version__


HEX_CODEPOINT = re.compile(r'(U[+])?[0-9A-Fa-f]{4,6}')


def width_limited_formatter(prog: str) -> argparse.HelpFormatter:
    return argparse.RawTextHelpFormatter(prog, width=70)


def configure_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='demicode',
        description='        "Unicode is boring without hemi-semi-demicode!"',
        epilog=dedent("""
            Demicode's output is paged. Press <return> to advance to the next
            page. If you enter "q" or "quit" before the <return>, demicode
            terminates immediately. It does the same if you press <control-c>.

            Demicode requires a terminal emulator that supports Ansi escape
            codes including 256 colors. Demicode is © 2023 Robert Grimm,
            licensed as open source under Apache 2.0.

                      <https://github.com/apparebit/demicode>
        """),
        formatter_class=width_limited_formatter,
    )
    parser.add_argument(
        '--with-keycap',
        action='store_true',
        help='include codepoints that combine with U+20E3\nfor keycaps.'
    )
    parser.add_argument(
        '--with-selection',
        action='store_true',
        help='include curated selection of codepoints.'
    )
    parser.add_argument(
        '--with-variation',
        action='store_true',
        help='include all codepoints that have text and\nemoji variations.'
    )
    parser.add_argument(
        'codepoints',
        nargs='*',
        help="""include codepoints provided as space-
separated hex numbers (4-6 digits, optionally
prefixed with "U+") or as literal characters
without intermediate spaces."""
    )
    parser.add_argument(
        '--as-grid',
        action='store_true',
        help='display as grid without further UCD information.'
    )
    parser.add_argument(
        '--bright', '-b',
        default=0,
        action='count',
        help='increase the color brightness of the output;\nmay be used more than once.'
    )
    parser.add_argument(
        '--version',
        action='store_true',
        help='display the package version and exit.'
    )
    return parser


def main(arguments: Sequence[str]) -> int:
    # Parse the options and handle version display (against pink background).
    parser = configure_parser()
    options = parser.parse_args(arguments[1:])

    if options.version:
        print(f'{Ansi.SGR("48;5;218;1")} demicode {__version__} {Ansi.Style.RESET}')
        return 0

    # Determine terminal's display settings.
    width, height = os.get_terminal_size()
    height -= 1
    brightness = options.bright

    # Determine code points to display.
    codepoints: list[Iterable[CodePoint]] = []
    if options.with_keycap:
        codepoints.append(UCD.with_keycap)
    if options.with_selection:
        codepoints.append(UCD.with_selection)
    if options.with_variation:
        codepoints.append(UCD.with_variation)
    if options.codepoints:
        # Both hexadecimal numbers and characters are recognized.
        for argument in options.codepoints:
            if HEX_CODEPOINT.match(argument):
                codepoints.append([CodePoint.of(argument)])
            else:
                codepoints.append(CodePoint.of(ch) for ch in argument)

    # If there's nothing to display, provide some hints.
    if len(codepoints) == 0:
        print(f'{Ansi.ERROR}Error: There are no codepoints to show.')
        print(f'Maybe try again with "1F49D" as argument——')
        print(f'or with "-h" to see all options.{Ansi.RESET}')
        return 1

    # Display the code points.
    if options.as_grid:
        page_lines(
            height,
            None,
            format_grid_lines(
                brightness,
                width,
                itertools.chain.from_iterable(codepoints)
            )
        )
    else:
        page_lines(
            height,
            format_legend(width),
            format_lines(
                brightness,
                width,
                itertools.chain.from_iterable(codepoints)
            )
        )

    # Done.
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
