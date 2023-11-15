"""
Demicode's command line tool.
"""

import argparse
from collections.abc import Iterable, Sequence
from contextlib import AbstractContextManager
import itertools
import logging
import re
import sys
from textwrap import dedent
import traceback
from types import TracebackType
from typing import Callable

from .benchmark import Probe, report_page_rendering
from .db.codegen import generate_code
from .db.codepoint import CodePoint, CodePointSequence
from .db.ucd import UnicodeCharacterDatabase
from .db.version import VersionError
from .display import display
from .selection import *
from .statistics import collect_statistics, show_mirrored_versions, show_statistics
from .ui.control import read_key_action, read_line_action
from .ui.render import KeyPressReader, Renderer, Style
from .ui.termio import TermIO
from . import __version__


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


class user_error(AbstractContextManager['user_error']):
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
    if sys.__stdout__.isatty():
        a: Callable[[str], str] = lambda text: Style.link(text)
        b: Callable[[str], str] = Style.bold
        i: Callable[[str], str] = Style.italic
    else:
        a = lambda text: text
        b = lambda text: text
        i = lambda text: text

    tagline = i("It's not just Unicode, it's hemi-semi-demicode!")
    parser = argparse.ArgumentParser(
        prog='demicode',
        description=f"""        "{tagline}\"""",
        epilog=dedent(f"""
            Demicode pages its output and, after rendering a page, waits for
            your {b("your keyboard input")} to determine what to do next. On Linux
            and macOS, use the left and right cursor keys to go backward and
            forward one page. Use <escape>, <q>, or <x> to terminate demicode
            instead. On all other operating systems, enter a command and then
            confirm it with <return>:

              - `b`, `back`, `backward`, `p`, and `previous` page backward.
              - ``, `f`, `forward`, `n`, and `next` page forward.
              - `q`, `quit`, `x`, and `exit` terminate demicode.

            Linux and macOS recognize the single letter commands as well.

            If available, Demicode's grapheme-per-line mode shows the {b("name")} of
            a a code point or emoji sequence. NAMES IN ALL-CAPS denote code
            points, are from the UCD, and are immutable. In contrast, names in
            lower- case (mostly) denote emoji sequences, originate from the
            CLDR, and may change over time. The {b("age")} is the Unicode version
            that first assigned a code point or, when prefixed with E, the
            Unicode Emoji version that first defined a sequence.

            Demicode requires {b("Python 3.11 or later")} and a terminal that supports
            {b("ANSI escape codes")} including 256 colors. Demicode is © 2023 Robert
            Grimm, licensed as open source under Apache 2.0.

                      <{a("https://github.com/apparebit/demicode")}>
             ​
        """),
        formatter_class=width_limited_formatter,
    )

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~

    ucd_group = parser.add_argument_group(b('configure UCD'))
    ucd_group.add_argument(
        '--ucd-path',
        help='use path for local UCD mirror instead of the\n'
        'designated cache directory',
    )
    ucd_group.add_argument(
        '--ucd-version',
        help='use UCD version >= 4.1 even though the default,\n'
        'i.e., latest, version yields best results'
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
    ucd_group.add_argument(
        '--ucd-mirror-all',
        action='store_true',
        help='eagerly mirror the files for all known UCD versions'
    )
    ucd_group.add_argument(
        '--ucd-list-versions',
        action='store_true',
        help='list UCD versions in mirror directory and exit'
    )

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~

    cp_group = parser.add_argument_group(b('select code points'))
    cp_group.add_argument(
        '--with-ucd-emoji-variation',
        action='store_true',
        help='include all code points that have text and emoji\nvariations'
    )
    cp_group.add_argument(
        '--with-ucd-extended-pictographic', '-x',
        action='store_true',
        help='include extended pictographic code points,\nincluding unassigned ones'
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
        '--with-version-oracle', '-o',
        action='store_true',
        help='include emoji that date supported Unicode version'
    )
    cp_group.add_argument(
        '--with-curation', '-q',
        action='store_true',
        help='include curated selection of code points'
    )
    cp_group.add_argument(
        'graphemes',
        nargs='*',
        help=dedent("""\
            include graphemes provided as space-separated
            hex numbers of 4-6 digits, optionally prefixed
            with "U+", or as literal strings
        """)
    )

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~

    in_group = parser.add_argument_group(b('control input'))
    in_group.add_argument(
        '--use-line-input',
        action='store_true',
        help='fall back onto line input even if raw input is\navailable',
    )

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~

    out_group = parser.add_argument_group(b('control presentation'))
    out_group.add_argument(
        '--incrementally', '-i',
        action='store_true',
        help='display blots incrementally, which is much slower\n'
        'but enables blot size measurement'
    )
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
        dest='in_color_intensity',
        help='use brighter colors in output; may be used twice'
    )
    out_group.add_argument(
        '--in-plain-text', '-p',
        default=None,
        action='store_false',
        dest='in_style',
        help='emit plain text without ANSI escape codes'
    )
    out_group.add_argument(
        '--in-style',
        default=None,
        action='store_true',
        help='style output with ANSI escapes',
    )
    out_group.add_argument(
        '--in-verbose', '-v',
        action='store_true',
        help='use verbose mode to enable instructive logging',
    )

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~

    about_tool_group = parser.add_argument_group(b('about this tool'))
    about_tool_group.add_argument(
        '--inspect-version', '-V',
        action='store_true',
        help='display the tool version and exit'
    )
    about_tool_group.add_argument(
        '--inspect-perf', '-T',
        action="store_true",
        help="determine page rendering latency and exit"
    )
    about_tool_group.add_argument(
        '--inspect-perf-nonce',
        dest='nonce',
        action='store',
        help='nonce that uniquely marks a benchmark run, for use in filenames',
    )
    about_tool_group.add_argument(
        '--inspect-ucd', '-U',
        action='store_true',
        help='display UCD statistics and exit'
    )
    about_tool_group.add_argument(
        '--generate-code',
        action='store_true',
        help='generate Python modules based on Unicode data\nfiles and exit',
    )

    return parser


# --------------------------------------------------------------------------------------


def run(arguments: Sequence[str]) -> int:
    # ---------------------------- Parse the options and prepare console renderer
    parser = configure_parser()
    options = parser.parse_args(arguments[1:])

    logging.basicConfig(
        format='[%(levelname)s] %(name)s: %(message)s',
        level=logging.INFO if options.in_verbose else logging.WARNING,
    )

    termio = TermIO()

    renderer = Renderer.new(
        styled=options.in_style,
        dark=options.in_dark_mode,
        intensity=options.in_color_intensity,
    )

    try:
        return process(options, termio, renderer)
    except UserError as x:
        renderer.newline()
        renderer.emit_error(x.args[0])
        if x.__context__:
            renderer.writeln(f'In particular: {x.__context__.args[0]}')
        return 1
    except Exception as x:
        renderer.newline()
        renderer.emit_error(
            'Demicode encountered an unexpected error. For details, please see the\n'
            'exception trace below. If you can exclude your system as cause, please\n'
            'file an issue at https://github.com/apparebit/demicode/issues.\n'
        )
        renderer.writeln('\n'.join(traceback.format_exception(x)))
        return 1


def process(options: argparse.Namespace, termio: TermIO, renderer: Renderer) -> int:
    # --------------------------------------------------------------- Prepare UCD
    try:
        ucd = UnicodeCharacterDatabase(
            options.ucd_path, options.ucd_version, renderer.tick
        )
    except NotADirectoryError:
        raise UserError(f'"{options.ucd_path}" is not a directory')
    except VersionError:
        raise UserError(f'"{options.ucd_version}" is not a valid UCD version')

    if options.ucd_optimize:
        ucd.optimize()
    if options.ucd_validate:
        ucd.validate()
    if options.ucd_mirror_all:
        ucd.mirror.retrieve_all(renderer.tick)

    renderer.newline()  # Terminate potential line with ticks

    if options.ucd_list_versions:
        show_mirrored_versions(ucd, renderer)
        return 0

    # ------------------------------------------------ Perform tool house keeping
    if options.inspect_version:
        renderer.strong(f' demicode {__version__} ')
        renderer.newline()
        return 0

    if options.inspect_ucd:
        prop_counts = collect_statistics(ucd.mirror.root, ucd.version)
        overlap = ucd.count_break_overlap()
        show_statistics(ucd.version, prop_counts, overlap, renderer)
        return 0

    if options.generate_code:
        assert ucd.version is not None
        generate_code(ucd.mirror)
        return 0

    # ------------------------------------------ Determine code points to display
    codepoints: list[Iterable[CodePoint|CodePointSequence|str]] = []
    # Standard selections
    if options.with_ucd_emoji_variation:
        codepoints.append(sorted(ucd.with_emoji_variation))
    if options.with_ucd_extended_pictographic:
        codepoints.append(
            itertools.chain.from_iterable(
                r.codepoints() for r in ucd.extended_pictographic_ranges()
            )
        )
    if options.with_ucd_keycaps:
        codepoints.append(sorted(ucd.with_keycap))

    # Non-standard selections
    if options.with_arrows or options.inspect_latency:
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
    if options.with_curation or options.inspect_latency:
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

        if not ucd.is_grapheme_cluster(cluster):
            raise UserError(f'{cluster!r} is more than one grapheme cluster!')
        codepoints.append(
            [cluster.to_singleton() if cluster.is_singleton() else cluster])

    # --------------------------------------- Make sure there is enough to display
    if len(codepoints) == 0:
        raise UserError(dedent("""\
            There are no code points to show.
            Maybe try again with "1F49D" as argument——
            or with "-h" to see all options.
        """))

    if options.inspect_latency:
        codepoints.extend(codepoints)
        codepoints.extend(codepoints)

    # ------------------------------------------------------- Display code points
    if options.inspect_latency:
        incrementally = False
        in_grid = False
        probe = Probe(termio)
        read_action = probe.get_page_action
    else:
        incrementally = options.incrementally
        in_grid = options.in_grid
        probe = None
        read_action = (
            read_key_action
            if KeyPressReader.PLATFORM_SUPPORTED and not options.use_line_input
            else read_line_action
        )

    for _ in range(2):
        display(
            itertools.chain.from_iterable(codepoints),
            renderer,
            ucd,
            incrementally=incrementally,
            in_grid=in_grid,
            probe=probe,
            read_action=read_action,
        )

        if probe is None:
            break
        incrementally = True

    if probe:
        report_page_rendering(probe, options.nonce)

    # ---------------------------------------------------------------------- Done
    return 0
