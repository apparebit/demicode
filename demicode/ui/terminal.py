from collections.abc import Iterator
import dataclasses
import os
import subprocess
import sys
from typing import ClassVar, Self, TextIO

from .render import Renderer


@dataclasses.dataclass(frozen=True, slots=True)
class Terminal:
    # The application name as it appears in the main menu, usable in AppleScript
    name: str
    # The macOS bundle identifier
    bundle: str
    # A humane nickname, lowercase only
    nickname: str
    # The identifier for AppleScript `activate` commands if different from name
    activation: str

    @property
    def display(self) -> str:
        """Get the terminal's display name."""
        if self.bundle == 'com.microsoft.VSCode':
            return self.activation
        return self.name

    _registry: ClassVar[None | dict[str, Self]] = None

    @classmethod
    def registry(cls) -> dict[str, Self]:
        if cls._registry is None:
            cls._registry = {}

            for names in (
                # The first other name is an informal name for human use.
                # The second other name typically appears in TERM_PROGRAM.
                ('Alacritty', 'org.alacritty'),
                ('Hyper', 'co.zeit.hyper'),
                ('iTerm2', 'com.googlecode.iterm2', 'iterm', 'iTerm.app'),
                ('kitty', 'net.kovidgoyal.kitty'),
                ('Rio', 'com.raphaelamorim.rio'),
                ('Terminal', 'com.apple.Terminal', 'terminalapp', 'Apple_Terminal'),
                ('Code', 'com.microsoft.VSCode', 'vscode'),
                ('Warp', 'dev.warp.Warp-Stable', 'warp', 'WarpTerminal'),
                ('WezTerm', 'com.github.wez.wezterm'),
            ):
                for n in names:
                    assert n not in cls._registry, f'ambiguous terminal identifier {n}'
                name, bundle, *others = names

                nickname = others[0] if others else name.lower()
                assert nickname not in cls._registry,\
                    f'ambiguous terminal identifier {nickname}'

                activation = (
                    'iTerm' if name == 'iTerm2' else
                    'Visual Studio Code' if name == 'Code' else
                    name
                )
                assert activation not in cls._registry,\
                    f'ambiguous terminal identifier {activation}'

                terminal = cls(name, bundle, nickname, activation)
                cls._registry[name] = terminal
                cls._registry[bundle] = terminal
                for n in others:
                    cls._registry[n] = terminal

        return cls._registry

    def is_iterm(self) -> bool:
        return self.bundle == 'com.googlecode.iterm2'

    def is_vscode(self) -> bool:
        return self.bundle == 'com.microsoft.VSCode'

    @classmethod
    def all(cls) -> Iterator[Self]:
        seen: set[Self] = set()
        for terminal in cls.registry().values():
            if terminal in seen:
                continue
            seen.add(terminal)
            yield terminal

    @classmethod
    def resolve_name(cls, ident: str) -> str:
        terminal = cls.registry().get(ident)
        return terminal.display if terminal else ident

    @classmethod
    def resolve(cls, ident: str) -> Self:
        return cls.registry()[ident]


def inspect_env_variables() -> tuple[None | str, None | str]:
    if (terminal := os.getenv('TERM_PROGRAM')):
        terminal = Terminal.resolve_name(terminal)
    version = os.getenv('TERM_PROGRAM_VERSION')
    return terminal or None, version or None


def inspect_xtversion(
    renderer: None | Renderer = None
) -> tuple[None | str, None | str]:
    renderer = Renderer.new() if renderer is None else renderer

    try:
        response = renderer.query('[>q')
    except (NotImplementedError, TimeoutError):
        return None, None
    if not response.startswith(b'\x1BP>|') or not response.endswith(b'\x1B\\'):
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
    return Terminal.resolve_name(t), version.decode('ascii')


def inspect_bundle_id() -> tuple[None | str, None | str]:
    if not (bundle_id := os.getenv('__CFBundleIdentifier')):
        return None, None
    terminal = Terminal.resolve_name(bundle_id)

    paths = subprocess.run(
        ["mdfind", f"kMDItemCFBundleIdentifier == '{bundle_id}'"],
        stdout=subprocess.PIPE,
        encoding='utf8',
    ).stdout.splitlines()

    if not paths:
        return terminal, None

    for path in paths:
        version = subprocess.run(
            ['mdls', '-name', 'kMDItemVersion', '-raw', path],
            stdout=subprocess.PIPE,
            encoding='utf8',
        ).stdout
        if version:
            return terminal, version

    return terminal, None


def report_terminal_version(
    renderer: None | Renderer = None
) -> tuple[None | str, None | str]:
    renderer = Renderer.new() if renderer is None else renderer
    t, v = inspect_xtversion(renderer)
    if t and v:
        return t, v

    t, v = inspect_bundle_id()
    if t and v:
        # The bundle version is horribly outdated.
        if t == 'Warp':
            v = os.getenv('TERM_PROGRAM_VERSION')
        return t, v

    t, v = inspect_env_variables()
    if t and v:
        return t, v

    return None, None


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
    idn = join_terminal_version(*report_terminal_version(renderer))
    if show_all:
        id1 = join_terminal_version(*inspect_env_variables())
        id2 = join_terminal_version(*inspect_xtversion(renderer))
        id3 = join_terminal_version(*inspect_bundle_id())
        width = max(len(id1), len(id2), len(id3), len(idn)) + 8
        print(f'   env: {id1}\n  ansi: {id2}\nbundle: {id3}\n{"─" * width}')
        print(f' combo: {idn}')
    else:
        print(idn)

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
