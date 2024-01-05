import base64
from collections.abc import Iterator
import dataclasses
import os
import subprocess
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
            return "Visual Studio Code"
        return self.name

    @property
    def display(self) -> str:
        display = self.long_name
        if self.version:
            display = f"{display} ({self.version})"
        return display

    def __str__(self) -> str:
        return self.display

    def is_versioned(self) -> bool:
        return self.version is not None

    def without_version(self) -> Self:
        return type(self)(self.name, self.bundle)

    def with_version(self, version: str) -> Self:
        return type(self)(self.name, self.bundle, version)

    def is_iterm(self) -> bool:
        return self.bundle == "com.googlecode.iterm2"

    def is_unknown(self) -> bool:
        return self.bundle == "unknown.unknown"

    def is_vscode(self) -> bool:
        return self.bundle == "com.microsoft.VSCode"

    def is_warp(self) -> bool:
        return self.bundle == "dev.warp.Warp-Stable"

    _unknown: ClassVar[None | Self] = None

    @classmethod
    def unknown(cls) -> Self:
        if cls._unknown is None:
            cls._unknown = cls("someterm", "unknown.unknown")
        return cls._unknown

    _registry: ClassVar[None | dict[str, Self]] = None

    @classmethod
    def registry(cls) -> dict[str, Self]:
        if cls._registry is None:
            cls._registry = {}

            for names in (
                # A terminal's display name, its macOS bundle ID, and any other
                # names:
                #   - Alacritty and WezTerm have different reverse-DNS names for
                #     Linux desktops. We include them as aliases.
                #   - iTerm's latest version is 3.4.22, but somehow the '2' is
                #     sticky at least in the main menu
                #   - Apple's Terminal application uses "Terminal" in the
                #     menubar and "Apple_Terminal" in the TERM_PROGRAM
                #     environment variable. The former is too generic and the
                #     latter awkward, so we use "Terminal.app" instead.
                #   - Visual Studio Code uses the generic "Code" in the menubar
                #     and "Visual Studio Code" on disk. The former is too
                #     generic and the latter a mouthful, so we use "VSCode"
                #     instead.
                #   - Warp uses "WarpTerminal" in TERM_PROGRAM.
                ("Alacritty", "org.alacritty", "org.alacritty.Alacritty"),
                ("Hyper", "co.zeit.hyper"),
                ("iTerm", "com.googlecode.iterm2", "iTerm2"),
                ("Kitty", "net.kovidgoyal.kitty"),
                ("Rio", "com.raphaelamorim.rio"),
                ("Terminal.app", "com.apple.Terminal", "Terminal", "Apple_Terminal"),
                ("VSCode", "com.microsoft.VSCode", "Code", "Visual Studio Code"),
                ("Warp", "dev.warp.Warp-Stable", "WarpTerminal"),
                ("WezTerm", "com.github.wez.wezterm", "org.wezfurlong.wezterm"),
            ):
                keys = [n.casefold() for n in names]
                for key, name in zip(keys, names):
                    if key in cls._registry:
                        raise AssertionError(f"duplicate terminal name {name}")

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
    def resolve(cls, ident: str) -> None | Self:
        return cls.registry().get(ident.casefold())

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~

    @classmethod
    def from_bundle_id(cls) -> None | Self:
        """Resolve the terminal name based on the macOS bundle identifier"""
        if (bundle := os.getenv("__CFBundleIdentifier")) is None:
            return None
        return cls.resolve(bundle)

    def with_bundle_version(self) -> Self:
        """Add in the terminal version based on the macOS bundle identifier."""
        if sys.platform != "darwin":
            raise NotImplementedError("only supported on macOS")

        paths = subprocess.run(
            ["mdfind", f"kMDItemCFBundleIdentifier == '{self.bundle}'"],
            stdout=subprocess.PIPE,
            encoding="utf8",
        ).stdout.splitlines()
        if len(paths) != 1:
            return self

        version = subprocess.run(
            ["mdls", "-name", "kMDItemVersion", "-raw", paths[0]],
            stdout=subprocess.PIPE,
            encoding="utf8",
        ).stdout
        return self.with_version(version) if version else self

    @classmethod
    def from_bundle(cls) -> None | Self:
        """
        Resolve the terminal name and version based on the macOS bundle
        identifier.
        """
        if (terminal := cls.from_bundle_id()) is None:
            return None
        if terminal.is_warp():
            return terminal.with_env_version()
        return terminal.with_bundle_version()

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~

    def with_env_version(self) -> Self:
        """
        Add in the terminal version based on the `TERM_PROGRAM_VERSION`
        environment variable.
        """
        version = os.getenv("TERM_PROGRAM_VERSION")
        return self.with_version(version) if version else self

    @classmethod
    def from_env(cls) -> None | Self:
        """
        Resolve the terminal name and version based on the `TERM_PROGRAM` and
        `TERM_PROGRAM_VERSION` environment variables.
        """
        if (program := os.getenv("TERM_PROGRAM")) is None:
            return None
        if (terminal := cls.resolve(program)) is None:
            return None
        return terminal.with_env_version()

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
        if report[-1] == ")":
            name, _, version = report.rpartition("(")
            version = version[:-1]
        else:
            name, _, version = report.partition(" ")
        if (terminal := cls.resolve(name)) is None:
            return None
        return terminal.with_version(version) if version else terminal

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~

    @classmethod
    def current(cls, termio: None | TermIO = None) -> Self:
        """Resolve the terminal name and version."""
        if (terminal := cls.from_xtversion(termio)) is not None:
            return terminal
        if (terminal := cls.from_bundle()) is not None:
            return terminal
        if (terminal := cls.from_env()) is not None:
            return terminal
        return cls.unknown()

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~

    @classmethod
    def nonce(cls) -> str:
        value = (
            base64.b32encode(int(time.time() * 1000).to_bytes(4))
            .decode("ascii")
            .lower()
        )
        pad = value.index("=")
        return value[:pad] if pad >= 0 else value

    def filename(self, label: str, nonce: str, suffix: str) -> str:
        return f"{label}-{nonce}-{self.name.lower()}{suffix}"


if __name__ == "__main__":

    def help() -> None:
        print("usage: python -m demicode.terminal [-a]")

    show_all = False
    for arg in sys.argv[1:]:
        if arg == "-h":
            help()
            sys.exit(0)
        elif arg == "-a":
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
    termio.writeln("bundle:  " + (t1.display if t1 else ""))
    termio.writeln("  ansi:  " + (t2.display if t2 else ""))
    termio.writeln("   env:  " + (t3.display if t3 else ""))
    termio.writeln("─" * width)
    termio.writeln(" total:  " + (tn.display if tn else ""))
