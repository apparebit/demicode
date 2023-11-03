#!./venv/bin/python

import sys
if sys.platform != 'darwin':
    raise NotImplementedError('script currently supports macOS only!')

import argparse
import dataclasses
import os
from pathlib import Path
import subprocess
from textwrap import dedent
from typing import Any, Self, TypeAlias

from PIL import Image, ImageChops


Rect: TypeAlias = tuple[int, int, int, int]

def _parse_rect(s: str) -> Rect:
    if s.endswith('\n'):
        s = s[:-1]
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1]
    n1, n2, n3, n4 = s.split(',')
    return int(n1), int(n2), int(n3), int(n4)


def _run_applescript(script: str, **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(
        ['osascript', '-s', 's', '-'],
        input=dedent(script).encode('utf8'),   # sets stdin to PIPE
        capture_output=True,           # sets stdout, stderr to PIPE
        **kwargs,
    )

    if result.returncode != 0:
        print('AppleScript failed:')
        print(result.stderr)
        result.check_returncode()

    return result


# --------------------------------------------------------------------------------------


def _is_red_pixel(r: int, g: int, b: int) -> bool:
    return r > 230 and g < 55 and b < 55


_PROBES = 5

def _between_bars(im: Image.Image) -> tuple[None | Rect, None | Rect]:
    step = im.width // (_PROBES + 1)

    def is_red_bar(y: int) -> bool:
        for x in range(1, _PROBES + 1):
            pixel = x * step, y
            color = im.getpixel(pixel)  # type: ignore
            if not _is_red_pixel(*color):  # type: ignore
                return False
        return True

    hit_bar = False
    upper1: None | int = None
    lower1: None | int = None
    upper2: None | int = None
    lower2: None | int = None

    for y in range(im.height):
        bar = is_red_bar(y)

        if not hit_bar:
            if bar:
                hit_bar = True
        elif upper1 is None:
            if not bar:
                upper1 = y
        elif lower1 is None:
            if bar:
                lower1 = y
        elif upper2 is None:
            if not bar:
                upper2 = y
        elif lower2 is None:
            if bar:
                lower2 = y
                break

    r1 = r2 = None
    if upper1 is not None and lower1 is not None:
        r1 = 45, upper1, im.width - 45, lower1
    if upper2 is not None and lower2 is not None:
        r2 = 45, upper2, im.width - 45, lower2
    return r1, r2


def _without_transparency(im: Image.Image) -> Image.Image:
    assert im.mode == 'RGBA'
    bg = Image.new('RGBA', im.size, 'WHITE')
    bg.paste(im, (0, 0), im)
    return bg.convert('RGB')


def _trim(im: Image.Image) -> None | tuple[int, int, int, int]:
    bg = Image.new(im.mode, im.size, im.getpixel((10, 10)))  # type: ignore
    diff = ImageChops.difference(im, bg)
    diff = ImageChops.add(diff, diff, 2.0, -3)
    return diff.getbbox()


# --------------------------------------------------------------------------------------


_NAME_2_TERM: 'dict[str, Terminal]' = {}
_BUNDLE_2_TERM: 'dict[str, Terminal]' = {}
_NICK_2_TERM: 'dict[str, Terminal]' = {}
_ALL_TERMINALS: 'list[Terminal]' = []
_PADDING = 10

@dataclasses.dataclass(frozen=True, slots=True)
class Terminal:
    name: str
    bundle: str
    nickname: str

    @classmethod
    def of(cls, name: str, bundle: str, nickname: str) -> Self:
        if name in _NAME_2_TERM or bundle in _BUNDLE_2_TERM:
            raise ValueError(f'cannot use {name} or {bundle}')

        terminal = cls(name, bundle, nickname)
        _NAME_2_TERM[name] = terminal
        _BUNDLE_2_TERM[bundle] = terminal
        _NICK_2_TERM[nickname] = terminal
        _ALL_TERMINALS.append(terminal)
        return terminal

    @classmethod
    def from_name(cls, name: str) -> Self:
        if name not in _NAME_2_TERM:
            raise ValueError(f'unknown terminal name {name}')
        return _NAME_2_TERM[name]

    @classmethod
    def from_bundle(cls, bundle: str) -> Self:
        if bundle not in _BUNDLE_2_TERM:
            raise ValueError(f'unknown terminal bundle {bundle}')
        return _BUNDLE_2_TERM[bundle]

    @classmethod
    def from_nickname(cls, nickname: str) -> Self:
        if nickname not in _NICK_2_TERM:
            raise ValueError(f'unknown terminal nickname {nickname}')
        return _NICK_2_TERM[nickname]

    def is_current(self) -> None | bool:
        if (current_bundle := os.getenv('__CFBundleIdentifier')):
            return self.bundle == current_bundle
        return None

    def activate(self) -> Self:
        name = 'iTerm' if self.name == 'iTerm2' else self.name
        _run_applescript(f'activate application "{name}"')
        return self

    def make_frontmost(self) -> Self:
        _run_applescript(f"""
            tell application "System Events"
                tell application process "{self.name}"
                    set frontmost to true
                end tell
            end tell
        """)
        return self

    def run(self, cwd: str | Path, cmd: str) -> Self:
        if self.name == 'iTerm2':
            # Make up for iTerm not bringing window to front upon activation.
            extra = ['keystroke "1" using {option down, command down}', 'delay 1']
        else:
            extra = ['', '']

        _run_applescript(f"""\
            tell application "System Events"
                tell application process "{self.name}"
                    delay 3

                    {extra[0]}
                    {extra[1]}

                    keystroke "clear"
                    keystroke return
                    delay 0.5

                    keystroke "cd {cwd}"
                    keystroke return
                    delay 1

                    keystroke "{cmd}"
                    keystroke return
                    delay 2

                    keystroke return
                end tell
            end tell
        """)
        return self

    def window_rect_xywh(self) -> tuple[int, int, int, int]:
        result = _run_applescript(f"""
            tell application "System Events"
                tell application process "{self.name}"
                    set aWindow to its first window
                    set aPosition to value of attribute "AXPosition" of aWindow
                    set aSize to value of attribute "AXSize" of aWindow

                    set TID to AppleScript's text item delimiters
                    set AppleScript's text item delimiters to ","
                    set aString to (aPosition & aSize) as text
                    set AppleScript's text item delimiters to TID

                    return aString
                end tell
            end tell
        """)

        return _parse_rect(result.stdout.decode('utf8'))

    def screenshot_name(self, prefix: str) -> str:
        return f'{prefix}-{self.nickname}-raw.png'

    def screenshot(self, path: str | Path) -> Self:
        subprocess.run([
            'screencapture', '-m',
            '-R', ','.join(str(n) for n in self.window_rect_xywh()),
            str(path),
        ], check=True)
        return self

    def quit(self) -> Self:
        # Directly telling the terminal to quit fails for Kitty
        _run_applescript(f"""\
            tell application "System Events"
                tell application process "{self.name}"
                    keystroke "q" using command down
                end tell
            end tell
        """)
        return self

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~

    def capture_dash_integral(
        self,
        demicode: str | Path,
        screenshot: str | Path
    ) -> Self:
        isrunner = self.is_current()

        if isrunner:
            assert demicode == Path.cwd()
            print('    Print dash-integral')
            subprocess.run(['./script/badterm.py'], check=True)

            print('    Capture screenshot')
            self.screenshot(screenshot)

        else:
            print(f'    Activate {self.name}')
            self.activate()

            print(f'    Print dash-integral in {self.name}')
            self.run(demicode, './script/badterm.py')

            print(f'    Capture screenshot of {self.name}')
            self.screenshot(screenshot)

            print(f'    Quit {self.name}')
            self.quit()
        return self

    def split_dash_integral(self, raw_screenshot: str | Path) -> tuple[Path, Path]:
        with Image.open(raw_screenshot) as im:
            if im.mode == 'RGBA':
                im = _without_transparency(im)

            # Get rectangles between red horizontal bars
            print('    Scan for red horizontal bars')
            r1, r2 = _between_bars(im)
            assert r1 is not None
            assert r2 is not None

            p1: None | Path = None
            p2: None | Path = None

            for rect1 in (r1, r2):
                first = rect1 == r1

                # Crop image to area between bars
                print(f'    Extract image #{2 - first}')
                wim = im.copy() if first else im
                wim = wim.crop(rect1)

                # Get bounding box of text without surrounding all-white margin
                print(f'    Trim image #{2 - first}')
                rect2 = _trim(wim)
                assert rect2 is not None

                # Crop image to bounding box plus padding
                rect2 = (
                    rect2[0] - _PADDING,
                    rect2[1] - _PADDING,
                    rect2[2] + _PADDING,
                    rect2[3] + _PADDING,
                )
                wim = wim.crop(rect2)

                # Save image
                print(f'    Save image #{2 - first}')
                path = Path(raw_screenshot).with_name(
                    f'dash-integral-{self.nickname}-{2 - first}.png'
                )
                wim.save(path)

                if first:
                    p1 = path
                else:
                    p2 = path

            assert p1 is not None
            assert p2 is not None
            return p1, p2


ALACRITTY = Terminal.of('Alacritty', 'org.alacritty', 'alacritty')
HYPER = Terminal.of('Hyper', 'co.zeit.hyper', 'hyper')
ITERM = Terminal.of('iTerm2', 'com.googlecode.iterm2', 'iterm')
KITTY = Terminal.of('kitty', 'net.kovidgoyal.kitty', 'kitty')
RIO = Terminal.of('Rio', 'com.raphaelamorim.rio', 'rio')
TERMINAL_APP = Terminal.of('Terminal', 'com.apple.Terminal', 'terminalapp')
VS_CODE = Terminal.of('Visual Studio Code', 'com.microsoft.VSCode', 'vscode')
WARP = Terminal.of('Warp', 'dev.warp.Warp-Stable', 'warp')
WEZTERM = Terminal.of('WezTerm', 'com.github.wez.wezterm', 'wezterm')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--terminal', '-t')
    options = parser.parse_args()

    demicode_root = Path.cwd()
    assert (demicode_root / 'demicode').is_dir()
    assert (demicode_root / 'doc').is_dir()
    assert (demicode_root / 'script').is_dir()
    screenshot_dir = demicode_root / 'doc' / 'screenshot'
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    if options.terminal:
        terminals = [Terminal.from_nickname(options.terminal)]
    else:
        terminals = _ALL_TERMINALS

    for terminal in terminals:
        print(f'\x1b[1m{terminal.name} ({terminal.bundle})\x1b[0m')
        screenshot_path = screenshot_dir / terminal.screenshot_name('dash-integral')
        if terminal.name == 'Visual Studio Code':
            if not screenshot_path.exists():
                print('Run "script/badterm.py" in Visual Studio Code\'s terminal')
                print(
                    'and save screenshot to '
                    '"doc/screenshot/dash-integral-vscode-raw.png"'
                )
                continue
        else:
            terminal.capture_dash_integral(demicode_root, screenshot_path)
        terminal.split_dash_integral(screenshot_path)


if __name__ == '__main__':
    main()
