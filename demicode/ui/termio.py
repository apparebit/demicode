from collections.abc import Iterator
from contextlib import contextmanager, suppress
import enum
import io
import os
import select
import shutil
import sys
import termios
import time
import tty
from typing import Callable, cast, ClassVar, Literal, Never, Self, TextIO


__all__ = (
    "BatchMode",
    "TermIO",
)


CSI = "\x1b["
bCSI = b"\x1b["
DCS = "\x1bP"
OSC = "\x1b]"
ST = "\x1b\\"


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
    A convenient interface for terminal I/O.

    In general, methods that write to the terminal do *not* flush the output.
    However, if a method name contains `request`, the method flushes the output
    after writing the request.

    TODO: Figure out Windows support.
    """

    def __init__(
        self,
        input: None | TextIO = None,
        output: None | TextIO = None,
    ) -> None:
        self._input = input or sys.__stdin__
        self._output = output or sys.__stderr__
        self._width, self._height = self.query_size()

        # TODO: Consider querying terminal attributes via termios.tcgetattr()
        self._cbreak_mode = False
        self._batching = False
        self._buffer_level = 0

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    def query_size(self) -> tuple[int, int]:
        """Get the current terminal size without changing internal state."""
        try:
            return os.get_terminal_size(self._output.fileno())
        except OSError:
            return 80, 24

    def update_size(self) -> tuple[int, int]:
        self._width, self._height = self.query_size()
        return self._width, self._height

    def check_same_size(self) -> Self:
        """Validate that the terminal size has not changed."""
        width, height = self.query_size()
        if self._width != width or self._height != height:
            raise AssertionError(
                f"terminal size changed from {self._width}×{self._height} "
                f"to {width}×{height}"
            )
        return self

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~
    # Basic Support for Reading

    def is_cbreak_mode(self) -> bool:
        """
        Determine whether the terminal is in cbreak mode, which is necessary for
        reading the reports resulting from requests.
        """
        return self._cbreak_mode

    @contextmanager
    def cbreak_mode(self) -> Iterator[Self]:
        """
        Put the terminal into cbreak mode. Unlike for cooked mode, a terminal in
        cbreak mode does not wait for the end of line and forwards individual
        keystrokes. Unlike for raw more, a terminal in cbreak mode still handles
        special key combinations such as control-C for to trigger the SIGINT
        signal. An application must enter cbreak mode before reading individual
        keystrokes or issueing requests.
        """
        if sys.platform == "win32":
            raise AssertionError("Windows does not support cbreak mode")
        if self._cbreak_mode:
            raise AssertionError("terminal already is in cbreak mode")

        fileno = self._input.fileno()
        settings = termios.tcgetattr(fileno)
        self._cbreak_mode = True
        tty.setcbreak(fileno)
        try:
            yield self
        finally:
            termios.tcsetattr(fileno, termios.TCSADRAIN, settings)
            self._cbreak_mode = False

    def check_cbreak_mode(self) -> Self:
        """Check that the terminal is in cbreak mode."""
        if sys.platform == "win32":
            raise AssertionError("Windows does not support cbreak mode")
        if not self._cbreak_mode:
            raise AssertionError("terminal not in cbreak mode")
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
            raise ValueError(f"unexpected key code 0x{b:02X}")

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

    def _write(self, text: str) -> Self:
        # I have yet to find Python code using text streams that actually checks
        # the number of characters written. A reality check won't hurt.
        expected = len(text)
        actual = self._output.write(text)
        assert expected == actual
        return self

    def write(self, text: str) -> Self:
        """Write out all of the text. Do not flush."""
        return self._write(text)

    def writeln(self, text: None | str = None) -> Self:
        """
        Write the text followed by a newline character. That character may cause
        the underlying stream to flush itself.
        """
        if text:
            self._write(text)
        return self._write("\n")

    def escape(self, *parts: int | str) -> Self:
        """
        Write the stringified and joined escape sequence to the terminal. Do not
        flush. This method must not be used for content, only escape sequences.
        """
        self._write("".join(str(p) for p in parts))
        return self

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
        try:
            return (
                self
                .check_not_batching()
                .check_not_buffering()
                .check_cbreak_mode()
                .escape(*query)
                .flush()
                .read_escape()
            )
        except TimeoutError:
            return None

    def request_text(self, *query: str, prefix: str, suffix: str) -> None | str:
        """
        Submit the given request, convert the resulting report to Unicode, check
        the text for prefix and suffix, and return the intermediate text.
        """
        if (report := self.raw_request(*query)) is None:
            return None
        report = report.decode("utf8")
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
        return [int(num) for num in report[len(prefix) : -len(suffix)].split(b";")]

    def request_terminal_version(self) -> None | str:
        """Request a report with the terminal version."""
        return self.request_text(CSI, ">q", prefix="".join([DCS, ">|"]), suffix=ST)

    def request_cursor_position(self) -> None | tuple[int, int]:
        """Request a report with the cursor position in (x, y) order."""
        numbers = self.request_numbers(CSI, "6n", prefix=bCSI, suffix=b"R")
        return None if len(numbers) != 2 else (numbers[1], numbers[0])

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~
    # Buffering

    def is_buffering(self) -> bool:
        """Determine whether this terminal is buffering."""
        return self._buffer_level > 0

    def check_not_buffering(self) -> Self:
        """Check that this terminal is not currently buffering."""
        if self._buffer_level > 0:
            raise AssertionError("terminal is buffering when it shouldn't")
        return self

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

    def get_buffer(self) -> str:
        """Get the current buffer contents."""
        if not self.is_buffering():
            raise AssertionError('get_buffer() only works inside "with buffer()" block')
        return cast(io.StringIO, self._output).getvalue()

    def discard_buffer(self) -> Self:
        """Discard the current buffer contents but keep on buffering."""
        if not self.is_buffering():
            raise AssertionError(
                'discard_buffer() only works inside "with buffer()" block'
            )
        self._output.close()
        self._output = io.StringIO()
        return self

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~
    # Batching

    @contextmanager
    def batch(self) -> Iterator[Self]:
        """
        Batch all updates. The context manager instructs the terminal to delay
        any updates until the with block is finished. Batch mode cannot be
        nested. Use `request_batch_mode()` to determine whether a terminal
        supports batching.
        """
        self.check_not_batching()
        self._batching = True
        self.escape(CSI, "?2026h").flush()
        try:
            yield self
        finally:
            self.escape(CSI, "?2026l").flush()
            self._batching = False

    def request_batch_mode(self) -> BatchMode:
        """Request the current batch mode."""
        # https://gist.github.com/christianparpart/d8a62cc1ab659194337d73e399004036
        report = self.request_numbers(
            CSI, "?2026$p", prefix=b"\x1b[?2026;", suffix=b"$y"
        )
        return BatchMode(report[0]) if len(report) == 1 else BatchMode.NOT_SUPPORTED

    def is_batching(self) -> bool:
        return self._batching

    def check_not_batching(self) -> Self:
        if self.is_batching():
            raise AssertionError("terminal is batching when it shouldn't")
        return self

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~
    # Positioning the Cursor, Erasing Content, and Styling Content

    def pipe(self, callback: Callable[[Self], None | Self]) -> Self:
        """Invoke the callback on this terminal I/O instance."""
        result = callback(self)
        return result if isinstance(result, TermIO) else self

    def home(self) -> Self:
        """Set cursor position to (1, 1)."""
        return self.escape(CSI, ";H")

    def cursor_position(
        self, row: int | Literal[""] = "", column: int | Literal[""] = ""
    ) -> Self:
        """Set the cursor position."""
        return self.escape(CSI, row, ";", column, "H")

    def cursor_at_column(self, column: int | Literal[""] = "") -> Self:
        """Set the cursor column."""
        return self.escape(CSI, column, "G")

    def cursor_at_line_start(self) -> Self:
        """Move the cursor to the start of the current line."""
        return self.escape(CSI, "G")

    def erase_screen(self) -> Self:
        """Erase the display."""
        return self.escape(CSI, "2J")

    def erase_line(self) -> Self:
        """Clear the current line."""
        return self.escape(CSI, "2K")

    def style(self, *parameters: int | str) -> Self:
        """Modify the style, including text appearance and colors."""
        return self.escape(CSI, ";".join(str(p) for p in parameters), "m")

    def plain(self) -> Self:
        """Reset styles to plain."""
        return self.escape(CSI, "m")

    def bold(self) -> Self:
        """Set style to bold."""
        return self.escape(CSI, "1m")

    def faint(self) -> Self:
        """Set style to faint"""
        return self.escape(CSI, "2m")

    def italic(self) -> Self:
        """Set style to italic."""
        return self.escape(CSI, "3m")

    def bell(self) -> Self:
        """Ring terminal bell."""
        return self.escape("\a")

    def link(self, text: str, href: str, id: None | str = None) -> Self:
        """Mark a hyperlink."""
        # https://gist.github.com/egmontkob/eb114294efbcd5adb1944c9f3cb5feda
        code = f"8;id={id};" if id else "8;;"
        return self.escape(OSC, code, href, ST).write(text).escape(OSC, "8;;", ST)

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
        self.escape(CSI, "22;2t", OSC, "0;", title, ST).flush()
        try:
            yield self
        finally:
            self.escape(CSI, "23;2t").flush()

    @contextmanager
    def alternate_screen(self) -> Iterator[Self]:
        """Switch to the terminal's alternate (unbuffered) screen."""
        self.escape(CSI, "?1049h").flush()
        try:
            yield self
        finally:
            self.escape(CSI, "?1049l").flush()

    @contextmanager
    def hidden_cursor(self) -> Iterator[Self]:
        """Make cursor invisible."""
        self.escape(CSI, "?25l")
        try:
            yield self
        finally:
            self.escape(CSI, "?25h")

    @contextmanager
    def bracketed_paste(self) -> Iterator[Self]:
        """
        Enable [bracketed
        pasting](https://gitlab.com/gnachman/iterm2/-/wikis/Paste-Bracketing).
        """
        self.escape(CSI, "?2004h")
        try:
            yield self
        finally:
            self.escape(CSI, "?2004l")

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~

    TICKS_PER_SECOND: ClassVar[int] = 5
    TICKS_PER_BLINK: ClassVar[int] = 3

    def resize_interactively(self, width: int = -1, height: int = -1) -> Self:
        """
        Help the user resize the terminal by displaying the current size. When
        invoked with target width and height, this method returns once that
        width and height have been reached. Otherwise, the user needs to cancel
        resizing by pressing control-C.
        """
        if width == -1 or height == -1:
            width = height = -1
        else:
            assert width >= 20
            assert height >= 5

        w, h = self.update_size()
        if w == width and h == height:
            print(f'Terminal window already has target size {w:3d}×{h:3d}.')
            return self

        ticks = 0
        cursor = "█"
        linger = 0

        with suppress(KeyboardInterrupt), self.alternate_screen(), self.hidden_cursor():
            self.home().erase_screen()
            if width == -1:
                self.write(
                    "\n    Please adjust the terminal size until you are satisfied."
                    "\n    Then hit control-C to exit.\n\n"
                )
            else:
                self.write(
                    f"\n    Please adjust the terminal size to {width}x{height}.\n\n"
                )
            self.flush()

            while True:
                # Update terminal size
                w, h = self.update_size()
                if w == width and h == height:
                    linger += 1
                    if linger == 3 * self.TICKS_PER_SECOND:
                        return self
                else:
                    linger = 0

                # Simulate blinking cursor
                ticks += 1
                if ticks == self.TICKS_PER_BLINK:
                    ticks = 0
                    cursor = " " if cursor == "█" else "█"

                # Update size display
                self.cursor_at_line_start().erase_line().write("        ")

                if w == width and h == height:
                    self.style("48;5;156").write(f" {w:3d}×{h:3d} ").plain()
                else:
                    (
                        self
                        .style("38;5;244" if w == width else "1")
                        .write(f" {w:3d}")
                        .plain()
                        .write("×")
                        .style("38;5;244" if h == height else "1")
                        .write(f"{h:3d} ")
                        .plain()
                    )

                self.write(f"{cursor}").flush()

                # Nap a little
                time.sleep(1 / self.TICKS_PER_SECOND)
        return self
