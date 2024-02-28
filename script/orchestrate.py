#!./venv/bin/python

"""
Illustrate fixed-width rendering issues for lots of terminal emulators. This
script automates the collection of screenshots by:

 1. Launch a terminal emulator with AppleScript on macOS.
 2. Run commands with AppleScript on macOS.
 3. Take screenshot with `screencapture` command line utility on macOS
 4. Crop screenshot to command output using Pillow library.

Since the first three tasks are implemented with macOS-only technology, this
script only runs on macOS. While there are cross-platform libraries for taking
screenshots, how to automate the first two tasks on Linux or Windows is less
clear.
"""

import sys

if sys.platform != "darwin":
    raise NotImplementedError("script currently supports macOS only!")

import argparse
import json
import os
from pathlib import Path
import subprocess
from textwrap import dedent
import time
import traceback
from typing import Any, Literal, Self, TypeAlias

# Fix Python path to include project root
sys.path.insert(0, str(Path.cwd()))

from demicode.ui.terminal import Terminal as BaseTerminal
import demicode.util.image as image


# --------------------------------------------------------------------------------------


_SIDE_MARGIN = 60
_LEFT_VSCODE_MARGIN = 140
_TRIM_PADDING = 10
_PROBES = 5


Rect: TypeAlias = tuple[int, int, int, int]


def _parse_rect(s: str) -> Rect:
    if s.endswith("\n"):
        s = s[:-1]
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1]
    n1, n2, n3, n4 = s.split(",")
    return int(n1), int(n2), int(n3), int(n4)


def _format_wh(w: int, h: int) -> str:
    return f'{" " * (5 + 1 + 5 + 1)} {w:5,d}×{h:5,d}'


def _format_xywh(x1: int, y1: int, x2: int, y2: int) -> str:
    return f"{x1:5,d}×{y1:5,d}, {x2-x1:5,d}×{y2-y1:5,d}"


# --------------------------------------------------------------------------------------


def _run_applescript(script: str, **kwargs: Any) -> str:
    result = subprocess.run(
        ["osascript", "-s", "s", "-"],
        input=dedent(script).encode("utf8"),  # sets stdin to PIPE
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        **kwargs,
    )

    output = result.stdout.decode("utf8")
    if result.returncode != 0:
        print(f"\x1b[1mAppleScript failed:\x1b[0m\n{output}\n")
        result.check_returncode()
    return output


# --------------------------------------------------------------------------------------


PayloadType: TypeAlias = Literal[
    "dash-integral", "spaced-dash-integral", "arab-ligature", "seven-languages"
]


def _mark_up_figure(
    payload: PayloadType,
    all_terminals: list[str],
    all_paths: list[Path],
    all_sizes: list[image.SizeT],
) -> list[str]:
    # The description of screenshot contents
    desc2 = None
    match payload:
        case "dash-integral":
            desc1 = "a sequence mixing punctuation and symbols"
        case "spaced-dash-integral":
            desc1 = "a sequence mixing punctuation and symbols"
            desc2 = "with extra spaces to separate glyphs"
        case "arab-ligature":
            desc1 = "the code point with the largest glyph"
        case "seven-languages":
            desc1 = "the same (rather overdone) sentence"
            desc2 = "about free software ensuring a free society in 7 major languages"
        case _:  # type: ignore
            raise ValueError(f"unexpected payload {payload}")

    # Lines of markup
    lines = ["<figure class=wide-figure>"]

    # The images
    for terminal, path, size in zip(all_terminals, all_paths, all_sizes):
        lines.append(f'<img src="/blog/2024/terminals/{path.name}"')
        lines.append(f'     width={size[0]} height={size[1]}')
        if desc2 is None:
            lines.append(f'     alt="screenshot of {terminal} displaying {desc1}">')
        else:
            lines.append(f'     alt="screenshot of {terminal} displaying {desc1}')
            lines.append(f'          {desc2}">')

    # The caption
    terminals = list(dict.fromkeys(all_terminals).keys())
    match len(terminals):
        case 1:
            names = terminals[0]
        case 2:
            names = f"{terminals[0]} and {terminals[1]}"
        case _:
            names = ", ".join(t for t in terminals[:-1]) + ", and " + terminals[-1]

    lines.append(f'<figcaption>{names}')
    if desc2 is None:
        lines.append(f'display {desc1}</figcaption>')
    else:
        lines.append(f'display {desc1}')
        lines.append(f'{desc2}</figcaption>')

    lines.append("</figure>")
    return lines


# --------------------------------------------------------------------------------------


class Terminal(BaseTerminal):

    def is_current(self) -> None | bool:
        if current_bundle := os.getenv("__CFBundleIdentifier"):
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
        _run_applescript(
            f"""\
            tell application id "{self.bundle}"
                activate
                delay 4
            end tell
            """
        )

        if self.is_iterm():
            # Use keyboard shortcut to bring iTerm window to front
            _run_applescript(
                f"""
                tell application "System Events"
                    tell (some process whose bundle identifier is "{self.bundle}")
                        keystroke "1" using {{option down, command down}}
                        delay 2
                    end tell
                end tell
                """
            )

        elif self.is_vscode():
            # Screenshot analysis expects a red bar across much of the image.
            # The primary side bar and split editors get in the way of that.
            _run_applescript(
                f"""
                tell application "System Events"
                    tell (some process whose bundle identifier is "{self.bundle}")
                        keystroke "p" using {{shift down, command down}}
                        delay 0.5
                        keystroke "View Close All Editors"
                        keystroke return
                        delay 1

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
                """
            )

        return self

    def change_dir(self, cwd: Path) -> Self:
        _run_applescript(
            f"""
            tell application "System Events"
                tell (some process whose bundle identifier is "{self.bundle}")
                    keystroke "cd {cwd}"
                    keystroke return
                    delay 1
                end tell
            end tell
            """
        )
        return self

    def exec(self, cmd: str) -> Self:
        _run_applescript(
            f"""\
            tell application "System Events"
                tell (some process whose bundle identifier is "{self.bundle}")
                    keystroke "{cmd}"
                    keystroke return
                    delay 4
                end tell
            end tell
            """
        )
        return self

    def window_rect_xywh(self) -> tuple[int, int, int, int]:
        output = _run_applescript(
            f"""
            tell application "System Events"
                tell (some process whose bundle identifier is "{self.bundle}")
                    set {{theX, theY}} to position of its first window
                    set {{theW, theH}} to size of its first window
                    return {{theX, ",", theY, ",", theW, ",", theH}} as text
                end tell
            end tell
            """
        )
        return _parse_rect(output)

    def screenshot_name(self, prefix: str, suffix: str = "") -> str:
        return f"{prefix}-{self.name.lower()}{suffix}.png"

    def screenshot(self, path: Path) -> Self:
        subprocess.run(
            [
                "screencapture",
                "-m",
                "-R",
                ",".join(str(n) for n in self.window_rect_xywh()),
                str(path),
            ],
            check=True,
        )
        return self

    def quit(self) -> Self:
        # Directly telling the terminal to quit fails for Kitty
        _run_applescript(
            f"""\
            tell application "System Events"
                tell (some process whose bundle identifier is "{self.bundle}")
                    keystroke "q" using command down
                end tell
            end tell
            """
        )
        return self

    # ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~

    def capture_output(
        self,
        demicode: Path,
        payload: PayloadType,
        screenshot: Path,
    ) -> Path:
        if self.is_current():
            # This terminal is running this script. Run payload directly,
            # without UI scripting. Don't quit.
            print(f"    ⊙ Activate {self.name}")
            self.activate()
            assert demicode == Path.cwd()

            print(f"    ⊙ Display {payload}")
            if payload == 'seven-languages':
                subprocess.run(
                    ["./script/highlight.py", "./script/en-es-ja-ru-he-zh-hi.txt"],
                    check=True
                )
            else:
                subprocess.run(["./script/show.py", payload], check=True)

            print("    ⊙ Capture screenshot")
            self.screenshot(screenshot)
            return screenshot

        print(f"    ⊙ Activate {self.name}")
        self.activate()
        self.change_dir(demicode)

        print(f"    ⊙ Make {self.name} display {payload}")
        if payload == 'seven-languages':
            self.exec(f"./script/highlight.py ./script/en-es-ja-ru-he-zh-hi.txt")
        else:
            self.exec(f"./script/show.py {payload}")

        print(f"    ⊙ Capture screenshot of {self.name}")
        self.screenshot(screenshot)

        if not self.is_vscode():
            print(f"    ⊙ Quit {self.name}")
            self.quit()

        return screenshot

    def crop_output(
        self, demicode: Path, payload: PayloadType, screenshot: Path
    ) -> tuple[list[Path], list[image.SizeT]]:
        print(f'    ⊙ Load "{screenshot.relative_to(demicode)}" and normalize colors')
        with image.open(screenshot) as im:
            # Remember DPI for saving cropped images.
            dpi = im.info.get("dpi")

            # Normalize colorspace and drop alpha channel
            profile = image.get_profile(im)
            im = image.convert_to_srgb(im, profile)
            im = image.resolve_alpha(im)

            # Get rectangles between red horizontal bars
            print(f'    ⊙ Scan for red bars')

            x1 = _LEFT_VSCODE_MARGIN if self.is_vscode() else _SIDE_MARGIN
            x2 = im.width - _SIDE_MARGIN
            step = (x2 - x1) // _PROBES
            ranges = image.scan_bars(im, slice(x1, x2, step))
            only_one = len(ranges) == 1

            paths: list[Path] = []
            sizes: list[image.SizeT] = []
            for index, (y1, y2) in enumerate(ranges, start=1):
                outer = (x1, y1, x2, y2)
                bounds = _format_xywh(*outer)
                suffix = "  (xywh)" if index == 1 else ""
                print(f"    ⊙ Extract image #{index}:  {bounds}{suffix}")
                extract = im.crop(outer)

                inner = image.size_matte(extract)
                assert inner is not None
                bounds = _format_xywh(*image.box_in_box(inner, outer))
                print(f"    ⊙ Without matte:     {bounds}")
                extract = image.crop_box(extract, inner, _TRIM_PADDING)

                sizes.append(extract.size)
                bounds = _format_wh(*extract.size)
                print(f"    ⊙ Save image #{index}:     {bounds}")
                suffix = "" if only_one else f"-{index}"
                path = screenshot.with_name(self.screenshot_name(payload, suffix))
                extract.save(path, dpi=dpi, icc_profile=image.SRGB.tobytes())
                paths.append(path)

            for path in paths:
                print(f'    ≫ "{path.relative_to(demicode)}"')
            return paths, sizes

    def benchmark(self, demicode: Path, nonce: str) -> dict[str, object]:
        if not self.is_current():
            print(f"    ⊙ Activate {self.name}")
            self.activate()
            self.change_dir(demicode)

        print(f"    ⊙ Prepare for benchmark")
        path = Path(f"{self.name.lower()}-render-perf-{nonce}.json")
        if path.exists():
            path.unlink()

        print(f"    ⊙ Start benchmark")
        if self.is_current():
            subprocess.run(["python", "-m", "demicode", "-T", "-N", nonce], check=True)
        else:
            self.exec(f"python -m demicode -T -N {nonce}")

        print(f"    ⊙ Wait for completion")
        for _ in range(20):
            if path.exists():
                break
            time.sleep(1)
        if not path.exists():
            raise FileNotFoundError(path)

        print("    ⊙ Read results")
        with open(path, mode="rb") as file:
            results = json.load(file)

        if not self.is_vscode():
            print(f"    ⊙ Quit {self.name}")
            self.quit()

        return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--terminal",
        "-t",
        choices=[
            "alactritty",
            "hyper",
            "iterm",
            "kitty",
            "rio",
            "tabby",
            "terminal",
            "vscode",
            "warp",
            "wezterm",
        ],
        help="run only the selected terminal",
    )
    parser.add_argument(
        "--payload",
        "-p",
        choices=[
            "dash-integral", "spaced-dash-integral", "arab-ligature", "seven-languages"
        ],
        default="dash-integral",
        help="select the payload to display",
    )
    parser.add_argument("--benchmark", help="benchmark terminal performance")
    options = parser.parse_args()

    # Check that we are running in right directory.
    project_root = Path.cwd()
    msg = "tool must run in root of demicode project"
    assert (project_root / "demicode").is_dir(), msg
    assert (project_root / "doc").is_dir(), msg
    assert (project_root / "script").is_dir(), msg

    # Prevent the current terminal from leaking variable definitions to the
    # terminal being tested. Amazingly, macOS does propagate the environment
    # variables from Python through the osascript subprocess and System Events
    # helper process into the activated application.
    os.environ.pop("TERM_PROGRAM", None)
    os.environ.pop("TERM_PROGRAM_VERSION", None)

    # Determine the terminals requiring orchestration.
    if options.terminal:
        if (t := Terminal.resolve(options.terminal)) is None:
            raise ValueError(f'unknown terminal "{options.terminal}"')
        terminals = iter([t])
    else:
        terminals = Terminal.all()

    # Process current terminal last, make sure it doesn't show previous run.
    todo: list[Terminal] = []
    current: None | Terminal = None
    for terminal in terminals:
        if terminal.is_current():
            current = terminal
        else:
            todo.append(terminal)
    if current:
        todo.append(current)
        if len(todo) <= 3:
            try:
                _, height = os.get_terminal_size()
            except:
                height = 60
            print("\n" * height)

    # -------------------------
    # Collect Performance Stats
    # -------------------------

    if options.benchmark:
        nonce = Terminal.nonce()
        all_stats = {}

        for terminal in todo:
            stats = terminal.benchmark(project_root, nonce)
            all_stats[terminal.name] = stats

        path = project_root / f"perf-{nonce}.json"
        with open(path, mode="w", encoding="utf8") as file:
            json.dump(all_stats, file)

        print(f"Combined results written to {path}")
        return

    # -------------------
    # Collect Screenshots
    # -------------------

    screenshot_dir = project_root / "doc" / "screenshot"
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    # Mr DeMille, the terminals are ready for their close-ups!
    all_terminals: list[Terminal] = []
    all_paths: list[Path] = []
    all_sizes: list[image.SizeT] = []
    failures = 0

    for terminal in todo:
        print(f"\x1b[1m{terminal.name} ({terminal.bundle})\x1b[0m")
        screenshot = screenshot_dir / terminal.screenshot_name(options.payload, "-raw")
        screenshot = terminal.capture_output(project_root, options.payload, screenshot)
        cropshots = terminal.crop_output(project_root, options.payload, screenshot)
        all_paths.extend(cropshots[0])
        all_sizes.extend(cropshots[1])
        all_terminals.extend([terminal] * len(cropshots[0]))

        if (
            (options.payload == "dash-integral" and len(cropshots[0]) != 2)
            or len(cropshots[0]) != 1
        ):
            failures += 1
            print("    ⊙ \x1b[97;48;5;88mCould not extract any images!\x1b[0m")

    lines = _mark_up_figure(
        options.payload,
        [t.name for t in all_terminals],
        all_paths,
        all_sizes
    )

    print("\n".join(lines))

if __name__ == "__main__":
    try:
        main()
    except Exception as x:
        traceback.print_exception(x)
