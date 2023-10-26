import os
import sys
from typing import TextIO

from .render import Renderer


_CANONICAL_NAME = {
    'org.alacritty': 'Alacritty',
    'Hyper': 'Hyper',
    'co.zeit.hyper': 'Hyper',
    'iTerm2': 'iTerm2',
    'iTerm.app': 'iTerm2',
    'com.googlecode.iterm2': 'iTerm2',
    'kitty': 'Kitty',
    'net.kovidgoyal.kitty': 'Kitty',
    'rio': 'Rio',
    'com.raphaelamorim.rio': 'Rio',
    'Apple_Terminal': 'Terminal.app',
    'com.apple.Terminal': 'Terminal.app',
    'vscode': 'Visual Studio Code',
    'WarpTerminal': 'Warp',
    'dev.warp.Warp-Stable': 'Warp',
    'WezTerm': 'WezTerm',
    'com.github.wez.wezterm': 'WezTerm',
}


def report_xtversion(
    renderer: None | Renderer = None
) -> tuple[None | str, None | str]:
    renderer = Renderer.new() if renderer is None else renderer

    try:
        response = renderer.query('[>q')
    except (NotImplementedError, TimeoutError):
        return None, None
    if not response.startswith(b'\x1BP>|'):
        return None, None
    if not response.endswith(b'\x1B\\'):
        return None, None

    response = response[4:-2]
    if response[-1] == 41:
        parts = response.rsplit(b'(', maxsplit=1)
        if len(parts) != 2:
            return None, None
        terminal = parts[0]
        version = parts[1][:-1]
    else:
        parts = response.rsplit(b' ', maxsplit=1)
        if len(parts) != 2:
            return None, None
        terminal, version = parts

    t = terminal.decode('ascii')
    return _CANONICAL_NAME.get(t, t), version.decode('ascii')


def report_terminal_version(
    renderer: None | Renderer = None
) -> tuple[None | str, None | str]:
    renderer = Renderer.new() if renderer is None else renderer

    terminal = os.getenv('TERM_PROGRAM')
    if terminal is not None:
        terminal = _CANONICAL_NAME.get(terminal, terminal)

    if terminal is None:
        terminal = os.getenv('__CFBundleIdentifier')
        if terminal is not None:
            terminal = _CANONICAL_NAME.get(terminal, terminal)

    version = os.getenv('TERM_PROGRAM_VERSION')

    if terminal is None or version is None:
        t, v = report_xtversion(renderer)
        terminal = terminal or t
        version = version or v

    return terminal, version


def join_terminal_version(terminal: None | str, version: None | str) -> str:
    if terminal is None:
        return 'Unknown Terminal'
    if version is None:
        return terminal
    return f'{terminal} ({version})'


def termid(renderer: None | Renderer = None) -> str:
    return join_terminal_version(*report_terminal_version(renderer))


if __name__ == '__main__':
    def help() -> None:
        print('usage: python -m demicode.terminal [-a]')

    show_all = False
    for arg in sys.argv[1:]:
        if arg == '-h':
            help()
            sys.exit(0)
        elif arg == '-a':
            show_all = True
        else:
            help()
            sys.exit(1)

    renderer = Renderer.new()
    if show_all:
        print(join_terminal_version(*report_xtversion(renderer)))
    print(join_terminal_version(*report_terminal_version(renderer)))


# --------------------------------------------------------------------------------------


class TerminalSizeChecker:
    """Callable to check that terminal size didn't change on every invocation."""

    def __init__(self, output: None | TextIO = None) -> None:
        self._fileno = (output or sys.stdout).fileno()
        self._width, self._height = os.get_terminal_size(self._fileno)

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    def __call__(self) -> None:
        width, height = os.get_terminal_size(self._fileno)
        if self._width != width or self._height != height:
            raise AssertionError(
                f'terminal size changed from {self._width}×{self._height} '
                f'to {width}×{height}'
            )
