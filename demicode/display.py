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
from .model import Presentation
from .render import Padding, Renderer
from .ucd import UCD, Version


CodePoints: TypeAlias = CodePoint | CodePointSequence


# --------------------------------------------------------------------------------------
# Enrich Code Points with Presentation


@overload
def make_presentable(
    data: Iterable[CodePoints | str], *, headings: Literal[False]
) -> Iterator[tuple[Presentation, CodePoints]]: ...

@overload
def make_presentable(
    data: Iterable[CodePoints | str], *, headings: bool = ...
) -> Iterator[tuple[Presentation, CodePoints]|tuple[str, None]]: ...

def make_presentable(
    data: Iterable[CodePoints | str],
    *,
    headings: bool = True,  # Allow embedded headings
) -> Iterator[tuple[Presentation, CodePoints]|tuple[str, None]]:
    """Enrich code points with their presentation."""
    for datum in data:
        if isinstance(datum, str):
            if not datum:
                continue
            if datum[0] == '\u0001':
                if headings:
                    yield datum, None
                continue
            datum = CodePointSequence.from_string(datum)

        if not datum.is_singleton():
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
    # Validate grapheme cluster.
    if not UCD.is_grapheme_cluster(codepoints):
        raise ValueError(f'{codepoints!r} are not a single grapheme cluster')

    # Determine display and width for blot.
    if codepoints.is_singleton():
        display = presentation.apply(codepoints.to_singleton())
        width = UCD.width(display)
    else:
        display = str(codepoints)
        width = UCD.width(codepoints)

    # Fail gracefully for control, surrogate, and private use characters.
    if width == -1:
        width = 1
        display = '\u2BD1' # UNCERTAINTY SIGN

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

    # A grapheme cluster: Try to make presentation explicit. If it is none,
    # display code points and, for emoji sequences, age and name.
    if not codepoints.is_singleton():
        assert isinstance(codepoints, CodePointSequence)
        presentation = Presentation.unapply(codepoints)
        if presentation is Presentation.NONE:
            yield renderer.fit(repr(codepoints), width=PROPS_WIDTH-AGE_WIDTH, fill=True)

            name, age = UCD.emoji_sequence_data(codepoints)
            if name:
                yield f'{cast(Version, age).in_emoji_format():>{AGE_WIDTH}} '
                yield renderer.fit(name, width=_name_width(renderer.width))
            return

        codepoints = codepoints[0]

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

    name = name or unidata.name or ''
    block = unidata.block or ''
    if name and block:
        name = name + ' '
    if block:
        name = f'{name}({block})'
    yield renderer.fit(name, width=renderer.width-FIXED_WIDTH)


# --------------------------------------------------------------------------------------


def format_lines(
    renderer: Renderer,
    stream: Iterable[tuple[Presentation, CodePoints]|tuple[str, None]],
) -> Iterator[str]:
    """Emit the extended, per-line representation for all code points."""
    for presentation, codepoints in stream:
        if isinstance(presentation, str):
            yield format_heading(renderer, presentation)
        else:
            assert codepoints is not None
            yield ''.join(
                itertools.chain(
                    format_blot(
                        renderer,
                        codepoints,
                        presentation=presentation,
                    ),
                    format_info(
                        renderer,
                        codepoints,
                        presentation=presentation,
                    )
                )
            )


def format_grid_lines(
    renderer: Renderer,
    stream: Iterable[tuple[Presentation, CodePoint | CodePointSequence]],
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
    Display one page of lines at a time. This function updates the terminal size
    for every page and accordingly adjusts output. For that reason, it recreates
    the legend for every page as well, hence requiring a function.
    """
    page_number = 0
    hint = renderer.hint(' ‹return›: next page; q‹return›/‹ctrl-c›: quit') + '  '

    while True:
        renderer.refresh()

        page_number += 1
        print(renderer.window_title(f'demicode (page {page_number})'))

        legend = None if make_legend is None else make_legend(renderer)
        legend_height = 0 if legend is None else len(legend.splitlines())
        body_height = renderer.height - legend_height - 1
        body = [*itertools.islice(lines, body_height)]

        actual_body_height = len(body)
        if actual_body_height == 0:
            print(renderer.window_title(''))
            return
        if actual_body_height < body_height:
            body.extend([''] * (body_height - actual_body_height))

        page = '\n'.join(itertools.chain([] if legend is None else [legend], body))
        print(page)

        try:
            s = input(hint).lower()
        except KeyboardInterrupt:
            return
        if s == 'q' or s == 'quit':
            return
