"""
Display character blots in the terminal.

This module has one entry point, `display()`. It renders character blots one
page at a time, waits for user input, and then moves a page forward or backward,
as requested by the user. When displaying a new page, it also updates the
terminal size to ensure that the output fits into the window.
"""

from collections.abc import Iterator, Iterable
from contextlib import ExitStack
import itertools
import math
from typing import Callable, cast

from .benchmark import Probe
from .codepoint import CodePoint, CodePointSequence
from .control import Action, read_line_action
from .model import Age, General_Category, Presentation
from .render import Padding, Renderer
from .ucd import UnicodeCharacterDatabase
from . import __version__


# --------------------------------------------------------------------------------------
# Enrich Code Points with Presentation


def make_presentable(
    data: Iterable[str | CodePoint | CodePointSequence],
    ucd: UnicodeCharacterDatabase,
    *,
    headings: bool = True,  # Allow embedded headings
) -> Iterator[tuple[Presentation, str | CodePoint | CodePointSequence]]:
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
            if len(datum) == 2 and datum[1] == CodePoint.PAD:
                datum = datum[0]
            yield Presentation.NONE, datum
            continue

        datum = datum.to_singleton()
        if datum in ucd.fullwidth_punctuation:
            yield Presentation.CORNER, datum
            yield Presentation.CENTER, datum
        elif datum in ucd.with_emoji_variation:
            yield Presentation.NONE, datum
            yield Presentation.TEXT, datum
            yield Presentation.EMOJI, datum
            if datum in ucd.with_keycap:
                yield Presentation.KEYCAP, datum
        else:
            yield Presentation.NONE, datum


# --------------------------------------------------------------------------------------


LEGEND_BLOT = ' 123   123  '
LEGEND_PROPS = 'Sz Code Pt  VS Ct Wd Other Properties            Age'
LEGEND_NAME = 'Name'
LEGEND = f'{LEGEND_BLOT} {LEGEND_PROPS} {LEGEND_NAME}'

BLOT_WIDTH = len(LEGEND_BLOT)
PROPS_WIDTH = len(LEGEND_PROPS)
SIZE_WIDTH = 3
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
    return LEGEND.ljust(renderer.width) if renderer.has_style else LEGEND[6:]


def emit_heading(heading: str, renderer: Renderer) -> None:
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

    renderer.emit_heading(heading)


def emit_blot(
    codepoints: CodePoint | CodePointSequence,
    renderer: Renderer,
    ucd: UnicodeCharacterDatabase,
    *,
    start_column: int = 1,
    presentation: Presentation = Presentation.NONE,
) -> None:
    """Format the fixed-width character blot."""
    # Determine display and width for blot. If the code points are an unassigned
    # singleton or more than one grapheme cluster, their blots are elided.
    presentation, codepoints = presentation.normalize(codepoints)

    if not ucd.is_grapheme_cluster(codepoints):
        display = '···'
        width = 3
    elif codepoints.is_singleton():
        codepoint = codepoints.to_singleton()
        if (
            ucd.resolve(codepoint, General_Category)
            is General_Category.Unassigned
        ):
            display = '···'
            width = 3
        else:
            display = presentation.apply(codepoints.to_singleton())
            width = ucd.width(display)
    else:
        display = str(codepoints)
        width = ucd.width(codepoints)

    # Fail gracefully for control, surrogate, and private use characters.
    if width == -1:
        width = 1
        display = str(CodePoint.REPLACEMENT_CHARACTER)

    # Render Character Blots
    renderer.adjust_column(start_column + 1)
    renderer.emit_blot(display, Padding.BACKGROUND, 3 - width)
    renderer.write(' ')
    renderer.adjust_column(start_column + 7)
    renderer.emit_blot(display, Padding.FOREGROUND, 3 - width)
    renderer.write(' ' if renderer.has_style else '   ')


def emit_info(
    codepoints: CodePoint | CodePointSequence,
    renderer: Renderer,
    ucd: UnicodeCharacterDatabase,
    *,
    size: int = -1,
    presentation: Presentation = Presentation.NONE,
) -> None:
    """Format information about the code points."""
    renderer.adjust_column(len(LEGEND_BLOT) + 1 + 1)
    renderer.write('   ' if size == -1 else f'{size: 2d} ')

    # For code points, if they have implicit presentation, switch to single code
    # point and presentation instead. Otherwise, display the code points, plus
    # age and name for emoji sequences, plus disclaimer for non-grapheme-clusters.
    presentation, codepoints = presentation.normalize(codepoints)
    if not codepoints.is_singleton():
        renderer.write(renderer.fit(
            repr(codepoints), width=PROPS_WIDTH - SIZE_WIDTH - AGE_WIDTH - 1, fill=True
        ))

        # Account for non-grapheme-clusters and emoji sequences.
        name = age = None
        if not ucd.is_grapheme_cluster(codepoints):
            name = renderer.fit(
                f'Not a grapheme cluster in UCD {ucd.version.in_short_format()}',
                width=_name_width(renderer.width)
            )
            renderer.write(' ' * (AGE_WIDTH + 1))
            renderer.write(' ')
            renderer.faint(name)
            return

        name, age = ucd.emoji_sequence_data(codepoints)
        if age:
            renderer.write(f' {age.in_emoji_format():>{AGE_WIDTH}}')
        elif name:
            renderer.write(' ' * (AGE_WIDTH + 1))
        if name:
            renderer.write(f' {renderer.fit(name, width=_name_width(renderer.width))}')
        return

    # A single code point: Display detailed metadata including presentation.
    codepoint = codepoints.to_singleton()
    unidata = ucd.lookup(codepoint)

    renderer.write(f'{codepoint!r:<8s} ')
    vs = presentation.variation_selector
    renderer.write(f'{vs - CodePoint.VARIATION_SELECTOR_1 + 1:>2} ' if vs>0 else '   ')
    renderer.write(unidata.category.value)
    renderer.write(f' {unidata.east_asian_width:<2} ')
    flags = ' '.join(f.value for f in unidata.flags)
    renderer.write(renderer.fit(flags, width=25, fill=True))

    name = age = None
    if presentation is not Presentation.TEXT:
        name, age = ucd.emoji_sequence_data(presentation.apply(codepoint))

    age_display = '' if unidata.age is Age.Unassigned else str(unidata.age)
    age_display = age.in_emoji_format() if age else age_display
    renderer.write(f' {age_display:>{AGE_WIDTH}} ')

    if unidata.category is General_Category.Unassigned:
        name = renderer.fit(
            f'Unassigned in UCD {ucd.version.in_short_format()}',
            width=_name_width(renderer.width)
        )
        renderer.faint(name)
        return

    name = name or unidata.name or ''
    block = unidata.block or ''
    if name and block:
        name = name + ' '
    if block:
        name = f'{name}({block})'
    renderer.write(renderer.fit(name, width=_name_width(renderer.width)))


# --------------------------------------------------------------------------------------


def emit_lines(
    stream: Iterable[tuple[Presentation, str | CodePoint | CodePointSequence]],
    renderer: Renderer,
    ucd: UnicodeCharacterDatabase,
    *,
    legend: None | str,
    incrementally: bool,
    probe: None | Probe,
) -> int:
    label = Probe.PAGE_LINE_BY_LINE if incrementally else Probe.PAGE_AT_ONCE
    lines_printed = 0

    with ExitStack() as stack:
        if probe:
            stack.enter_context(probe.measure(label))

        if legend is not None:
            renderer.emit_legend(legend)
            renderer.newline()

        for presentation, codepoints in stream:
            if presentation.is_heading:
                emit_heading(cast(str, codepoints), renderer)
            else:
                emit_blot(
                    cast(CodePoint | CodePointSequence, codepoints),
                    renderer,
                    ucd,
                    presentation=presentation,
                )

                size = -1
                if incrementally:
                    renderer.flush()
                    position = renderer.get_position()
                    size = -1 if position is None else position[1] - 9

                emit_info(
                    cast(CodePoint | CodePointSequence, codepoints),
                    renderer,
                    ucd,
                    size=size,
                    presentation=presentation,
                )

            renderer.newline()
            lines_printed += 1

        renderer.flush()

    if probe:
        renderer.write(f'[{ probe.latest_reading(label):,} ns]')

    return lines_printed


GRID_COLUMN_WIDTH = 16

def grid_column(index: int) -> int:
    return index * GRID_COLUMN_WIDTH + 2


def emit_grid(
    stream: Iterable[tuple[Presentation, str | CodePoint | CodePointSequence]],
    renderer: Renderer,
    ucd: UnicodeCharacterDatabase,
    *,
    column_count: int,
) -> None:
    """Emit the compact, grid-like representation for all code points."""
    # Ensure that every loop iteration consumes more code points
    #stream = iter(data)

    for count, (presentation, codepoints) in enumerate(
        itertools.islice(stream, column_count)
    ):
        emit_blot(
            cast(CodePoint | CodePointSequence, codepoints),
            renderer,
            ucd,
            presentation=presentation,
            start_column=grid_column(count),
        )


# --------------------------------------------------------------------------------------


def display(
    stream: Iterable[str | CodePoint | CodePointSequence],
    renderer: Renderer,
    ucd: UnicodeCharacterDatabase,
    *,
    incrementally: bool = False,
    in_grid: bool = False,
    probe: None | Probe = None,
    read_action: Callable[[Renderer], Action] = read_line_action,
) -> None:
    data = [*make_presentable(stream, ucd, headings=not in_grid)]
    total_count = len(data)
    start = stop = -1
    action = Action.FORWARD
    pages_shown = 0

    renderer.set_window_title(
        f'[ Demicode {__version__} • Unicode {ucd.version.in_short_format()} ]'
    )

    while True:
        renderer.refresh()

        legend = None if in_grid else format_legend(renderer)
        legend_height = 0 if legend is None else len(legend.splitlines())
        body_height = renderer.height - legend_height - 1
        column_count = (renderer.width - 2) // GRID_COLUMN_WIDTH if in_grid else 1
        display_count = body_height * column_count

        if action is Action.FORWARD:
            start = stop + 1
            stop = min(start + display_count, total_count)
            done = start >= total_count
        elif action is Action.BACKWARD:
            stop = start - 1
            start = max(0, stop - display_count)
            done = stop <= 0
        else:
            stop = min(start + display_count, total_count)
            done = start >= total_count

        if done:
            renderer.restore_window_title()
            return

        if in_grid:
            emit_grid(
                data[start:stop],
                renderer,
                ucd,
                column_count=column_count,
            )
            blots_printed = stop - start + 1
            lines_printed = math.ceil(blots_printed / column_count)
        else:
            lines_printed = emit_lines(
                data[start:stop],
                renderer,
                ucd,
                legend=legend,
                incrementally=incrementally,
                probe=probe,
            )
        pages_shown += 1

        if renderer.is_interactive:
            # Make sure we fill the page with lines
            if lines_printed < body_height:
                for _ in range(body_height - lines_printed):
                    renderer.newline()

            if probe is None:
                # Ask user in true interactive mode
                action = read_action(renderer)
            elif pages_shown > 1:
                # Thrash back and forth when timing page rendering
                action = (
                    Action.TERMINATE if pages_shown >= probe.required_readings else
                    Action.FORWARD if action is Action.BACKWARD else
                    Action.BACKWARD
                )
                renderer.newline()

            if action is Action.TERMINATE:
                renderer.restore_window_title()
                return
