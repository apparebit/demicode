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

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
import os
import sys
from typing import Never, TextIO


from .codepoint import CodePoint


_CSI = '\x1b['
_OSC = '\x1b]'
_ST = '\x1b\\'


def _SGR(code: str) -> str:
    """Format Select Graphic Rendition."""
    return f'{_CSI}{code}m'


def _CHA(column: int | str) -> str:
    """Format Cursor Horizontal Absolute (an editor function)."""
    return f'{_CSI}{column}G'


def _HPA(column: int | str) -> str:
    """Format Horizontal Position Absolute (a format effector)."""
    return f'{_CSI}{column}`'


def _bg(color: int | str) -> str:
    return f'48;5;{color}'


def _fg(color: int | str) -> str:
    return f'38;5;{color}'


@dataclass(frozen=True, slots=True)
class Theme:
    legend: str
    heading: str
    blot_highlight: str
    blot_obstruction: str
    faint: str
    error: str

    @classmethod
    def of(
        cls,
        legend: str,
        heading: str,
        blot_highlight: str,
        blot_obstruction: str,
        faint: str,
        error: str,
    ) -> 'Theme':
        return cls(
            _SGR(legend),
            _SGR(heading),
            _SGR(blot_highlight),
            _SGR(blot_obstruction),
            _SGR(faint),
            _SGR(error),
        )


class Style:
    RESET = _SGR('0')
    BOLD = _SGR('1')
    ITALIC = _SGR('3')

    LIGHT = (
        Theme.of(_bg(252), _fg('246;3'), _bg(254), _fg(244), _fg(246), _fg('160;1')),
        Theme.of(_bg(252), _fg('246;3'), _bg(220), _fg(244), _fg(246), _fg('160;1')),
        Theme.of(_bg(252), _fg('246;3'), _bg(220), _fg(202), _fg(246), _fg('160;1')),
    )

    DARK = (
        Theme.of(_bg(240), _fg('245;3'), _bg(238), _fg(243), _fg(245), _fg('88;1')),
        Theme.of(_bg(240), _fg('245;3'), _bg(53),  _fg(243), _fg(245), _fg('88;1')),
        Theme.of(_bg(240), _fg('245;3'), _bg(53),  _fg(93),  _fg(245), _fg('88;1')),
    )

    @classmethod
    def bold(cls, text: str) -> str:
        return f'{cls.BOLD}{text}{cls.RESET}'

    @classmethod
    def italic(cls, text: str) -> str:
        return f'{cls.ITALIC}{text}{cls.RESET}'

    @classmethod
    def link(cls, href: str, text: None | str = None) -> str:
        text = href if text is None else text
        return f'{_OSC}8;;{href}{_ST}{text}{_OSC}8;;{_ST}'


class Mode(StrEnum):
    LIGHT = 'LIGHT'
    DARK = 'DARK'


class Padding(StrEnum):
    BACKGROUND = ' '
    FOREGROUND = str(CodePoint.FULL_BLOCK)


class MalformedEscape(Exception):
    pass


if sys.platform in ('linux', 'darwin'):

    import select
    import termios
    import tty

    class KeyPressReader(Iterator[bytes]):
        """
        A class to read key presses without waiting for a newline. The file
        descriptor must be associated with a TTY in cbreak mode.
        """

        __slots__ = ('_fileno',)

        def __init__(self, fileno: int) -> None:
            self._fileno = fileno

        def __next__(self) -> bytes:
            return self.read()

        def read(self, timeout: float = 0) -> bytes:
            """
            Read the next pressed key or key combination. If the key or key
            combination corresponds to an ASCII character, this method returns a
            one-byte sequence with that character. For all other keys and key
            combinations, it returns a multibyte sequence. If the `timeout` is
            positive, this method waits as long for a key press and then raises
            a `TimeoutError`.
            """
            if timeout > 0:
                ready, _, _ = select.select([self._fileno], [], [], timeout)
                if not ready:
                    raise TimeoutError()
            return os.read(self._fileno, 3)

        ESCAPE_TIMEOUT: float = 0.2

        def read_escape(self) -> bytes:
            """
            Read a complete escape sequence from input. This method recognizes
            the different escape sequence patterns and accumulates all bytes
            belonging to such a sequence. This method raises a `TimeoutError` if
            a character read times out. It raises a `MalformedEscape` if the
            escape sequence is syntactically invalid.
            """
            buffer = bytearray()

            def next_byte(timeout: float = self.ESCAPE_TIMEOUT) -> int:
                ready, _, _ = select.select([self._fileno], [], [], timeout)
                if not ready:
                    raise TimeoutError()
                b = os.read(self._fileno, 1)[0]
                buffer.append(b)
                return b

            def bad_byte(b: int) -> Never:
                raise MalformedEscape(f'unexpected key code 0x{b:02X}')

            b = next_byte()
            if b != 0x1B:
                bad_byte(b)

            b = next_byte()
            if b == 0x5B:  # [
                # CSI has structure
                b = next_byte()
                while 0x30 <= b <= 0x3F:
                    b = next_byte()
                while 0x20 <= b <= 0x2F:
                    b = next_byte()
                if 0x40 <= b <= 0x7E:
                    return bytes(buffer)
                bad_byte(b)

            if b in (0x50, 0x58, 0x5D, 0x5E, 0x5F):  # P,X,],^,_
                # DCS, SOS, OSC, PM, and APC end with ST only
                b = next_byte()
                while b not in (0x07, 0x1B):
                    b = next_byte()
                if b == 0x07:
                    return bytes(buffer)
                b = next_byte()
                if b == 0x5C:  # \\
                    return bytes(buffer)
                bad_byte(b)

            while 0x20 <= b <= 0x2F:
                b = next_byte()
            if 0x30 <= b <= 0x7E:
                return bytes(buffer)
            bad_byte(b)


class Renderer:

    MAX_WIDTH = 140

    def __init__(
        self, input: TextIO, output: TextIO, mode: Mode, intensity: int
    ) -> None:
        self._input = input
        self._output = output
        self._interactive = input.isatty() and output.isatty()
        self._theme = getattr(Style, mode.value)[min(2, max(0, intensity))]
        self.refresh()

    # ----------------------------------------------------------------------------------
    # Read Terminal Properties

    @property
    def is_interactive(self) -> bool:
        return self._interactive

    @property
    def has_style(self) -> bool:
        return False

    def refresh(self) -> None:
        """
        Refresh the renderer's width and height reading of the terminal. This
        method enables polling for size changes when it makes sense to react to
        them, i.e., just before building the next page to display.
        """
        if self.is_interactive:
            width, self._height = os.get_terminal_size()
            self._width = min(width, self.MAX_WIDTH)
        else:
            self._height = 30
            self._width = self.MAX_WIDTH

    @property
    def height(self) -> int:
        return self._height

    @property
    def width(self) -> int:
        return self._width

    # ----------------------------------------------------------------------------------
    # Read from Terminal

    has_reader = False

    @contextmanager
    def reader(self) -> Iterator[KeyPressReader]:
        raise NotImplementedError('Renderer.reader()')

    def query(self, text: str) -> bytes:
        """
        Query the terminal. This method prints the given escape sequence and
        returns the result. It raises an exception if the text is not an escape
        sequence or reading from the terminal is not supported.
        """
        if not text.startswith('\x1B'):
            raise ValueError(f'query {text} is not an escape sequence')
        with self.reader() as reader:
            self.print(text)
            return reader.read_escape()

    def get_cursor(self) -> None | tuple[int, int]:
        """Get the row and column of the cursor. This method requires a reader."""
        response = self.query(f'{_CSI}6n')
        if not response.startswith(b'\x1B[') or not response.endswith(b'R'):
            return None
        row, _, column = response[2:-1].partition(b';')
        return int(row), int(column)

    # ----------------------------------------------------------------------------------
    # Update Terminal

    def set_window_title(self, text: str) -> None:
        pass

    # ----------------------------------------------------------------------------------
    # Format Text

    def fit(self, text: str, *, width: None | int = None, fill: bool = False) -> str:
        if width is None:
            width = self.width
        if len(text) <= width:
            return text.ljust(width) if fill else text
        return text[:width - 1] + '…'

    def adjust_column(self, column: int) -> str:
        return ''

    def format_error(self, text: str) -> str:
        return text

    def format_legend(self, text: str) -> str:
        return text

    def format_heading(self, text: str) -> str:
        return text

    def format_blot(self, text: str, padding: Padding, width: int) -> str:
        if padding is Padding.BACKGROUND:
            return ''
        else:
            return text + (padding.value * width)

    def faint(self, text:str) -> str:
        return text

    def em(self, text: str) -> str:
        return text

    def strong(self, text: str) -> str:
        return text

    def link(self, href: str, text: None | str = None) -> str:
        return href if text is None else text

    # ----------------------------------------------------------------------------------
    # Print Formatted Text

    def print(self, text: str = '') -> None:
        # Sneakily exposing flush()
        if text:
            self._output.write(str(text))
        self._output.flush()

    def println(self, text: str = '') -> None:
        if text:
            self._output.write(str(text))
        self._output.write('\n')
        self._output.flush()


class StyledRenderer(Renderer):
    """A line-oriented console renderer using ANSI escape codes."""

    @property
    def has_style(self) -> bool:
        return True

    if sys.platform in ('linux', 'darwin'):
        has_reader = True

        @contextmanager
        def reader(self) -> Iterator[KeyPressReader]:
            fileno = self._input.fileno()
            settings = termios.tcgetattr(fileno)
            tty.setcbreak(fileno)
            try:
                yield KeyPressReader(fileno)
            finally:
                termios.tcsetattr(fileno, termios.TCSADRAIN, settings)

    def set_window_title(self, text: str) -> None:
        if self.is_interactive:
            self.print(f'{_OSC}0;{text}{_ST}')

    def adjust_column(self, column: int) -> str:
        return _CHA(column)

    def format_legend(self, text: str) -> str:
        return f'{self._theme.legend}{text}{Style.RESET}'

    def format_heading(self, text: str) -> str:
        return f'{self._theme.heading}{text}{Style.RESET}'

    def format_blot(self, text: str, padding: Padding, width: int) -> str:
        if padding is Padding.BACKGROUND:
            return (
                text
                + self._theme.blot_highlight
                + (padding.value * width)
                + Style.RESET
            )
        else:
            return (
                text
                + self._theme.blot_obstruction
                + (padding.value * width)
                + Style.RESET
            )

    def faint(self, text:str) -> str:
        return f'{self._theme.faint}{text}{Style.RESET}'

    def em(self, text: str) -> str:
        return Style.italic(text)

    def strong(self, text: str) -> str:
        return Style.bold(text)

    def link(self, href: str, text: None | str = None) -> str:
        return Style.link(href, text)

    def format_error(self, text: str) -> str:
        return f'{self._theme.error}{text}{Style.RESET}'
