import time

from .render import KeyPressReader, Renderer
from .action import Action


__all__ = ("read_key_action", "read_line_action")


_KEY_HINTS: tuple[str, ...] = (
    " \u2B05 | ‹q›uit | \u2B95  ",
    " \u2B05 | e‹x›it | \u2B95  ",
    " \u2B05 | ‹escape› | \u2B95  ",
    " \u2B05 | ‹control-c› | \u2B95  ",
)


_LINE_HINTS: tuple[str, ...] = (
    " [ ‹p›revious | ‹q›uit | ‹n›ext ] ‹return› ",
    " [ ‹p›revious | ‹q›uit | ‹f›orward ] ‹return› ",
    " [ ‹b›ackward | ‹q›uit | ‹f›orward ] ‹return› ",
    " [ ‹b›ackward | ‹q›uit | ‹n›ext ] ‹return› ",
    " [ ‹b›ackward | e‹x›it | ‹n›ext ] ‹return› ",
    " [ ‹b›ackward | e‹x›it | ‹f›orward ] ‹return› ",
    " [ ‹p›revious | e‹x›it | ‹f›orward ] ‹return› ",
    " [ ‹p›revious | e‹x›it | ‹n›ext ] ‹return› ",
)


def _pick_hint(hints: tuple[str, ...]) -> str:
    """Live a little! 🤪"""
    return hints[int(time.time()) % len(hints)]


if KeyPressReader.PLATFORM_SUPPORTED:

    def _to_action(nib: bytes) -> Action:
        """Turn key data into action."""
        nib_length = len(nib)
        if nib_length == 3:
            # For cursor keys leading two bytes are 0x1B 0x5B
            key = nib[2]
            if key == 0x44:  # Cursor left
                return Action.BACKWARD
            if key == 0x43:  # Cursor right
                return Action.FORWARD
            if key == 0x5A:  # Shift-Tab
                return Action.BACKWARD
        elif nib_length == 1:
            key = nib[0]
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

    def read_key_action(renderer: Renderer, /) -> Action:
        """Read next action using raw standard input."""
        renderer.faint(_pick_hint(_KEY_HINTS))
        renderer.flush()
        with renderer.reader() as reader:
            try:
                while True:
                    action = _to_action(reader.read())
                    if action is not Action.ERROR:
                        break
                    renderer.beep()
            except KeyboardInterrupt:
                return Action.TERMINATE

        # Terminate line with key hint after all. Return error-free action.
        renderer.newline()
        return action

else:

    def read_key_action(renderer: Renderer, /) -> Action:
        raise NotImplementedError()


def read_line_action(renderer: Renderer, /) -> Action:
    """Read next action using Python's line-oriented input() builtin."""
    try:
        renderer.faint(_pick_hint(_LINE_HINTS))
        s = input().lower()
    except KeyboardInterrupt:
        return Action.TERMINATE
    if s in ("q", "quit", "x", "exit"):
        return Action.TERMINATE
    if s in ("", " ", "\t", "n", "next", "f", "forward"):
        return Action.FORWARD
    if s in ("p", "prev", "previous", "b", "back", "backward"):
        return Action.BACKWARD

    return Action.ERROR
