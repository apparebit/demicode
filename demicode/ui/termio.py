from collections.abc import Iterator
from contextlib import contextmanager
import enum
import io
import os
import select
import shutil
import sys
import termios
import time
import tty
from typing import cast, ClassVar, Literal, Never, Self, TextIO


CSI = '\x1b['
bCSI = b'\x1b['
DCS = '\x1bP'
OSC = '\x1b]'
ST = '\x1b\\'


def join(*fragments: str) -> str:
    return ''.join(fragments)


class BatchMode(enum.Enum):
    NOT_SUPPORTED = 0
    ENABLED = 1
    DISABLED = 2
    UNDEFINED = 3
    PERMANENTLY_DISABLED = 4

    def is_supported(self) -> bool:
        return self is BatchMode.ENABLED or self is BatchMode.DISABLED

    def is_enabled(self) -> bool:
        return self is BatchMode.ENABLED

    def is_disabled(self) -> bool:
        return self is not BatchMode.ENABLED


class TermIO:
    """
    A higher-level interface to the terminal.

    In general, methods that write to the terminal do *not* flush the output.
    However, if a method name contains `request`, the method flushes the output
    after writing the request.

    TODO: Figure out Windows support.
    """

    def __init__(
        self,
        input: None | TextIO = None,
        output: None | TextIO = None
    ) -> None:
        self._input = input or sys.stdin
        self._output = output or sys.stdout
        assert self._input.isatty()
        assert self._output.isatty()

        #self._original_input_attr = termios.tcgetattr(self._input.fileno())
        #self._original_output = self._output

        self.update_size()
        self._is_cbreak_mode = False
        self._buffer_level = 0

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    def update_size(self) -> tuple[int, int]:
        """Get the current terminal size."""
        if self._output != sys.__stdout__:
            # Try os.get_terminal_size() for accurate answer
            try:
                self._width, self._height = os.get_terminal_size(self._output.fileno())
                return self._width, self._height
            except OSError:
                pass

        # Live with shutil.get_terminal_size()
        self._width, self._height = shutil.get_terminal_size()
        return self._width, self._height

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~
    # Basic Support for Reading

    def is_break_mode(self) -> bool:
        """
        Determine whether the terminal is in cbreak mode, which is necessary for
        reading the reports resulting from requests.
        """
        return self._is_cbreak_mode

    @contextmanager
    def cbreak_mode(self) -> Iterator[Self]:
        """
        Put the terminal into cbreak mode suitable for reading individual key
        strokes. This mode is necessary for reading the reports resulting from
        requests.
        """
        if self._is_cbreak_mode:
            raise ValueError(f'terminal already is in cbreak mode')

        fileno = self._input.fileno()
        settings = termios.tcgetattr(fileno)
        self._is_cbreak_mode = True
        tty.setcbreak(fileno)
        try:
            yield self
        finally:
            termios.tcsetattr(fileno, termios.TCSADRAIN, settings)
            self._is_cbreak_mode = False

    def check_cbreak_mode(self) -> Self:
        """Check that the terminal is in cbreak mode."""
        if not self._is_cbreak_mode:
            raise AssertionError('terminal not in cbreak mode')
        return self

    def read(self, /, length: int = 3, timeout: float = 0) -> bytes:
        """Read from this terminal, which must be in cbreak mode."""
        self.check_cbreak_mode()
        fileno = self._input.fileno()
        if timeout > 0:
            ready, _, _ = select.select([fileno], [], [], timeout)
            if not ready:
                raise TimeoutError()
        return os.read(fileno, length)

    ESCAPE_TIMEOUT: ClassVar[float] = 0.5

    def read_escape(self) -> bytes:
        """
        Read an escape sequence from this terminal, which must be in cbreak
        mode.
        """
        self.check_cbreak_mode()
        buffer = bytearray()

        def next_byte() -> int:
            b = self.read(length=1, timeout=self.ESCAPE_TIMEOUT)[0]
            buffer.append(b)
            return b

        def bad_byte(b: int) -> Never:
            raise ValueError(f'unexpected key code 0x{b:02X}')

        # TODO: Support ESC, CAN, SUB for cancellation

        b = next_byte()
        if b != 0x1B:
            bad_byte(b)

        # CSI Control Sequence
        # --------------------

        b = next_byte()
        if b == 0x5B:  # [
            b = next_byte()
            while 0x30 <= b <= 0x3F:
                b = next_byte()
            while 0x20 <= b <= 0x2F:
                b = next_byte()
            if 0x40 <= b <= 0x7E:
                return bytes(buffer)
            bad_byte(b)

        # DCS/SOS/OSC/PM/APC Control Sequence (Ending in ST)
        # --------------------------------------------------

        if b in (0x50, 0x58, 0x5D, 0x5E, 0x5F):  # P,X,],^,_
            b = next_byte()
            while b not in (0x07, 0x1B):
                b = next_byte()
            if b == 0x07:
                return bytes(buffer)
            b = next_byte()
            if b == 0x5C:  # \\
                return bytes(buffer)
            bad_byte(b)

        # Escape Sequence
        # ---------------

        while 0x20 <= b <= 0x2F:
            b = next_byte()
        if 0x30 <= b <= 0x7E:
            return bytes(buffer)
        bad_byte(b)

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~
    # Basic Support for Writing

    def write(self, text: str) -> Self:
        """Write out all of the text. Do not flush."""
        remaining = len(text)
        while remaining > 0:
            remaining -= self._output.write(text[-remaining:])
        return self

    def emit(self, *esc_parts: int | str) -> Self:
        """
        Write the stringified and joined escape sequence to the terminal. Do not
        flush. This method must not be used for content, only escape sequences.
        """
        return self.write(''.join(str(p) for p in esc_parts))

    def flush(self) -> Self:
        """Flush the output."""
        self._output.flush()
        return self

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~
    # Basic Support for Requests and Reports

    def raw_request(self, *query: str) -> None | bytes:
        """
        Submit the given request and return the resulting report. This method
        does flush the output. It returns `None` upon timing out. The terminal
        must be in cbreak mode.
        """
        self.check_cbreak_mode().emit(*query).flush()
        try:
            return self.read_escape()
        except TimeoutError:
            return None

    def request_text(self, *query: str, prefix: str, suffix: str) -> None | str:
        """
        Submit the given request, convert the resulting report to Unicode, check
        the text for prefix and suffix, and return the intermediate text.
        """
        if (report := self.raw_request(*query)) is None:
            return None
        report = report.decode('utf8')
        if not report.startswith(prefix) or not report.endswith(suffix):
            return None
        return report[len(prefix) : -len(suffix)]

    def request_numbers(self, *query: str, prefix: bytes, suffix: bytes) -> list[int]:
        """
        Submit the given request, check the resulting report for prefix and
        suffix, split the intermediate bytes by semicolons, and return the parts
        converted to integers.
        """
        if (report := self.raw_request(*query)) is None:
            return []
        if not report.startswith(prefix) or not report.endswith(suffix):
            return []
        return [int(num) for num in report[len(prefix) : -len(suffix)].split(b';')]

    def request_terminal_version(self) -> None | str:
        """Request a report with the terminal version."""
        return self.request_text(CSI, '>q', prefix=join(DCS, '>|'), suffix=ST)

    def request_cursor_position(self) -> None | tuple[int, int]:
        """Request a report with the cursor position in (x, y) order."""
        numbers = self.request_numbers(CSI, '6n', prefix=bCSI, suffix=b'R')
        return None if len(numbers) != 2 else (numbers[1], numbers[0])

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~
    # Buffering and Batching Writes

    @contextmanager
    def buffer(self) -> Iterator[Self]:
        """
        Redirect all output, including control sequences, into a buffer. If the
        context manager exits normally, it writes the buffer's contents to the
        original output stream. Otherwise, it discards them.
        """
        saved_output = self._output
        self._buffer_level += 1
        self._output = io.StringIO()
        try:
            yield self
        except:
            self._output.close()  # discard buffer contents
            raise  # reraise exception
        finally:
            nested_output = self._output
            self._output = saved_output
            self._buffer_level -= 1
            if not nested_output.closed:
                shutil.copyfileobj(nested_output, saved_output)

    def is_buffering(self) -> bool:
        """Determine whether this terminal control instance is buffering."""
        return self._buffer_level > 0

    def get_buffer(self) -> str:
        """Get the current buffer contents."""
        if not self.is_buffering():
            raise AssertionError(
                'get_buffer() only works inside "with buffer()" block')
        return cast(io.StringIO, self._output).getvalue()

    def discard_buffer(self) -> Self:
        """Discard the current buffer contents but keep on buffering."""
        if not self.is_buffering():
            raise AssertionError(
                'discard_buffer() only works inside "with buffer()" block')
        self._output.close()
        self._output = io.StringIO()
        return self

    @contextmanager
    def batch(self) -> Iterator[Self]:
        """
        Batch all updates. The context manager instructs the terminal to delay
        any updates until the with block is finished. Use `request_batch_mode()`
        to determine whether a terminal supports batching.
        """
        self.emit(CSI, '?2026h').flush()
        try:
            yield self
        finally:
            self.emit(CSI, '?2026l').flush()

    def request_batch_mode(self) -> BatchMode:
        """Request the current batch mode."""
        # https://gist.github.com/christianparpart/d8a62cc1ab659194337d73e399004036
        report = self.request_numbers(
            CSI, '?2026$p', prefix=b'\x1b[?2026;', suffix=b'$y')
        return BatchMode(report[0]) if len(report) == 1 else BatchMode.NOT_SUPPORTED

    def is_batching(self) -> bool:
        return self.request_batch_mode().is_enabled()

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~
    # Positioning the Cursor, Erasing Content, and Styling Content

    def set_cursor_column(self, column: int | Literal[''] = '') -> Self:
        """Set the cursor column."""
        return self.emit(CSI, column, 'G')

    def set_cursor_position(
        self, row: int | Literal[''] = '', column: int | Literal[''] = ''
    ) -> Self:
        """Set the cursor position."""
        return self.emit(CSI, row, ';', column, 'H')

    def home(self) -> Self:
        """Set cursor position to (1, 1)."""
        return self.emit(CSI, ';H')

    def clear(self) -> Self:
        """Erase the display."""
        return self.emit(CSI, '2J')

    def linestart(self) -> Self:
        return self.emit(CSI, 'G')

    def clearline(self) -> Self:
        return self.emit(CSI, '2K')

    def style(self, *parameters: int | Literal['']) -> Self:
        """Modify the style, including text appearance and colors."""
        return self.emit(CSI, ';'.join(str(p) for p in parameters), 'm')

    def reset_style(self) -> Self:
        """Reset the style."""
        return self.style(0)

    def bell(self) -> Self:
        """Ring terminal bell."""
        return self.emit('\a')

    def link(self, text: str, href: str, id: None | str = None) -> Self:
        """Mark a hyperlink."""
        # https://gist.github.com/egmontkob/eb114294efbcd5adb1944c9f3cb5feda
        code = f'8;id={id};' if id else '8;;'
        return self.emit(OSC, code, href, ST).write(text).emit(OSC, '8;;', ST)

    # iTerm
    # OSC 1337 ; StealFocus ST
    # OSC 1337 ; CurrentDir=[current directory] ST

    # VSCode shell integration   OSC 633 ; [code]  ST
    #   OSC 633 ; A ST  Mark prompt start
    #   OSC 633 ; B ST  Mark prompt end
    #   OSC 633 ; C ST  Mark pre-execution
    #   OSC 633 ; D [; exitcode] ST  Mark execution finished
    #   OSC 633 ; E ; commandline ST  Set the command line
    #       \xAB to escape ASCII  notably newline and semicolon
    #   OSC 633 ; P ; key = value ST  Set a property
    #        Cwd    current directory
    #        IsWindows    uses Windows backend

    #   OSC 133 ; A ST    Mark prompt start
    #   OSC 133 ; B ST    Mark prompt end
    #   OSC 133 ; C ST    Mark pre-execution
    #   OSC 133 ; D [; exitcode] ST  Mark execution finished

    #   OSC 1337 ; SetMark ST  set mark to left of line   ctrl/cmd up/down

    # https://gitlab.freedesktop.org/Per_Bothner/specifications/blob/master/proposals/semantic-prompts.md

    #   OCS 6 ; FILE_URL ST  document    (Terminal.app)
    #   OSC 7 ; FILE_URL ST  working directory   (Terminal.app)

    # https://wezfurlong.org/wezterm/escape-sequences.html#operating-system-command-sequences

    #   OSC 9;9; CWD ST (ConEmu)
    # https://conemu.github.io/en/AnsiEscapeCodes.html#ConEmu_specific_OSC

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~

    @contextmanager
    def window_title(self, title: str) -> Iterator[Self]:
        """
        Use a different window title. On entry, this context manager pushes the
        current window title on the terminal's stack on entry and pops it again
        during exit.
        """
        # Save window title on stack, then update window title
        self.emit(CSI, '22;2t', OSC, '0;', title, ST).flush()
        try:
            yield self
        finally:
            self.emit(CSI, '23;2t').flush()

    @contextmanager
    def alternate_screen(self) -> Iterator[Self]:
        """Switch to the terminal's alternate (unbuffered) screen."""
        self.emit(CSI, '?1049h').flush()
        try:
            yield self
        finally:
            self.emit(CSI, '?1049l').flush()

    @contextmanager
    def hidden_cursor(self) -> Iterator[Self]:
        """Make cursor invisible."""
        self.emit(CSI, '?25l')
        try:
            yield self
        finally:
            self.emit(CSI, '?25h')

    @contextmanager
    def bracketed_paste(self) -> Iterator[Self]:
        # https://gitlab.com/gnachman/iterm2/-/wikis/Paste-Bracketing
        self.emit(CSI, '?2004h')
        try:
            yield self
        finally:
            self.emit(CSI, '?2004l')

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~

    TICKS_PER_SECOND: ClassVar[int] = 5
    TICKS_PER_BLINK: ClassVar[int] = 3

    def resize_interactively(self, width: int = -1, height: int = -1) -> Self:
        if width != -1 or height != -1:
            assert width >= 20
            assert height >= 5

        w, h = self.update_size()
        if w == width and h == height:
            return self

        ticks = -1
        cursor = ' '

        with self.alternate_screen(), self.hidden_cursor():
            self.home().clear()
            if width == -1:
                self.write('\n    The terminal size is:\n\n')
            else:
                self.write(
                    f'\n    Please adjust the terminal size to {width}x{height}:\n\n')
            self.flush()

            while True:
                w, h = self.update_size()
                if w == width and h == height:
                    return self

                w = f'{CSI}{"38;5;244" if w ==  width else "1"}m{w:3d}{CSI}0m'
                h = f'{CSI}{"38;5;244" if h == height else "1"}m{h:3d}{CSI}0m'

                ticks += 1
                if ticks % self.TICKS_PER_BLINK == 0:
                    cursor = '█' if cursor == ' ' else ' '

                self.linestart().clearline().write(f'        {w}x{h} {cursor}').flush()
                time.sleep(1 / self.TICKS_PER_SECOND)
