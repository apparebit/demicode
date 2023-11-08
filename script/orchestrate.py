#!./venv/bin/python

"""
Illustrate fixed-width rendering issues for nine different terminal emulators by
producing screenshots that are ready for publication. In addition to depending
on the Pillow package for image manipulation, this script makes extensive use of
AppleScript for controlling other applications and the `screencapture` command
line tool for taking screenshots. As a result, it only runs on macOS.
"""

import sys
if sys.platform != 'darwin':
    raise NotImplementedError('script currently supports macOS only!')

import argparse
import os
from pathlib import Path
import subprocess
from textwrap import dedent
from typing import Any, Literal, Self, TypeAlias

from PIL import Image, ImageChops

# Fix Python path to include project root
sys.path.insert(0, str(Path.cwd()))

from demicode.ui.terminal import Terminal as BaseTerminal


# --------------------------------------------------------------------------------------


Rect: TypeAlias = tuple[int, int, int, int]

def _parse_rect(s: str) -> Rect:
    if s.endswith('\n'):
        s = s[:-1]
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1]
    n1, n2, n3, n4 = s.split(',')
    return int(n1), int(n2), int(n3), int(n4)


def _grow_rect(rect: Rect, delta: int) -> Rect:
    return rect[0] - delta, rect[1] - delta, rect[2] + delta, rect[3] + delta


def _format_wh(w: int, h: int) -> str:
    return f'{" " * (5 + 1 + 5 + 1)} {w:5,d}×{h:5,d}'


def _format_xywh(x1: int, y1: int, x2: int, y2: int) -> str:
    return f'{x1:5,d}×{y1:5,d}, {x2-x1:5,d}×{y2-y1:5,d}'


# --------------------------------------------------------------------------------------


def _run_applescript(script: str, **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(
        ['osascript', '-s', 's', '-'],
        input=dedent(script).encode('utf8'),   # sets stdin to PIPE
        capture_output=True,           # sets stdout, stderr to PIPE
        **kwargs,
    )

    if result.returncode != 0:
        print('AppleScript failed:')
        print(result.stdout)
        print(result.stderr)
        result.check_returncode()

    return result


# --------------------------------------------------------------------------------------


_DEBUG_COLOR = False
_SIDE_MARGIN = 45
_LEFT_VSCODE_MARGIN = 110
_TRIM_PADDING = 10
_PROBES = 5


def _is_red_pixel(r: int, g: int, b: int) -> bool:
    # iTerm renders the red as #E74025. It apparently is the most non-red.
    return r > 0xE0 and g < 0x48 and b < 0x30


def _find_regions_between_bars(
    im: Image.Image,
    left_margin: int = _SIDE_MARGIN,
    right_margin: int = _SIDE_MARGIN,
) -> tuple[None | Rect, None | Rect]:
    step = im.width // (_PROBES + 1)

    def is_red_bar(y: int) -> bool:
        for x in range(1, _PROBES + 1):
            pixel = x * step, y
            color = im.getpixel(pixel)  # type: ignore
            if _DEBUG_COLOR:
                print(
                    f'probe {x:2d}×{step}={pixel[0]:4d}, {pixel[1]:4d}: '
                    f'#{color[0]:02x}{color[1]:02x}{color[2]:02x}'
                )
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
        r1 = left_margin, upper1, im.width - right_margin, lower1
    if upper2 is not None and lower2 is not None:
        r2 = left_margin, upper2, im.width - right_margin, lower2
    return r1, r2


def _without_transparency(im: Image.Image) -> Image.Image:
    assert im.mode == 'RGBA'
    bg = Image.new('RGBA', im.size, 'WHITE')
    bg.paste(im, (0, 0), im)
    return bg.convert('RGB')


def _find_content_bbox(im: Image.Image) -> None | tuple[int, int, int, int]:
    bg = Image.new(im.mode, im.size, im.getpixel((10, 10)))  # type: ignore
    diff = ImageChops.difference(im, bg)
    diff = ImageChops.add(diff, diff, 2.0, -3)
    return diff.getbbox()


# --------------------------------------------------------------------------------------


PayloadType: TypeAlias = Literal[
    'dash-integral', 'spaced-dash-integral', 'arab-ligature'
]


class Terminal(BaseTerminal):

    def is_current(self) -> None | bool:
        if (current_bundle := os.getenv('__CFBundleIdentifier')):
            return self.bundle == current_bundle
        return None

    @property
    def application(self) -> str:
        if self.is_iterm():
            return '"iTerm2"'
        elif self.is_vscode():
            return '"Code"'
        else:
            return f'(name of application id "{self.bundle}")'

    def activate(self) -> Self:
        _run_applescript(f"""\
            tell application id "{self.bundle}"
                activate
                delay 4
            end tell
        """)

        if self.is_iterm():
            # Use keyboard shortcut to bring iTerm window to front
            _run_applescript(f"""
                tell application "System Events"
                    tell process {self.application}
                        keystroke "1" using {{option down, command down}}
                        delay 2
                    end tell
                end tell
            """)

        elif self.is_vscode():
            # Use keyboard shortcuts to make terminal window semi-presentable
            _run_applescript(f"""
                tell application "System Events"
                    tell process {self.application}
                        keystroke "p" using {{shift down, command down}}
                        delay 0.5
                        keystroke "View Close Primary Side Bar"
                        keystroke return
                        delay 1

                        keystroke "p" using {{shift down, command down}}
                        delay 0.5
                        keystroke "Terminal Create New Terminal in Editor Area"
                        keystroke return
                        delay 2
                    end tell
                end tell
            """)
        return self

    def change_dir(self, cwd: Path) -> Self:
        _run_applescript(f"""
            tell application "System Events"
                tell process {self.application}
                    keystroke "cd {cwd}"
                    keystroke return
                    delay 1
                end tell
            end tell
        """)
        return self

    def exec(self, cmd: str) -> Self:
        _run_applescript(f"""\
            tell application "System Events"
                tell process {self.application}
                    keystroke "{cmd}"
                    keystroke return
                    delay 2
                end tell
            end tell
        """)
        return self

    def window_rect_xywh(self) -> tuple[int, int, int, int]:
        result = _run_applescript(f"""
            tell application "System Events"
                tell process {self.application}
                    set {{theX, theY}} to position of its first window
                    set {{theW, theH}} to size of its first window
                    return {{theX, ",", theY, ",", theW, ",", theH}} as text
                end tell
            end tell
        """)

        return _parse_rect(result.stdout.decode('utf8'))

    def screenshot_name(self, prefix: str) -> str:
        return f'{prefix}-{self.nickname}-raw.png'

    def screenshot(self, path: Path) -> Self:
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
                tell process {self.application}
                    keystroke "q" using command down
                end tell
            end tell
        """)
        return self

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~

    def capture_output(
            self, demicode: Path, payload: PayloadType, screenshot: Path,
    ) -> None | Path:
        if self.is_current():
            # This terminal is running this script. Don't activate or quit.
            # Just run badterm.py directly.
            assert demicode == Path.cwd()
            print(f'    ⊙ Display {payload}')
            subprocess.run(['./script/badterm.py', payload], check=True)

            print('    ⊙ Capture screenshot')
            self.screenshot(screenshot)
            return screenshot

        print(f'    ⊙ Activate {self.name}')
        self.activate()
        self.change_dir(demicode)

        print(f'    ⊙ Make {self.name} display {payload}')
        self.exec(f'./script/badterm.py {payload}')

        print(f'    ⊙ Capture screenshot of {self.name}')
        self.screenshot(screenshot)

        if not self.is_vscode():
            print(f'    ⊙ Quit {self.name}')
            self.quit()

        return screenshot

    def crop_output(
        self, demicode: Path, payload: PayloadType, raw_screenshot: Path
    ) -> tuple[Path, None | Path]:
        with Image.open(raw_screenshot) as im:
            if im.mode == 'RGBA':
                im = _without_transparency(im)

            # Get rectangles between red horizontal bars
            print(f'    ⊙ Scan "{raw_screenshot.relative_to(demicode)}" for red bars')
            left_margin = _LEFT_VSCODE_MARGIN if self.is_vscode() else _SIDE_MARGIN
            r1, r2 = _find_regions_between_bars(im, left_margin)

            if r1 is None:
                raise AssertionError('could not identify region between red bars')
            to_scan = [r1]
            if r2 is not None:
                to_scan.append(r2)

            p1: None | Path = None
            p2: None | Path = None

            for rect1 in to_scan:
                first = rect1 == r1
                if first:
                    print(f'{" " * (6 + 17)}     \x1b[3mx     y      w     h\x1b[0m')

                print(f'    ⊙ Extract image #{2 - first}: {_format_xywh(*rect1)}')
                wim = im.copy() if first else im
                wim = wim.crop(rect1)
                rect2 = _find_content_bbox(wim)
                assert rect2 is not None

                print(f'    ⊙ Trim white space: {_format_xywh(*rect2)}')
                rect2 = _grow_rect(rect2, _TRIM_PADDING)
                wim = wim.crop(rect2)

                image_size = _format_wh(*wim.size)
                print(f'    ⊙ Save image #{2 - first}:    {image_size}')
                path = raw_screenshot.with_name(
                    f'{payload}-{self.nickname}{"" if first else "-2"}.png'
                )
                wim.save(path)

                if first:
                    p1 = path
                else:
                    p2 = path

            assert p1 is not None
            if r2 is not None:
                assert p2 is not None
            return p1, p2


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--terminal', '-t',
        choices=[
            'alactritty', 'hyper', 'iterm', 'kitty', 'rio', 'terminalapp', 'vscode',
            'warp', 'wezterm',
        ],
        help='run only the selected terminal'
    )
    parser.add_argument(
        '--payload', '-p',
        choices=['dash-integral', 'spaced-dash-integral', 'arab-ligature'],
        default='dash-integral',
        help='select the payload to display',
    )
    options = parser.parse_args()

    project_root = Path.cwd()
    msg = 'tool must run in root of demicode project'
    assert (project_root / 'demicode').is_dir(), msg
    assert (project_root / 'doc').is_dir(), msg
    assert (project_root / 'script').is_dir(), msg
    screenshot_dir = project_root / 'doc' / 'screenshot'
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    # Prevent the current terminal from leaking variable definitions to the
    # terminal being tested. Amazingly, macOS does propagate the environment
    # through AppleScript into activated applications.
    os.environ.pop('TERM_PROGRAM', None)
    os.environ.pop('TERM_PROGRAM_VERSION', None)

    if options.terminal:
        terminals = iter([Terminal.resolve(options.terminal)])
    else:
        terminals = Terminal.all()

    for terminal in terminals:
        print(f'\x1b[1m{terminal.name} ({terminal.bundle})\x1b[0m')
        screenshot = screenshot_dir / terminal.screenshot_name(options.payload)
        screenshot = terminal.capture_output(project_root, options.payload, screenshot)
        if screenshot is not None:
            paths = terminal.crop_output(project_root, options.payload, screenshot)
            if options.payload == 'dash-integral':
                assert paths[1] is not None


if __name__ == '__main__':
    main()
