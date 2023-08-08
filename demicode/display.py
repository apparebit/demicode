"""
Display code points in the terminal.

This module displays code points for evaluating a terminal's handling of
fixed-width characters. In particular, this module makes a best guess as to
whether the character is narrow or wide, i.e., requires one or two columns of
the fixed-width display. When displaying a character, this module adds one or
two blank characters in a different color to always form a group of three
columns. By using spaces as well U+2588 FULL BLOCK, it nicely illustrates the
impact of misclassified characters.

To further improve the display, this module can either display one character per
line with helpful information from the Unicode Character Database or in a
tighter grid. It also pages the display.
"""

from collections.abc import Iterator, Iterable
from enum import auto, Enum
import itertools

from .render import Padding, Renderer
from .codepoint import CodePoint
from .ucd import UCD


class Presentation(Enum):
    """The presentation style for displaying a character.

    Text variation adds the U+FE0E variation selector, emoji variation adds the
    U+FE0F variation selector, and keycap adds both U+FE0F and U+20E3 keycap
    selector. Alas, these selectors work only for, ahem, select Unicode code
    points, namely those returned by `USD.with_variation` for the former two
    selectors and `#*0123456789` for the latter. However, most terminals and
    code editors do not handle them correctly, displaying emoji style for both
    sequences in the common case.
    """

    PLAIN = auto()
    TEXT_VARIATION = auto()
    EMOJI_VARIATION = auto()
    KEYCAP = auto()

    @property
    def label(self) -> str:
        if self == Presentation.PLAIN:
            return '   '
        elif self == Presentation.TEXT_VARIATION:
            return 'TV '
        else:
            return 'EV '


# --------------------------------------------------------------------------------------


LEGEND_CORE = ' 123 123 Code Pt  at th ar  Age Name'
CORE_WIDTH = len(LEGEND_CORE)
MIN_NAME_LENGTH = 4


def _max_name_length(width: int) -> int:
    if width <= CORE_WIDTH:
        return MIN_NAME_LENGTH
    return width - CORE_WIDTH + MIN_NAME_LENGTH


def format_legend(renderer: Renderer) -> str:
    """Format the legend for lines formatted with `format_info`."""
    flexible_spaces = _max_name_length(renderer.width) - MIN_NAME_LENGTH

    return (
        renderer.legend(
            (' ' * 18) + '\uFF23 Wd \uFF36' + (' ' * (CORE_WIDTH - 18 - 8))
            + (' ' * flexible_spaces)
        ) + '\n'
        + renderer.legend(
            LEGEND_CORE + (' ' * flexible_spaces)
        )
    )


def format_info(
    renderer: Renderer,
    codepoint: CodePoint,
    *,
    start_column: int = 1,
    include_char_info: bool = True,
    presentation: Presentation = Presentation.PLAIN,
) -> Iterator[str]:
    """
    Format the fixed-width information for the given code point.

    If `include_char_info` is `True`, this function emits one line per code
    point. After showing the codepoint against a lightly colored background and
    a darkly colored foreground, this function also displays:

      * the hexadecimal value of the code point,
      * the general category,
      * the East Asian Width,
      * whether it used text or emoji variation selectors,
      * the Unicode version that introduced the code point,
      * and the name followed by the block in parentheses.

    If `include_char_info` is `False`, this function only displays the
    character, assuming it is a visible and not, for example, a surrogate or
    unassigned code point.

    The brightness controls how colorful the output is. At the default of 0,
    both background and foreground are colored in greys. At 1, the background
    turns a bright yelllow and, at 2, the foreground turns a bright orange. That
    generally works for the one code point per line format, but I do not
    recommend cranking up the brightness for the grid format.
    """
    # What to show?
    name_prefix = None
    category = UCD.category(codepoint)
    wcwidth = UCD.fixed_width(codepoint)

    if category is None or category.is_invalid or wcwidth == -1:
        wcwidth = 1
        display = '\uFFFD' # REPLACEMENT CHARACTER
    elif UCD.is_line_break(codepoint):
        display = '\u23CE' # RETURN SYMBOL
    elif presentation is Presentation.TEXT_VARIATION:
        assert codepoint in UCD.with_variation
        display = f'{chr(codepoint)}\uFE0E' # Force text variation
    elif presentation is Presentation.EMOJI_VARIATION:
        assert codepoint in UCD.with_variation
        display = f'{chr(codepoint)}\uFE0F' # Force emoji variation
    elif presentation is Presentation.KEYCAP:
        assert codepoint in UCD.with_keycap
        display = f'{chr(codepoint)}\uFE0F\u20E3'
        name_prefix = 'KEYCAP '
    else:
        display = chr(codepoint)

    # Render against background and against foreground
    yield renderer.column(start_column + 1)
    yield renderer.blot(display, Padding.BACKGROUND, 3 - wcwidth)
    yield renderer.column(start_column + 5)
    yield renderer.blot(display, Padding.FOREGROUND, 3 - wcwidth)

    # More information about the codepoint
    if include_char_info:
        yield renderer.column(start_column + 9)
        yield f'{str(codepoint):<8s} '
        yield '-- ' if category is None else f'{category.value} '
        east_asian_width = UCD.east_asian_width(codepoint)
        yield '-- ' if east_asian_width is None else f'{east_asian_width.value:<2s} '
        yield presentation.label
        age = UCD.age(codepoint)
        yield ' ---' if age is None else f'{age:>4s}'
        yield renderer.column(start_column + CORE_WIDTH - MIN_NAME_LENGTH)

        name = UCD.name(codepoint)
        if name is None:
            name = str(codepoint)
        block = UCD.block(codepoint)
        if block is not None:
            name = f'{name} ({block})'
        if name_prefix is not None:
            name = name_prefix + name
        max_length = _max_name_length(renderer.width)
        if len(name) > max_length:
            name = name[:max_length - 1] + '…'
        yield f'{name}'


# --------------------------------------------------------------------------------------


def add_presentation(
    codepoints: Iterable[CodePoint]
) -> Iterator[tuple[CodePoint, Presentation]]:
    """
    Turn the stream of code points into a stream of code points and their
    presentation. For every code point in the given iterable, this generator
    produces all possible text, emoji, and keycap variations.
    """
    for codepoint in codepoints:
        if codepoint not in UCD.with_variation:
            yield codepoint, Presentation.PLAIN
            continue

        yield codepoint, Presentation.TEXT_VARIATION
        yield codepoint, Presentation.EMOJI_VARIATION

        if codepoint in UCD.with_keycap:
            yield codepoint, Presentation.KEYCAP


def format_lines(
    renderer: Renderer,
    codepoints: Iterable[tuple[CodePoint, Presentation]],
) -> Iterator[str]:
    """Emit the extended, per-line representation for all code points."""
    for codepoint, presentation in codepoints:
        yield ''.join(format_info(
            renderer,
            codepoint,
            presentation=presentation,
        ))


def format_grid_lines(
    renderer: Renderer,
    codepoints: Iterable[tuple[CodePoint, Presentation]],
) -> Iterator[str]:
    """Emit the compact, grid-like representation for all code points."""
    column_count = (renderer.width - 1) // 11
    while True:
        line = ''.join(itertools.chain.from_iterable(
            format_info(
                renderer,
                codepoint,
                presentation=presentation,
                start_column=count * 11 + 2,
                include_char_info=False,
            )
            for count, (codepoint, presentation)
            in enumerate(itertools.islice(codepoints, column_count))
        ))
        if line == '':
            return
        yield line


def page_lines(
    height: int,
    legend: None | str,
    lines: Iterable[str],
) -> None:
    """Display one page of lines at a time."""
    lines_per_page = height if legend is None else (height - len(legend.splitlines()))
    adjustment = 0 if legend is None else 1 # Adjust for legend entry in page_lines

    while True:
        page_lines = [] if legend is None else [legend]
        page_lines.extend(itertools.islice(lines, lines_per_page))

        line_count = len(page_lines)
        if line_count == (legend is not None):
            return
        if line_count < lines_per_page:
            # line_count counts +1 for legend, unless there is no legend at all.
            page_lines.extend([''] * (lines_per_page - line_count + adjustment))

        print('\n'.join(page_lines))

        try:
            s = input().lower()
        except KeyboardInterrupt:
            return
        if s == 'q' or s == 'quit':
            return
