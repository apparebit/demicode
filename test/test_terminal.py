import sys
import unittest

from demicode.ui.termio import CSI, OSC, ST, join, TermIO


class NotATerminal:
    """A class faking just enough of a stream's interface."""

    def isatty(self) -> bool:
        return True

    def fileno(self) -> int:
        return sys.__stdout__.fileno()

    def write(self, s: str) -> int:
        return len(s)


class TestTerminal(unittest.TestCase):

    def test_output(self) -> None:
        t = TermIO(NotATerminal(), NotATerminal())  # type: ignore

        with t.buffer():
            t.link('home', 'https://apparebit.com')
            self.assertEqual(
                t.get_buffer(),
                join(OSC, '8;;https://apparebit.com', ST, 'home', OSC, '8;;', ST)
            )

        with t.buffer():
            t.home().clear()
            self.assertEqual(t.get_buffer(), join(CSI, ';H', CSI, '2J'))

        with t.buffer():
            t.linestart().clearline()
            self.assertEqual(t.get_buffer(), join(CSI, 'G', CSI, '2K'))

        with t.buffer():
            with t.window_title('WINDOW'):
                t.write('test')
            self.assertEqual(
                t.get_buffer(),
                join(CSI, '22;2t', OSC, '0;WINDOW', ST, 'test', CSI, '23;2t')
            )

        with t.buffer():
            with t.alternate_screen(), t.hidden_cursor():
                t.write('TEST')
            self.assertEqual(
                t.get_buffer(),
                join(CSI, '?1049h', CSI, '?25l', 'TEST', CSI, '?25h', CSI, '?1049l')
            )

        with t.buffer():
            with t.bracketed_paste():
                t.write('PASTE')
            self.assertEqual(
                t.get_buffer(),
                join(CSI, '?2004h', 'PASTE', CSI, '?2004l')
            )
