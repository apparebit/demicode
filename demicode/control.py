from enum import Enum
import os
import sys
import time
from typing import Callable

from .render import Renderer


__all__ = (
    'Action',
    'read_keypress_action',
    'read_line_action'
)


class Action(Enum):
    ERROR = 665
    BACKWARD = -1
    TERMINATE = 0
    FORWARD = 1

    @property
    def error(self) -> bool:
        return self is Action.ERROR

    @property
    def backward(self) -> bool:
        return self is Action.BACKWARD

    @property
    def terminate(self) -> bool:
        return self is Action.TERMINATE

    @property
    def forward(self) -> bool:
        return self is Action.FORWARD


_KEY_HINTS: tuple[str,...] = (
    ' \u2B05 | ‹q›uit | \u2B95  ',
    ' \u2B05 | e‹x›it | \u2B95  ',
    ' \u2B05 | ‹escape› | \u2B95  ',
    ' \u2B05 | ‹control-c› | \u2B95  ',
)

_LINE_HINTS: tuple[str,...] = (
    ' [ ‹p›revious | ‹q›uit | ‹n›ext ] ‹return› ',
    ' [ ‹p›revious | ‹q›uit | ‹f›orward ] ‹return› ',
    ' [ ‹b›ackward | ‹q›uit | ‹f›orward ] ‹return› ',
    ' [ ‹b›ackward | ‹q›uit | ‹n›ext ] ‹return› ',
    ' [ ‹b›ackward | e‹x›it | ‹n›ext ] ‹return› ',
    ' [ ‹b›ackward | e‹x›it | ‹f›orward ] ‹return› ',
    ' [ ‹p›revious | e‹x›it | ‹f›orward ] ‹return› ',
    ' [ ‹p›revious | e‹x›it | ‹n›ext ] ‹return› ',
)


def pick_hint(hints: tuple[str,...]) -> str:
    """Live a little! 🤪"""
    return hints[int(time.time()) % len(hints)]


# Make function safe to name on all operating systems.
read_key_action: None | Callable[[Renderer], Action] = None


if sys.platform in ('linux', 'darwin'):

    import termios
    import tty

    def read_key_action(renderer: Renderer, /) -> Action:
        """Read next action using raw standard input."""
        sys.stdout.write(renderer.hint(pick_hint(_KEY_HINTS)))
        sys.stdout.flush()

        old_settings = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin.fileno())
        try:
            nib = os.read(sys.stdin.fileno(), 3).decode()
            # print(' '.join(f'U+{ord(c):04X}' for c in nib))
        except KeyboardInterrupt:
            return Action.TERMINATE
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

        # Terminate line with key hint after all.
        sys.stdout.write('\n')
        sys.stdout.flush()

        # Turn key into action. Nibs of 3 characters start with 0x1B 0x5B.
        nib_length = len(nib)
        if nib_length == 3:
            key = ord(nib[2])
            if key == 0x44: # Cursor left
                return Action.BACKWARD
            if key == 0x43: # Cursor right
                return Action.FORWARD
            if key == 0x5A: # Shift-Tab
                return Action.BACKWARD
        elif nib_length == 1:
            key = ord(nib[0])
            # B/b for backward, P/p for previous, <delete>
            if key in (0x42, 0x62, 0x50, 0x70, 0x7F):
                return Action.BACKWARD
            # <tab>/<return>/<space>, F/f for forward, N/n for next
            if key in (0x09, 0x0A, 0x20, 0x46, 0x66, 0x4E, 0x6E):
                return Action.FORWARD
            # <escape>, Q/q for quit, X/x for exit
            if key in (0x1B, 0x51, 0x71, 0x58, 0x78):
                return Action.TERMINATE

        return Action.ERROR


def read_line_action(renderer: Renderer, /) -> Action:
    """Read next action using Python's line-oriented input() builtin."""
    try:
        s = input(renderer.hint(pick_hint(_LINE_HINTS))).lower()
    except KeyboardInterrupt:
        return Action.TERMINATE
    if s in ('q', 'quit', 'x', 'exit'):
        return Action.TERMINATE
    if s in ('', ' ', '\t', 'n', 'next', 'f', 'forward'):
        return Action.FORWARD
    if s in ('p', 'prev', 'previous', 'b', 'back', 'backward'):
        return Action.BACKWARD

    return Action.ERROR
