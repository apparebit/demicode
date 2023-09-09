"""
Display character blots in the terminal.

This module contains the functionality for formatting demicode's character blots
on screen. Its high-level functions are:

  * `make_presentable()` enriches a stream of Unicode code points, grapheme
    clusters, and headings with their presentation. That has little impact on
    grapheme clusters and headings. But for code points that can be paired with
    a variation selector, the presentation enables just that.
  * `format_lines()` and `format_grid_lines()` turn the presentation-enriched
    stream of code points, graphemes, and headings into a stream of formatted
    lines.
  * `page_lines()` displays a stream of lines, one screen at a time, while also
    handling the user interaction.

The line-level functions are `format_legend()`, `format_heading()`, and
`format_info()`. The legend goes on top of a screen and headings are embedded in
the body. `format_info()` handles code point or grapheme per invocation even if
demicode is building a grid.
"""

from collections.abc import Iterator, Iterable
import itertools
from typing import Callable, cast, Literal, overload, TypeAlias

from .codepoint import CodePoint, CodePointSequence
from .model import GeneralCategory, Presentation
from .render import Padding, Renderer
from .ucd import UCD, Version


CodePoints: TypeAlias = CodePoint | CodePointSequence
HeadingPresentation = tuple[Literal[Presentation.HEADING], str]
CodePointPresentation = tuple[Presentation, CodePoints]


# --------------------------------------------------------------------------------------
# Enrich Code Points with Presentation


@overload
def make_presentable(
    data: Iterable[CodePoints | str], *, headings: Literal[False]
) -> Iterator[CodePointPresentation]: ...

@overload
def make_presentable(
    data: Iterable[CodePoints | str], *, headings: bool = ...
) -> Iterator[HeadingPresentation | CodePointPresentation]: ...

def make_presentable(
    data: Iterable[CodePoints | str],
    *,
    headings: bool = True,  # Allow embedded headings
) -> Iterator[HeadingPresentation | CodePointPresentation]:
    """
    Enrich code points with their presentation.

    If a character that usually is subject to variation selectors is directly
    followed by U+0080, pad, that padding is stripped from the code points and
    the presentation becomes the default `NONE`. In other words, U+0080 disables
    this function's enrichment with presentation for a given code point.
    """
    for datum in data:
        if isinstance(datum, str):
            if not datum:
                continue
            if datum[0] == '\u0001':
                if headings:
                    yield Presentation.HEADING, datum
                continue
            datum = CodePointSequence.from_string(datum)

        if not datum.is_singleton():
            datum = datum.to_sequence()
            if len(datum) == 2 and datum[1] == 0x0080:
                datum = datum[0]
            yield Presentation.NONE, datum
            continue

        datum = datum.to_singleton()
        if datum in UCD.fullwidth_punctuation:
            yield Presentation.CORNER, datum
            yield Presentation.CENTER, datum
        elif datum in UCD.with_emoji_variation:
            yield Presentation.NONE, datum
            yield Presentation.TEXT, datum
            yield Presentation.EMOJI, datum
            if datum in UCD.with_keycap:
                yield Presentation.KEYCAP, datum
        else:
            yield Presentation.NONE, datum


# --------------------------------------------------------------------------------------


LEGEND_BLOT = ' 123   123  '
LEGEND_PROPS = 'Code Pt  VS Ct Wd Other Properties            Age'
LEGEND_NAME = 'Name'
LEGEND = f'{LEGEND_BLOT} {LEGEND_PROPS} {LEGEND_NAME}'

BLOT_WIDTH = len(LEGEND_BLOT)
PROPS_WIDTH = len(LEGEND_PROPS)
AGE_WIDTH = 5
LEGEND_MIN_WIDTH = len(LEGEND)
FIXED_WIDTH = BLOT_WIDTH + 1 + PROPS_WIDTH + 1
NAME_MIN_WIDTH = len(LEGEND_NAME)

def _name_width(width: int) -> int:
    if width <= LEGEND_MIN_WIDTH:
        return NAME_MIN_WIDTH
    return width - FIXED_WIDTH


def format_legend(renderer: Renderer) -> str:
    """Format the per-page legend."""
    if not renderer.has_style:
        return LEGEND[6:]
    return renderer.legend(LEGEND.ljust(renderer.width))


def format_heading(renderer: Renderer, heading: str) -> str:
    """Format the heading without the initial \\u0001 (Start of Heading)."""
    if heading[0] != '\u0001':
        raise ValueError(
            f'string "{heading}" is not a valid heading, which starts with U+0001')

    # Measure length before adding decorative elements.
    heading = heading[1:]
    heading_length = len(heading)

    left = FIXED_WIDTH - 1
    if not renderer.has_style:
        left -= 6
    heading = f'{"─" * left} {heading}'

    right = renderer.width - FIXED_WIDTH - heading_length - 1
    if right < 0:
        heading = renderer.fit(heading, width=renderer.width)
    else:
        heading = f'{heading} {"─" * right}'

    return renderer.heading(heading)


def format_blot(
    renderer: Renderer,
    codepoints: CodePoints,
    *,
    start_column: int = 1,
    presentation: Presentation = Presentation.NONE,
) -> Iterator[str]:
    """Format the fixed-width character blot."""
    # Determine display and width for blot. If the code points are an unassigned
    # singleton or more than one grapheme cluster, their blots are elided.
    presentation, codepoints = presentation.normalize(codepoints)

    if not UCD.is_grapheme_cluster(codepoints):
        display = '···'
        width = 3
    elif codepoints.is_singleton():
        codepoint = codepoints.to_singleton()
        if UCD.category(codepoint) is GeneralCategory.Unassigned:
            display = '···'
            width = 3
        else:
            display = presentation.apply(codepoints.to_singleton())
            width = UCD.width(display)
    else:
        display = str(codepoints)
        width = UCD.width(codepoints)

    # Fail gracefully for control, surrogate, and private use characters.
    if width == -1:
        width = 1
        display = '\uFFFD' # REPLACEMENT CHARACTER

    # Render Character Blots
    yield renderer.column(start_column + 1)
    yield renderer.blot(display, Padding.BACKGROUND, 3 - width)
    yield ' '
    yield renderer.column(start_column + 7)
    yield renderer.blot(display, Padding.FOREGROUND, 3 - width)
    yield ' ' if renderer.has_style else '   '


def format_info(
    renderer: Renderer,
    codepoints: CodePoints,
    *,
    start_column: int = 1,
    presentation: Presentation = Presentation.NONE,
) -> Iterator[str]:
    """Format information about the code points."""
    yield renderer.column(start_column + 13)

    # For code points, if they have implicit presentation, switch to single code
    # point and presentation instead. Otherwise, display the code points, plus
    # age and name for emoji sequences, plus disclaimer for non-grapheme-clusters.
    presentation, codepoints = presentation.normalize(codepoints)
    if not codepoints.is_singleton():
        yield renderer.fit(repr(codepoints), width=PROPS_WIDTH - AGE_WIDTH, fill=True)

        # Account for non-grapheme-clusters and emoji sequences.
        name = age = None
        if not UCD.is_grapheme_cluster(codepoints):
            name = renderer.fit(
                f'Not a grapheme cluster in UCD {UCD.version.in_short_format()}',
                width=_name_width(renderer.width)
            )
            yield ' ' * AGE_WIDTH
            yield f' {renderer.hint(name)}'
            return

        name, age = UCD.emoji_sequence_data(codepoints)
        if age:
            yield f'{cast(Version, age).in_emoji_format():>{AGE_WIDTH}}'
        elif name:
            yield ' ' * AGE_WIDTH
        if name:
            yield f' {renderer.fit(name, width=_name_width(renderer.width))}'
        return

    # A single code point: Display detailed metadata including presentation.
    codepoint = codepoints.to_singleton()
    unidata = UCD.lookup(codepoint)

    yield f'{codepoint!r:<8s} '
    vs = presentation.variation_selector
    yield f'{vs - 0xFE00 + 1:>2} ' if vs > 0 else '   '
    yield unidata.category.value
    yield f' {unidata.east_asian_width:<2} '
    flags = ' '.join(f.value for f in unidata.flags)
    yield renderer.fit(flags, width=25, fill=True)

    name = age = None
    if presentation is not Presentation.TEXT:
        name, age = UCD.emoji_sequence_data(presentation.apply(codepoint))

    age_display = '' if unidata.age is None else str(unidata.age)
    age_display = age.in_emoji_format() if age else age_display
    yield f' {age_display:>{AGE_WIDTH}} '

    if unidata.category is GeneralCategory.Unassigned:
        name = renderer.fit(
            f'Unassigned in UCD {UCD.version.in_short_format()}',
            width=_name_width(renderer.width)
        )
        yield renderer.hint(name)
        return

    name = name or unidata.name or ''
    block = unidata.block or ''
    if name and block:
        name = name + ' '
    if block:
        name = f'{name}({block})'
    yield renderer.fit(name, width=_name_width(renderer.width))


# --------------------------------------------------------------------------------------


def format_lines(
    renderer: Renderer,
    stream: Iterable[HeadingPresentation | CodePointPresentation],
) -> Iterator[str]:
    """Emit the extended, per-line representation for all code points."""
    for presentation, codepoints in stream:
        if presentation.is_heading:
            yield format_heading(renderer, cast(str, codepoints))
        else:
            yield ''.join(
                itertools.chain(
                    format_blot(
                        renderer,
                        cast(CodePoint | CodePointSequence, codepoints),
                        presentation=presentation,
                    ),
                    format_info(
                        renderer,
                        cast(CodePoint | CodePointSequence, codepoints),
                        presentation=presentation,
                    )
                )
            )


def format_grid_lines(
    renderer: Renderer,
    stream: Iterable[CodePointPresentation],
) -> Iterator[str]:
    """Emit the compact, grid-like representation for all code points."""
    column_count = (renderer.width - 1) // 11
    while True:
        line = ''.join(itertools.chain.from_iterable(
            format_blot(
                renderer,
                codepoints,
                presentation=presentation,
                start_column=count * 11 + 2,
            )
            for count, (presentation, codepoints)
            in enumerate(itertools.islice(stream, column_count))
        ))
        if line == '':
            return
        yield line


# --------------------------------------------------------------------------------------


def page_lines(
    renderer: Renderer,
    lines: Iterable[str],
    *,
    make_legend: None | Callable[[Renderer], str] = None,
) -> None:
    """
    Display one page of lines at a time. This function should update the
    terminal size just before displaying the previous or next page and then
    regenerate its output accordingly. That means that the input to the pager
    should be the list of code points and grapheme clusters to cover as well as
    the function for rendering lines of output.

    TODO: move full page re-generation into the pager; switch to reading keyboard
    without enter
    """
    hint = renderer.hint(f' [ ‹p›revious | ‹n›ext | ‹q›uit ] ‹return› ')

    buffer = [*lines]
    buffer_size = len(buffer)
    start = stop = 0
    forward = True

    while True:
        renderer.refresh()
        legend = None if make_legend is None else make_legend(renderer)
        legend_height = 0 if legend is None else len(legend.splitlines())
        body_height = renderer.height - legend_height - 1

        if forward:
            start = stop + 1
            stop = start + body_height
            done = start >= buffer_size
        else:
            stop = start - 1
            start = stop - body_height
            done = stop <= 0

        if done:
            print(renderer.window_title(''))
            return

        body = buffer[start:stop]
        actual_body_height = len(body)
        if actual_body_height < body_height:
            body.extend([''] * (body_height - actual_body_height))

        page = '\n'.join(itertools.chain([] if legend is None else [legend], body))
        print(page)

        try:
            s = input(hint).lower()
        except KeyboardInterrupt:
            return
        if s in ('q', 'quit'):
            return
        if s in ('', 'n', 'next', 'f', 'forward'):
            forward = True
        if s in ('p', 'prev', 'previous', 'b', 'back'):
            forward = False
