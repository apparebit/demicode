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
import io
import os
import sys
from typing import Never, TextIO


from .codepoint import CodePoint
from .darkmode import is_darkmode


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

    def __init__(self, input: TextIO, output: TextIO, theme: Theme) -> None:
        self._input = input
        self._output = output
        self._interactive = input.isatty() and output.isatty()
        self._theme = theme
        self.refresh()

    @staticmethod
    def new(
        *,
        input: None | TextIO = None,
        output: None | TextIO = None,
        styled:  None | bool = None,
        dark: None | bool = None,
        intensity: None | int = None,
    ) -> 'Renderer':
        """
        Create a new renderer. By default, the renderer uses standard input and
        output. It styles the output if `output` is a TTY, and it uses a theme
        consistent with dark mode if it can be detected and with minimum color
        intensity.
        """
        if input is None:
            input = sys.stdin
        if output is None:
            output = sys.stdout
        if styled is None:
            styled = output.isatty()
        if dark is None:
            dark = is_darkmode()
        if intensity is None:
            intensity = 0

        constructor = StyledRenderer if styled else Renderer
        theme = getattr(Style, 'DARK' if dark else 'LIGHT')[min(2, max(0, intensity))]
        return constructor(input, output, theme)

    # ----------------------------------------------------------------------------------
    # Terminal Decodation

    def set_window_title(self, text: str) -> None:
        """Save window title and then update it."""
        pass

    def restore_window_title(self) -> None:
        """Restore window title saved before setting it."""
        pass

    # ----------------------------------------------------------------------------------
    # Terminal Properties Including Size

    @property
    def input(self) -> TextIO:
        return self._input

    @property
    def output(self) -> TextIO:
        return self._output

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

    def _query(self, text: str) -> bytes:
        raise NotImplementedError()

    def get_position(self) -> None | tuple[int, int]:
        """Get current cursor position. Only available for stylish terminals."""
        raise NotImplementedError()

    # ----------------------------------------------------------------------------------
    # Input

    READER_SUPPORTED: bool = KeyPressReader.PLATFORM_SUPPORTED

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
    # Format Text

    def fit(self, text: str, *, width: None | int = None, fill: bool = False) -> str:
        if width is None:
            width = self.width
        if len(text) <= width:
            return text.ljust(width) if fill else text
        return text[:width - 1] + '…'

    # ----------------------------------------------------------------------------------
    # Output Formatted Text

    def adjust_column(self, column: int) -> None:
        pass

    def newline(self) -> None:
        self._output.write('\n')

    def faint(self, text: str) -> None:
        self._output.write(text)

    def em(self, text: str) -> None:
        self._output.write(text)

    def strong(self, text: str) -> None:
        self._output.write(text)

    def link(self, href: str, text: None | str = None) -> None:
        self._output.write(href if text is None else text)

    def emit_legend(self, text: str) -> None:
        self._output.write(text)

    def emit_heading(self, text: str) -> None:
        self._output.write(text)

    def emit_blot(self, text: str, padding: Padding, width: int) -> None:
        if padding is Padding.FOREGROUND:
            self._output.write(text + (padding.value * width))

    def emit_error(self, text: str) -> None:
        self._output.write(text)

    def beep(self) -> None:
        pass

    # ----------------------------------------------------------------------------------
    # Output

    @contextmanager
    def buffering(self) -> Iterator[io.StringIO]:
        """
        Buffer all output made inside a `with renderer.buffering()` block. The
        buffered output is written and flushed upon completion of the block. A
        call to `renderer.clear_buffer()` erases all text buffered so far.
        """
        # Don't cache new self._output in local variable; see clear_buffer() below.
        saved_output = self._output
        self._output = io.StringIO()
        try:
            yield self._output
        finally:
            saved_output.write(self._output.getvalue())
            saved_output.flush()
            self._output = saved_output

    def clear_buffer(self) -> None:
        """Erase output buffered so far."""
        if not isinstance(self._output, io.StringIO):
            raise TypeError('renderer is not buffering')
        self._output = io.StringIO()

    def write(self, text: str = '') -> None:
        """Output the text. This method does not flush the output."""
        if text:
            self._output.write(str(text))

    def writeln(self, text: str = '') -> None:
        """
        Output the text followed by a newline. This method flushes the output
        stream. If that is undesired, consider `buffering()`.
        """
        if text:
            self._output.write(str(text))
        self._output.write('\n')
        self._output.flush()

    def flush(self) -> None:
        """Flush output."""
        self._output.flush()


class StyledRenderer(Renderer):
    """A line-oriented console renderer using ANSI escape codes."""

    @property
    def has_style(self) -> bool:
        return True

    def set_window_title(self, text: str) -> None:
        """Save and update window title. This method flushes output."""
        if self.is_interactive:
            self._output.write(f'{_CSI}22;0t{_OSC}0;{text}{_ST}')
            self._output.flush()

    def restore_window_title(self) -> None:
        """Restore previously saved window title. This method flushes output."""
        if self.is_interactive:
            self._output.write(f'{_OSC}0;{_ST}{_CSI}23;0t')
            self._output.flush()

    def _query(self, text: str) -> bytes:
        if not text.startswith('\x1B'):
            raise ValueError(f'query {text} is not an escape sequence')
        with self.reader() as reader:
            self._output.write(text)
            self._output.flush()
            return reader.read_escape()

    def get_position(self) -> None | tuple[int, int]:
        """Get current cursor position. This method flushes output."""
        response = self._query(f'{_CSI}6n')
        if not response.startswith(b'\x1B[') or not response.endswith(b'R'):
            return None
        row, _, column = response[2:-1].partition(b';')
        return int(row), int(column)

    def adjust_column(self, column: int) -> None:
        self._output.write(_CHA(column))

    def faint(self, text:str) -> None:
        self._output.write(f'{self._theme.faint}{text}{Style.RESET}')

    def em(self, text: str) -> None:
        self._output.write(Style.italic(text))

    def strong(self, text: str) -> None:
        self._output.write(Style.bold(text))

    def link(self, href: str, text: None | str = None) -> None:
        self._output.write(Style.link(href, text))

    def emit_legend(self, text: str) -> None:
        self._output.write(f'{self._theme.legend}{text}{Style.RESET}')

    def emit_heading(self, text: str) -> None:
        self._output.write(f'{self._theme.heading}{text}{Style.RESET}')

    def emit_blot(self, text: str, padding: Padding, width: int) -> None:
        self._output.write(''.join([
            text,
            (
                self._theme.blot_highlight
                if padding is Padding.BACKGROUND
                else self._theme.blot_obstruction
            ),
            padding.value * width,
            Style.RESET
        ]))

    def emit_error(self, text: str) -> None:
        """Emit the error text. This method flushes output."""
        self._output.write(f'{self._theme.error}{text}{Style.RESET}')
        self._output.flush

    def beep(self) -> None:
        """Ring the terminal's bell. This method flushes output."""
        self._output.write('\a')
        self._output.flush()
