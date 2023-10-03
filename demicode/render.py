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

from abc import ABCMeta, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
import os
import sys
from typing import Never, TextIO


from .codepoint import CodePoint


# --------------------------------------------------------------------------------------
# Basic Support for Styling Output


_CSI = '\x1b['
_OSC = '\x1b]'
_ST = '\x1b\\'


def _SGR(code: str) -> str:
    """Format Select Graphic Rendition."""
    return f'{_CSI}{code}m'


def _CHA(column: int | str) -> str:
    """Format Cursor Horizontal Absolute (an editor function)."""
    return f'{_CSI}{column}G'


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


# --------------------------------------------------------------------------------------
# Reading Key Presses


class MalformedEscape(Exception):
    pass


class KeyPressReader(Iterator[bytes], metaclass=ABCMeta):
    """
    The abstract base class for reading key presses from a file descriptor
    without waiting for a newline. The file descriptor must identify a TTY in
    cbreak mode.
    """

    PLATFORM_SUPPORTED = sys.platform in ('darwin', 'linux')

    __slots__ = ('_input',)

    def __init__(self, input: TextIO) -> None:
        self._input = input

    def __next__(self) -> bytes:
        return self.read()

    @abstractmethod
    def read(self, *, timeout: float = 0, length: int = 3) -> bytes:
        """
        Read the next pressed key or key combination. If the key or key
        combination corresponds to an ASCII character, this method returns a
        one-byte sequence with that character. For all other keys and key
        combinations, it returns a multibyte sequence. If the `timeout` is
        positive, this method waits as long for a key press and then raises a
        `TimeoutError`. The length is exposed for `read_escape()`, which
        consumes the input byte by byte.
        """

    ESCAPE_TIMEOUT = 0.2

    def read_escape(self) -> bytes:
        """
        Read a complete escape sequence from input. This method recognizes
        the different escape sequence patterns and accumulates all bytes
        belonging to such a sequence. This method raises a `TimeoutError` if
        a character read times out. It raises a `MalformedEscape` if the
        escape sequence is syntactically invalid.
        """
        buffer = bytearray()

        def next_byte() -> int:
            b = self.read(timeout=self.ESCAPE_TIMEOUT, length=1)[0]
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


if KeyPressReader.PLATFORM_SUPPORTED:

    import select
    import termios
    import tty

    class UnixKeyPressReader(KeyPressReader):

        __slots__ = ()

        def read(self, *, timeout: float = 0, length: int = 3) -> bytes:
            fileno = self._input.fileno()
            if timeout > 0:
                ready, _, _ = select.select([fileno], [], [], timeout)
                if not ready:
                    raise TimeoutError()
            return os.read(fileno, length)


# --------------------------------------------------------------------------------------
# Highlevel I/O


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
    # Window Title

    def set_window_title(self, text: str) -> None:
        """Save window title and then update it."""
        pass

    def restore_window_title(self) -> None:
        """Restore window title saved before setting it."""
        pass

    # ----------------------------------------------------------------------------------
    # Terminal Properties Including Size

    @property
    def is_interactive(self) -> bool:
        """Determine whether interactive input is supported."""
        return self._interactive

    @property
    def has_style(self) -> bool:
        """Determine whether escape sequences are supported."""
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
    # Input

    if KeyPressReader.PLATFORM_SUPPORTED:

        @contextmanager
        def reader(self) -> Iterator[KeyPressReader]:
            input = self._input
            fileno = input.fileno()
            settings = termios.tcgetattr(fileno)
            tty.setcbreak(fileno)
            try:
                yield UnixKeyPressReader(input)
            finally:
                termios.tcsetattr(fileno, termios.TCSADRAIN, settings)

    else:

        @contextmanager
        def reader(self) -> Iterator[KeyPressReader]:
            raise NotImplementedError('Renderer.reader()')

    # ----------------------------------------------------------------------------------
    # Querying the Terminal

    def query(self, text: str) -> bytes:
        raise NotImplementedError()

    def get_position(self) -> None | tuple[int, int]:
        raise NotImplementedError()

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

    def format_error(self, text: str) -> str:
        return text

    # ----------------------------------------------------------------------------------
    # Output

    def beep(self) -> None:
        pass

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

    def set_window_title(self, text: str) -> None:
        if self.is_interactive:
            self.print(f'{_CSI}22;0t{_OSC}0;{text}{_ST}')

    def restore_window_title(self) -> None:
        if self.is_interactive:
            self.print(f'{_OSC}0;{_ST}{_CSI}23;0t')

    def query(self, text: str) -> bytes:
        if not text.startswith('\x1B'):
            raise ValueError(f'query {text} is not an escape sequence')
        with self.reader() as reader:
            self.print(text)
            return reader.read_escape()

    def get_position(self) -> None | tuple[int, int]:
        response = self.query(f'{_CSI}6n')
        if not response.startswith(b'\x1B[') or not response.endswith(b'R'):
            return None
        row, _, column = response[2:-1].partition(b';')
        return int(row), int(column)

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

    def beep(self) -> None:
        print('\a')
