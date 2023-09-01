"""
Display character blots in the terminal.

This module contains the functionality for formatting demicode's character blots
on screen. Its high-level functions are:

  * `add_presentation()` enriches a stream of Unicode code points, grapheme
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
from enum import auto, Enum
import itertools
from typing import cast, Literal, overload, TypeAlias

from .codepoint import CodePoint, CodePointSequence
from .model import BinaryProperty
from .render import Padding, Renderer
from .ucd import UCD, Version


CodePoints: TypeAlias = CodePoint | CodePointSequence


class Presentation(Enum):
    """The presentation style for displaying a character.

    `PLAIN` displays just a character. It is the only valid presentation for
    most Unicode code points. The other presentation styles add further code
    points:

      * `CORNER` adds U+FE00 variation selector-1
      * `CENTER` adds U+FE01 variation selector-2
      * `TEXT` adds U+FE0E variation selector-15
      * `EMOJI` adds U+FE0F variation selector-16
      * `KEYCAP` adds U+FE0F variation selector-16 and U+20E3 combining
        enclosing keycap

    `CORNER` and `CENTER` may be used with the full-width forms of `!,.:;?`
    (U+FF01, U+FF0C, U+FF0E, U+FF1A, U+FF1B, U+FF1F), `TEXT` and `EMOJI` with
    the code points included in `USD.with_emoji_variation`, and `KEYCAP` with
    `#*0123456789`, which also are in `USD.with_emoji_variation`.
    """

    PLAIN = auto()
    CORNER = auto()
    CENTER = auto()
    TEXT = auto()
    EMOJI = auto()
    KEYCAP = auto()

    @classmethod
    def unapply(cls, codepoints: CodePointSequence) -> 'Presentation':
        if len(codepoints) == 2:
            second = codepoints[1]
            if second == 0xFE00:
                return Presentation.CORNER
            elif second == 0xFE01:
                return Presentation.CENTER
            elif second == 0xFE0E:
                return Presentation.TEXT
            elif second == 0xFE0F:
                return Presentation.EMOJI
        elif (
            len(codepoints) == 3
            and codepoints[1] == 0xFE0F
            and codepoints[2] == 0x20E3
        ):
            return Presentation.KEYCAP

        return Presentation.PLAIN

    def apply(self, codepoint: CodePoint) -> str:
        """Apply this presentation to the code point, yielding a string."""
        match self:
            case Presentation.PLAIN:
                return chr(codepoint)
            case Presentation.CORNER:
                assert codepoint in UCD.fullwidth_punctuation
                return f'{chr(codepoint)}\uFE00'
            case Presentation.CENTER:
                assert codepoint in UCD.fullwidth_punctuation
                return f'{chr(codepoint)}\uFE01'
            case Presentation.TEXT:
                assert codepoint in UCD.with_emoji_variation
                return f'{chr(codepoint)}\uFE0E'
            case Presentation.EMOJI:
                assert codepoint in UCD.with_emoji_variation
                return f'{chr(codepoint)}\uFE0F'
            case Presentation.KEYCAP:
                assert codepoint in UCD.with_keycap
                return f'{chr(codepoint)}\uFE0F\u20E3'

    @property
    def is_emoji_variation(self) -> bool:
        return self in (Presentation.EMOJI, Presentation.KEYCAP)

    @property
    def variation_selector(self) -> str:
        match self:
            case Presentation.PLAIN:
                return '   '
            case Presentation.CORNER:
                return ' 1 '
            case Presentation.CENTER:
                return ' 2 '
            case Presentation.TEXT:
                return '15 '
            case Presentation.EMOJI:
                return '16 '
            case Presentation.KEYCAP:
                return '16 '


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
    """Format the legend for lines formatted with `format_info`."""
    if not renderer.has_style:
        return LEGEND[6:]
    return renderer.legend(LEGEND.ljust(renderer.width))


def format_heading(renderer: Renderer, heading: str) -> str:
    """
    Format the given heading. The initial \\u0001 (Start of Heading) is
    discarded.
    """
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


def format_info(
    renderer: Renderer,
    codepoints: CodePoints,
    *,
    start_column: int = 1,
    account_for_emoji: bool = True,
    include_info: bool = True,
    presentation: Presentation = Presentation.PLAIN,
) -> Iterator[str]:
    """
    Format the fixed-width information for the given code points.

    If `include_info` is `True`, this function emits one line per code point.
    After showing the codepoint against a lightly colored background and a
    darkly colored foreground, this function also displays:

      * the hexadecimal value of the code point,
      * the general category,
      * the East Asian Width,
      * whether it used text or emoji variation selectors,
      * the Unicode version that introduced the code point,
      * and the name followed by the block in parentheses.

    If `include_info` is `False`, this function only displays the character,
    assuming it is a visible and not, for example, a surrogate or unassigned
    code point.

    The brightness controls how colorful the output is. At the default of 0,
    both background and foreground are colored in greys. At 1, the background
    turns a bright yelllow and, at 2, the foreground turns a bright orange. That
    generally works for the one code point per line format, but I do not
    recommend cranking up the brightness for the grid format.
    """
    name = age = unidata = None

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~
    # Determine Width and Display
    if not codepoints.is_singleton():
        assert isinstance(codepoints, CodePointSequence)
        presentation = Presentation.unapply(codepoints)
        if presentation is Presentation.PLAIN:
            wcwidth = UCD.wcwidth(codepoints)
            display = str(codepoints)
            name, age = UCD.emoji_sequence_data(codepoints)
            if account_for_emoji and name:
                wcwidth = 2
        else:
            codepoints = codepoints[0]
            # The next conditional does the work

    if codepoints.is_singleton():
        codepoint = codepoints.to_singleton()
        if UCD.is_line_break(codepoint):
            codepoint = CodePoint.of(0x23CE) # RETURN SYMBOL

        unidata = UCD.lookup(codepoint)
        if account_for_emoji and (
            # A code point with emoji presentation as default
            BinaryProperty.Emoji_Presentation in unidata.flags
            and presentation is not Presentation.TEXT
            or
            # A code point with text presentation as default.
            BinaryProperty.Emoji in unidata.flags
            and presentation is Presentation.EMOJI
        ):
            wcwidth = 2
        else:
            wcwidth = unidata.wcwidth()
        display = presentation.apply(codepoint)

    # wcwidth is -1 for control, surrogate, and private use characters. Since
    # they don't usually display either, fall back on replacement character.
    if wcwidth == -1:
        wcwidth = 1
        display = '\uFFFD' # REPLACEMENT CHARACTER

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~
    # Render Character Blots
    yield renderer.column(start_column + 1)
    yield renderer.blot(display, Padding.BACKGROUND, 3 - wcwidth)
    yield ' '
    yield renderer.column(start_column + 7)
    yield renderer.blot(display, Padding.FOREGROUND, 3 - wcwidth)
    yield ' ' if renderer.has_style else '   '

    if not include_info:
        return

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~
    # Render Metadata
    yield renderer.column(start_column + 13)

    # Blotting a grapheme cluster: Display code points. For emoji, also age & name.
    if unidata is None:
        assert isinstance(codepoints, CodePointSequence)
        yield renderer.fit(repr(codepoints), width=PROPS_WIDTH - AGE_WIDTH, fill=True)
        # name and age have already been retrieved
        if not name:
            return
        yield f'{cast(Version, age).in_emoji_format():>{AGE_WIDTH}} '
        yield renderer.fit(name, width=_name_width(renderer.width))
        return

    # Blotting a code point, maybe with variation selector. Display detailed metadata.
    yield f'{codepoint!r:<8s} '
    yield presentation.variation_selector
    yield unidata.category.value
    yield f' {unidata.east_asian_width:<2} '
    flags = ' '.join(f.value for f in unidata.flags)
    yield renderer.fit(flags, width=25, fill=True)

    if presentation is not Presentation.TEXT:
        name, age = UCD.emoji_sequence_data(codepoint)
        if name is None:
            name, age = UCD.emoji_sequence_data(display)

    age_display = '' if unidata.age is None else str(unidata.age)
    age_display = age_display if age is None else age.in_emoji_format()
    yield f' {age_display:>{AGE_WIDTH}} '

    name = name or unidata.name or ''
    block = unidata.block or ''
    if name and block:
        name = name + ' '
    if block:
        name = f'{name}({block})'
    yield renderer.fit(name, width=renderer.width-FIXED_WIDTH)


# --------------------------------------------------------------------------------------


@overload
def add_presentation(
    data: Iterable[CodePoints|str], *, headings: Literal[False]
) -> Iterator[tuple[Presentation, CodePoints]]: ...

@overload
def add_presentation(
    data: Iterable[CodePoints|str], *, headings: bool = ...
) -> Iterator[tuple[Presentation, CodePoints]|tuple[str, None]]: ...

def add_presentation(
    data: Iterable[CodePoints|str],
    *,
    headings: bool = True,  # Allow embedded headings
) -> Iterator[tuple[Presentation, CodePoints]|tuple[str, None]]:
    """
    Enrich code points with their presentation. This function takes a stream of
    code points, graphemes, and headings and enriches the former two with their
    presentation. For most code points and graphemes, that means just adding the
    `PLAIN` presentation. However, for some, that means repeating the code point
    with different presentation options. Headings are passed through the
    function, unless `headings` is `False`, in which case they are dropped.
    """
    for datum in data:
        if isinstance(datum, str):
            if not datum:
                continue
            if datum[0] == '\u0001':
                if headings:
                    yield datum, None
                continue
            if len(datum) > 1:
                yield Presentation.PLAIN, CodePointSequence.from_string(datum)
                continue
            datum = CodePoint.of(datum)

        if not datum.is_singleton():
            yield Presentation.PLAIN, datum
            continue

        datum = datum.to_singleton()
        if datum in UCD.fullwidth_punctuation:
            yield Presentation.CORNER, datum
            yield Presentation.CENTER, datum
        elif datum in UCD.with_emoji_variation:
            yield Presentation.PLAIN, datum
            yield Presentation.TEXT, datum
            yield Presentation.EMOJI, datum
            if datum in UCD.with_keycap:
                yield Presentation.KEYCAP, datum
        else:
            yield Presentation.PLAIN, datum


def format_lines(
    renderer: Renderer,
    stream: Iterable[tuple[Presentation, CodePoints]|tuple[str, None]],
) -> Iterator[str]:
    """Emit the extended, per-line representation for all code points."""
    for presentation, codepoints in stream:
        if isinstance(presentation, str):
            yield format_heading(renderer, presentation)
        else:
            yield ''.join(format_info(
                renderer,
                cast(CodePoint, codepoints),
                presentation=presentation,
            ))


def format_grid_lines(
    renderer: Renderer,
    stream: Iterable[tuple[Presentation, CodePoint | CodePointSequence]],
) -> Iterator[str]:
    """Emit the compact, grid-like representation for all code points."""
    column_count = (renderer.width - 1) // 11
    while True:
        line = ''.join(itertools.chain.from_iterable(
            format_info(
                renderer,
                codepoints,
                presentation=presentation,
                start_column=count * 11 + 2,
                include_info=False,
            )
            for count, (presentation, codepoints)
            in enumerate(itertools.islice(stream, column_count))
        ))
        if line == '':
            return
        yield line


def page_lines(
    renderer: Renderer,
    legend: None | str,
    lines: Iterable[str],
) -> None:
    """Display one page of lines at a time."""

    hint = renderer.hint(' ‹return›: next page; q‹return›/‹ctrl-c›: quit') + '  '
    legend_height = 0 if legend is None else len(legend.splitlines())

    while True:
        renderer.refresh()
        body_height = renderer.height - legend_height - 1
        body = [*itertools.islice(lines, body_height)]

        actual_body_height = len(body)
        if actual_body_height == 0:
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
