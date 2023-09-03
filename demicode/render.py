"""
Support for rendering demicode's output with different styles.

This module defines a line-oriented, semantic renderer, the corresponding output
themes, and the low-level code for using ANSI escape codes. There is no
intermediate interface that hides ANSI escape codes behind user-friendly names
since styles are not exposed outside the renderer.

This module also tracks the size of the available terminal character grid. Since
demicode does not implement terminal user interface widgets and just emits a
page's worth of lines at a time, it only makes sense to update the grid size
just before emitting a page. In other words, size updates require polling with
the `Renderer.refresh()` method.
"""

from dataclasses import dataclass
from enum import StrEnum
import os


CSI = '\x1b['


def SGR(code: str) -> str:
    return f'{CSI}{code}m'


def CHA(column: int | str) -> str:
    return f'{CSI}{column}G'


def bg(color: int | str) -> str:
    return f'48;5;{color}'


def fg(color: int | str) -> str:
    return f'38;5;{color}'


@dataclass(frozen=True, slots=True)
class Theme:
    legend: str
    heading: str
    blot_highlight: str
    blot_obstruction: str
    hint: str
    very_strong: str
    error: str

    @classmethod
    def of(
        cls,
        legend: str,
        heading: str,
        blot_highlight: str,
        blot_obstruction: str,
        hint: str,
        very_strong: str,
        error: str,
    ) -> 'Theme':
        return cls(
            SGR(legend),
            SGR(heading),
            SGR(blot_highlight),
            SGR(blot_obstruction),
            SGR(hint),
            SGR(very_strong),
            SGR(error),
        )


class Styles:
    RESET = SGR('0')
    BOLD = SGR('1')

    LIGHT = (
        Theme.of(bg(252), fg('246;3'), bg(254), fg(244), fg(246), '1', fg('160;1')),
        Theme.of(bg(252), fg('246;3'), bg(220), fg(244), fg(246), '1', fg('160;1')),
        Theme.of(bg(252), fg('246;3'), bg(220), fg(202), fg(246), bg('218;1'), fg('160;1')),
    )

    DARK = (
        Theme.of(bg(240), fg('245;3'), bg(238), fg(243), fg(245), '1', fg('88;1')),
        Theme.of(bg(240), fg('245;3'), bg(53),  fg(243), fg(245), '1', fg('88;1')),
        Theme.of(bg(240), fg('245;3'), bg(53),  fg(93),  fg(245), bg('218;1'), fg('88;1')),
    )


class Mode(StrEnum):
    LIGHT = 'LIGHT'
    DARK = 'DARK'


class Padding(StrEnum):
    BACKGROUND = ' '
    FOREGROUND = '\u2588'


class Renderer:

    MAX_WIDTH = 140

    def __init__(self, mode: Mode, intensity: int) -> None:
        self.refresh()

    @property
    def has_style(self) -> bool:
        return False

    def refresh(self) -> None:
        """
        Refresh the renderer's width and height reading of the terminal. This
        method enables polling for size changes when it makes sense to react to
        them, i.e., just before building the next page to display.
        """
        width, self._height = os.get_terminal_size()
        self._width = min(width, self.MAX_WIDTH)

    @property
    def height(self) -> int:
        return self._height

    @property
    def width(self) -> int:
        return self._width

    def window_title(self, text: str) -> str:
        return ''

    def fit(self, text: str, *, width: None | int = None, fill: bool = False) -> str:
        if width is None:
            width = self.width
        if len(text) <= width:
            return text.ljust(width) if fill else text
        return text[:width - 1] + '…'

    def column(self, column: int) -> str:
        return ''

    def legend(self, text: str) -> str:
        return text

    def heading(self, text: str) -> str:
        return text

    def blot(self, text: str, padding: Padding, width: int) -> str:
        if padding is Padding.BACKGROUND:
            return ''
        else:
            return text + (padding.value * width)

    def hint(self, text:str) -> str:
        return text

    def strong(self, text: str) -> str:
        return text

    def very_strong(self, text: str) -> str:
        return text

    def error(self, text: str) -> str:
        return text


class StyledRenderer(Renderer):
    """A line-oriented console renderer using ANSI escape codes."""

    def __init__(self, mode: Mode, intensity: int) -> None:
        self._theme = getattr(Styles, mode.value)[min(2, max(0, intensity))]
        self.refresh()

    @property
    def has_style(self) -> bool:
        return True

    def window_title(self, text: str) -> str:
        return f'\x1b]2;{text}\x07'

    def column(self, column: int) -> str:
        return CHA(column)

    def legend(self, text: str) -> str:
        return f'{self._theme.legend}{text}{Styles.RESET}'

    def heading(self, text: str) -> str:
        return f'{self._theme.heading}{text}{Styles.RESET}'

    def blot(self, text: str, padding: Padding, width: int) -> str:
        if padding is Padding.BACKGROUND:
            return (
                text
                + self._theme.blot_highlight
                + (padding.value * width)
                + Styles.RESET
            )
        else:
            return (
                text
                + self._theme.blot_obstruction
                + (padding.value * width)
                + Styles.RESET
            )

    def hint(self, text:str) -> str:
        return f'{self._theme.hint}{text}{Styles.RESET}'

    def strong(self, text: str) -> str:
        return f'{Styles.BOLD}{text}{Styles.RESET}'

    def very_strong(self, text: str) -> str:
        return f'{self._theme.very_strong}{text}{Styles.RESET}'

    def error(self, text: str) -> str:
        return f'{self._theme.error}{text}{Styles.RESET}'
