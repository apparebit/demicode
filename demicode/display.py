"""
Display character blots in the terminal.

This module has one entry point, `display()`. It renders character blots one
page at a time, waits for user input, and then moves a page forward or backward,
as requested by the user. When displaying a new page, it also updates the
terminal size to ensure that the output fits into the window.
"""

from collections.abc import Iterator, Iterable
import itertools
from typing import Callable, cast

from .codepoint import CodePoint, CodePointSequence
from .control import Action, read_line_action
from .model import GeneralCategory, Presentation, Property
from .render import Padding, Renderer
from .ucd import UnicodeCharacterDatabase, Version


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


def format_heading(heading: str, renderer: Renderer) -> str:
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
    codepoints: CodePoint | CodePointSequence,
    renderer: Renderer,
    ucd: UnicodeCharacterDatabase,
    *,
    start_column: int = 1,
    presentation: Presentation = Presentation.NONE,
) -> Iterator[str]:
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
            ucd.resolve(codepoint, Property.General_Category)
            is GeneralCategory.Unassigned
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
    yield renderer.column(start_column + 1)
    yield renderer.blot(display, Padding.BACKGROUND, 3 - width)
    yield ' '
    yield renderer.column(start_column + 7)
    yield renderer.blot(display, Padding.FOREGROUND, 3 - width)
    yield ' ' if renderer.has_style else '   '


def format_info(
    codepoints: CodePoint | CodePointSequence,
    renderer: Renderer,
    ucd: UnicodeCharacterDatabase,
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
        yield renderer.fit(
            repr(codepoints), width=PROPS_WIDTH - AGE_WIDTH - 1, fill=True)

        # Account for non-grapheme-clusters and emoji sequences.
        name = age = None
        if not ucd.is_grapheme_cluster(codepoints):
            name = renderer.fit(
                f'Not a grapheme cluster in UCD {ucd.version.in_short_format()}',
                width=_name_width(renderer.width)
            )
            yield ' ' * (AGE_WIDTH + 1)
            yield f' {renderer.hint(name)}'
            return

        name, age = ucd.emoji_sequence_data(codepoints)
        if age:
            yield f' {cast(Version, age).in_emoji_format():>{AGE_WIDTH}}'
        elif name:
            yield ' ' * (AGE_WIDTH + 1)
        if name:
            yield f' {renderer.fit(name, width=_name_width(renderer.width))}'
        return

    # A single code point: Display detailed metadata including presentation.
    codepoint = codepoints.to_singleton()
    unidata = ucd.lookup(codepoint)

    yield f'{codepoint!r:<8s} '
    vs = presentation.variation_selector
    yield f'{vs - CodePoint.VARIATION_SELECTOR_1 + 1:>2} ' if vs > 0 else '   '
    yield unidata.category.value
    yield f' {unidata.east_asian_width:<2} '
    flags = ' '.join(f.value for f in unidata.flags)
    yield renderer.fit(flags, width=25, fill=True)

    name = age = None
    if presentation is not Presentation.TEXT:
        name, age = ucd.emoji_sequence_data(presentation.apply(codepoint))

    age_display = '' if unidata.age is None else str(unidata.age)
    age_display = age.in_emoji_format() if age else age_display
    yield f' {age_display:>{AGE_WIDTH}} '

    if unidata.category is GeneralCategory.Unassigned:
        name = renderer.fit(
            f'Unassigned in UCD {ucd.version.in_short_format()}',
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
    data: Iterable[tuple[Presentation, str | CodePoint | CodePointSequence]],
    renderer: Renderer,
    ucd: UnicodeCharacterDatabase,
) -> Iterator[str]:
    """Emit the extended, per-line representation for all code points."""
    for presentation, codepoints in data:
        if presentation.is_heading:
            yield format_heading(cast(str, codepoints), renderer)
        else:
            yield ''.join(
                itertools.chain(
                    format_blot(
                        cast(CodePoint | CodePointSequence, codepoints),
                        renderer,
                        ucd,
                        presentation=presentation,
                    ),
                    format_info(
                        cast(CodePoint | CodePointSequence, codepoints),
                        renderer,
                        ucd,
                        presentation=presentation,
                    )
                )
            )


GRID_COLUMN_WIDTH = 16

def grid_column(index: int) -> int:
    return index * GRID_COLUMN_WIDTH + 2


def format_grid_lines(
    data: Iterable[tuple[Presentation, CodePoint | CodePointSequence]],
    column_count: int,
    renderer: Renderer,
    ucd: UnicodeCharacterDatabase,
) -> Iterator[str]:
    """Emit the compact, grid-like representation for all code points."""
    # Ensure that every loop iteration consumes more code points
    stream = iter(data)

    while True:
        line = ''.join(itertools.chain.from_iterable(
            format_blot(
                codepoints,
                renderer,
                ucd,
                presentation=presentation,
                start_column=grid_column(count),
            )
            for count, (presentation, codepoints)
            in enumerate(itertools.islice(stream, column_count))
        ))
        if line == '':
            return
        yield line


# --------------------------------------------------------------------------------------


def display(
    stream: Iterable[str | CodePoint | CodePointSequence],
    renderer: Renderer,
    ucd: UnicodeCharacterDatabase,
    *,
    in_grid: bool = False,
    read_action: Callable[[Renderer], Action] = read_line_action,
) -> None:
    data = [*make_presentable(stream, ucd, headings=not in_grid)]
    total_count = len(data)
    start = stop = -1
    action = Action.FORWARD

    renderer.set_window_title(f'⸺ Demicode • UCD {ucd.version.in_short_format()} ⸺')

    while True:
        renderer.refresh()

        legend = None if in_grid else format_legend(renderer)
        legend_height = 0 if legend is None else len(legend.splitlines())
        body_height = renderer.height - legend_height - 1
        column_count = (renderer.width - 2) // GRID_COLUMN_WIDTH if in_grid else 1
        display_count = body_height * column_count

        if action.forward:
            start = stop + 1
            stop = min(start + display_count, total_count)
            done = start >= total_count
        elif action.backward:
            stop = start - 1
            start = max(0, stop - display_count)
            done = stop <= 0

        if done:
            renderer.set_window_title('')
            return

        if in_grid:
            body = [*format_grid_lines(
                cast(
                    Iterable[tuple[Presentation, CodePoint | CodePointSequence]],
                    data[start:stop],
                ),
                column_count,
                renderer,
                ucd,
            )]
        else:
            body = [*format_lines(data[start:stop], renderer, ucd)]

        if renderer.is_interactive:
            actual_body_height = len(body)
            if actual_body_height < body_height:
                body.extend([''] * (body_height - actual_body_height))

        page = '\n'.join(itertools.chain([] if legend is None else [legend], body))
        renderer.println(page)

        if renderer.is_interactive:
            action = read_action(renderer)
            if action.terminate:
                renderer.set_window_title('')
                return
