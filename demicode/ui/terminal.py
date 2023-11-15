import base64
from collections.abc import Iterator
import dataclasses
import os
import subprocess
import struct
import sys
import time
from typing import ClassVar, Self

from .termio import TermIO


@dataclasses.dataclass(frozen=True, slots=True)
class Terminal:
    """A terminal emulator."""

    name: str
    bundle: str
    version: None | str = None

    @property
    def long_name(self) -> str:
        if self.is_vscode():
            return 'Visual Studio Code'
        return self.name

    @property
    def display(self) -> str:
        display = self.long_name
        if self.version:
            display = f'{display} ({self.version})'
        return display

    def is_versioned(self) -> bool:
        return self.version is not None

    def without_version(self) -> Self:
        return type(self)(self.name, self.bundle)

    def with_version(self, version: str) -> Self:
        return type(self)(self.name, self.bundle, version)

    def is_iterm(self) -> bool:
        return self.bundle == 'com.googlecode.iterm2'

    def is_unknown(self) -> bool:
        return self.bundle == 'known.unknown'

    def is_vscode(self) -> bool:
        return self.bundle == 'com.microsoft.VSCode'

    def is_warp(self) -> bool:
        return self.bundle == 'dev.warp.Warp-Stable'

    _unknown: ClassVar[None | Self] = None

    @classmethod
    def unknown(cls) -> Self:
        if cls._unknown is None:
            cls._unknown = cls('--unknown--', 'known.unknown')
        return cls._unknown

    _registry: ClassVar[None | dict[str, Self]] = None

    @classmethod
    def registry(cls) -> dict[str, Self]:
        if cls._registry is None:
            cls._registry = {}

            for names in (
                # An application's name, its macOS bundle ID, any other names:
                #   - Alacritty and WezTerm use a different reverse-DNS name
                #     for Linux desktops
                #   - iTerm's latest version is 3.4.22, but somehow the '2' is
                #     sticky at least in the main menu
                #   - Terminal.app is just a nickname whereas Apple_Terminal
                #     appears in the TERM_PROGRAM environment variable
                #   - Visual Studio Code is VSCode's full name
                #   - WarpTerminal appears in TERM_PROGRAM
                ('Alacritty', 'org.alacritty', 'org.alacritty.Alacritty'),
                ('Hyper', 'co.zeit.hyper'),
                ('iTerm', 'com.googlecode.iterm2', 'iTerm2'),
                ('Kitty', 'net.kovidgoyal.kitty'),
                ('Rio', 'com.raphaelamorim.rio'),
                ('Terminal', 'com.apple.Terminal', 'Terminal.app', 'Apple_Terminal'),
                ('VSCode', 'com.microsoft.VSCode', 'Visual Studio Code'),
                ('Warp', 'dev.warp.Warp-Stable', 'WarpTerminal'),
                ('WezTerm', 'com.github.wez.wezterm', 'org.wezfurlong.wezterm'),
            ):
                keys = [n.casefold() for n in names]
                for key, name in zip(keys, names):
                    if key in cls._registry:
                        raise AssertionError(f'duplicate terminal name {name}')
                terminal = cls(*names[:2])
                for key in keys:
                    cls._registry[key] = terminal

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
        terminal = cls.registry().get(ident.casefold())
        return terminal.long_name if terminal else ident

    @classmethod
    def resolve(cls, ident: str) -> Self:
        terminal = cls.registry().get(ident.casefold())
        return terminal if terminal else cls(ident, ident)


    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~

    @classmethod
    def from_bundle_id(cls) -> None | Self:
        """Resolve the terminal name based on the macOS bundle identifier"""
        bundle = os.getenv('__CFBundleIdentifier')
        return cls.resolve(bundle) if bundle else None

    def with_bundle_version(self) -> Self:
        """Add in the terminal version based on the macOS bundle identifier."""
        if sys.platform != 'darwin':
            raise NotImplementedError('only supported on macOS')

        paths = subprocess.run(
            ["mdfind", f"kMDItemCFBundleIdentifier == '{self.bundle}'"],
            stdout=subprocess.PIPE,
            encoding='utf8',
        ).stdout.splitlines()
        if len(paths) != 1:
            return self

        version = subprocess.run(
            ['mdls', '-name', 'kMDItemVersion', '-raw', paths[0]],
            stdout=subprocess.PIPE,
            encoding='utf8',
        ).stdout
        return self.with_version(version) if version else self

    @classmethod
    def from_bundle(cls) -> None | Self:
        """
        Resolve the terminal name and version based on the macOS bundle
        identifier.
        """
        t = cls.from_bundle_id()
        if t is None:
            return None
        return t.with_env_version() if t.is_warp() else t.with_bundle_version()

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~

    @classmethod
    def from_env_name(cls) -> None | Self:
        """
        Resolve the terminal name based on the `TERM_PROGRAM` environment
        variable.
        """
        program = os.getenv('TERM_PROGRAM')
        return cls.resolve(program) if program else None

    def with_env_version(self) -> Self:
        """
        Add in the terminal version based on the `TERM_PROGRAM_VERSION`
        environment variable.
        """
        version = os.getenv('TERM_PROGRAM_VERSION')
        return self.with_version(version) if version else self

    @classmethod
    def from_env(cls) -> None | Self:
        """
        Resolve the terminal name and version based on the `TERM_PROGRAM` and
        `TERM_PROGRAM_VERSION` environment variables.
        """
        terminal = cls.from_env_name()
        return terminal.with_env_version() if terminal else None

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~

    @classmethod
    def from_xtversion(cls, termio: None | TermIO = None) -> None | Self:
        """
        Resolve the terminal name and version based on the XTVERSION control
        sequence.
        """
        termio = termio or TermIO()
        try:
            with termio.cbreak_mode():
                report = termio.request_terminal_version()
        except TimeoutError:
            return None
        if report is None:
            return None
        if report[-1] == ')':
            name, _, version = report.rpartition('(')
            version = version[1:-1]
        else:
            name, _, version = report.partition(' ')
        terminal = cls.resolve(name)
        return terminal.with_version(version) if version else terminal

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~

    @classmethod
    def current(cls, termio: None | TermIO = None) -> Self:
        """Resolve the terminal name and version."""
        return (
            cls.from_xtversion(termio)
            or cls.from_bundle()
            or cls.from_env()
            or cls.unknown()
        )

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~

    @classmethod
    def nonce(cls) -> str:
        value = (
            base64.b32encode(struct.pack('>I', int(time.time())))
            .decode('ascii')
            .lower()
        )
        pad = value.index('=')
        return value[:pad] if pad >= 0 else value

    def filename(self, label: str, nonce: str, suffix: str) -> str:
        return f'{label}-{nonce}-{self.name.lower()}{suffix}'


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
    tn = Terminal.current()
    if not show_all:
        print(tn.display)
        sys.exit(0)

    l1 = l2 = l3 = ln = 0
    t1 = Terminal.from_bundle() or Terminal.unknown()
    l1 = len(t1.display)
    t2 = Terminal.from_xtversion() or Terminal.unknown()
    l2 = len(t2.display)
    t3 = Terminal.from_env() or Terminal.unknown()
    l3 = len(t3.display)

    width = 9 + max(l1, l2, l3)
    termio.writeln('bundle:  ' + (t1.display if t1 else ''))
    termio.writeln('  ansi:  ' + (t2.display if t2 else ''))
    termio.writeln('   env:  ' + (t3.display if t3 else ''))
    termio.writeln("─" * width)
    termio.writeln(' total:  ' + (tn.display if tn else ''))
