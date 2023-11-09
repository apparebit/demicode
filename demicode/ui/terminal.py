from collections.abc import Iterator
import dataclasses
import os
import subprocess
import sys
from typing import ClassVar, Self

from .termio import TermIO


@dataclasses.dataclass(frozen=True, slots=True)
class Terminal:
    """
    The many names of a terminal emulator:

     - `name` is a concise but memorable identifier;
     - `display` is the less concise version, at least for `VSCode`;
     - `nickname` is the slightly more concise, lower case version;
     - `bundle` serves as a unique ID on macOS, is reminiscent of DNS;
     - `TERM_PROGRAM` may use an altogether different identifier, only used for
       looking up the terminal's record;

    On macOS, the bundle ID is available through the terminal's
    __CFBundleIdentifier environment variable. Demicode relies on it for
    uniquely identifying terminal applications, even when not running on macOS.
    """

    name: str
    bundle: str
    nickname: str

    @property
    def display(self) -> str:
        return 'Visual Studio Code' if self.is_vscode() else self.name

    def is_iterm(self) -> bool:
        return self.bundle == 'com.googlecode.iterm2'

    def is_vscode(self) -> bool:
        return self.bundle == 'com.microsoft.VSCode'

    _registry: ClassVar[None | dict[str, Self]] = None

    @classmethod
    def registry(cls) -> dict[str, Self]:
        if cls._registry is None:
            cls._registry = {}

            for names in [
                # name, bundle identifier, nickname, TERM_PROGRAM
                ['Alacritty', 'org.alacritty'],
                ['Hyper', 'co.zeit.hyper'],
                ['iTerm2', 'com.googlecode.iterm2', 'iterm', 'iTerm.app'],
                ['Kitty', 'net.kovidgoyal.kitty'],
                ['Rio', 'com.raphaelamorim.rio'],
                ['Terminal', 'com.apple.Terminal', 'terminalapp', 'Apple_Terminal'],
                ['VSCode', 'com.microsoft.VSCode'],
                ['Warp', 'dev.warp.Warp-Stable', 'warp', 'WarpTerminal'],
                ['WezTerm', 'com.github.wez.wezterm'],
            ]:
                if len(names) == 2:
                    names.append(names[0].lower())
                for n in names:
                    assert n not in cls._registry, f'ambiguous terminal identifier {n}'

                terminal = cls(*names[:3])
                for n in names:
                    cls._registry[n] = terminal

        return cls._registry

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


# --------------------------------------------------------------------------------------


def inspect_xtversion(termio: None | TermIO = None) -> tuple[None | str, None | str]:
    termio = termio or TermIO()
    with termio.cbreak_mode():
        report = termio.request_terminal_version()
    if report is None:
        return None, None
    if report[-1] == ')':
        terminal, _, version = report.rpartition('(')
        version = version[1:-1]
    else:
        terminal, _, version = report.partition(' ')
    return Terminal.resolve_name(terminal), version


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


def inspect_env_variables() -> tuple[None | str, None | str]:
    if (terminal := os.getenv('TERM_PROGRAM')):
        terminal = Terminal.resolve_name(terminal)
    version = os.getenv('TERM_PROGRAM_VERSION')
    return terminal or None, version or None


def determine_terminal_version(
    termio: None | TermIO = None
) -> tuple[None | str, None | str]:
    termio = termio or TermIO()
    t, v = inspect_xtversion(termio)
    if t and v:
        return t, v

    t, v = inspect_bundle_id()
    if t and v:
        # The bundle version is horribly outdated.
        if t == 'Warp':
            v = os.getenv('TERM_PROGRAM_VERSION')
        return t, v

    t, v = inspect_env_variables()
    return t, v


def join_terminal_version(terminal: None | str, version: None | str) -> str:
    if terminal is None:
        return 'Unknown Terminal'
    if version is None:
        return terminal
    return f'{terminal} ({version})'


def termid(termio: None | TermIO = None) -> str:
    return join_terminal_version(*determine_terminal_version(termio))


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

    termio = TermIO()
    idn = join_terminal_version(*determine_terminal_version(termio))
    if show_all:
        id1 = join_terminal_version(*inspect_xtversion(termio))
        id2 = join_terminal_version(*inspect_bundle_id())
        id3 = join_terminal_version(*inspect_env_variables())
        width = max(len(id1), len(id2), len(id3), len(idn)) + 8
        print(f'  ansi: {id1}\nbundle: {id2}\n   env: {id3}\n{"─" * width}')
        print(f' combo: {idn}')
    else:
        print(idn)
