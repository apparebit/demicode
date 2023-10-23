from collections import defaultdict
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
import json
import math
import os
import statistics
import sys
import time
from typing import Callable, cast, NamedTuple, Self, TextIO

from .render import Renderer


class TerminalSizeChecker:
    """Validate that terminal size did not change."""

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
            raise RuntimeError('terminal size has changed')


class Statistics(NamedTuple):
    """Statistics for a series of readings."""

    min: int|float
    mean: int|float
    q50: int|float
    q90: int|float
    max: int|float

    @classmethod
    def of(cls, measurements: Sequence[int | float]) -> 'Statistics':
        measurements = sorted(measurements)
        count = len(measurements)

        min = measurements[0]
        mean = statistics.mean(measurements)
        q50 = measurements[round(0.5 * count)]
        q90 = measurements[round(0.9 * count) - 1]
        max = measurements[-1]

        return cls(min, mean, q50, q90, max)

    def scale(self, factor: float) -> 'Statistics':
        return type(self)(
            self.min / factor,
            self.mean / factor,
            self.q50 / factor,
            self.q90 / factor,
            self.max / factor,
        )


class Probe:
    """
    A probe for measuring demicode's latency. It accumulates measurements by
    label, while also ensuring that the probed environment remains consistent.
    In particular, it ensures that the terminal size does not change.
    """

    PAGE_LINE_BY_LINE = 'page.line_by_line'
    PAGE_AT_ONCE = 'page.at_once'

    def __init__(
        self,
        /,
        required_readings: int = 21,
        validator: Callable[[], None] = lambda: None
    ) -> None:
        self._required_readings = required_readings
        self.validate = validator
        self._readings: dict[str, list[int]] = defaultdict(list)

    @property
    def required_readings(self) -> int:
        return self._required_readings

    @contextmanager
    def measure(self, label: str) -> Iterator[Self]:
        self.validate()
        start = time.perf_counter_ns()
        try:
            yield self
        finally:
            duration = time.perf_counter_ns() - start
            self._readings[label].append(duration)
            self.validate()

    def latest_reading(self, label: str) -> int:
        if label not in self._readings:
            raise KeyError(label)
        return self._readings[label][-1]

    def count_readings(self, label: str) -> int:
        if label not in self._readings:
            return 0
        return len(self._readings[label])

    def all_readings(self, label: str) -> list[int]:
        if label not in self._readings:
            raise KeyError(label)
        return self._readings[label]

    def statistics(self, label: str) -> Statistics:
        return Statistics.of(self.all_readings(label))


# --------------------------------------------------------------------------------------


_TERM_PROGRAM = {
    'Apple_Terminal': 'Terminal.app',
    'Hyper': 'Hyper',
    'iTerm.app': 'iTerm2',
    'vscode': 'Visual Studio Code',
    'WarpTerminal': 'Warp',
    'WezTerm': 'WezTerm',
}


_CF_BUNDLE_IDENTIFIER = {
    'org.alacritty': 'Alacritty',
    'co.zeit.hyper': 'Hyper',
    'com.googlecode.iterm2': 'iTerm2',
    'net.kovidgoyal.kitty': 'Kitty',
    'com.apple.Terminal': 'Terminal.app',
    'dev.warp.Warp-Stable': 'Warp',
    'com.github.wez.wezterm': 'WezTerm',
}


def identify_terminal(renderer: Renderer) -> tuple[None | str, None | str]:
    terminal = os.getenv('TERM_PROGRAM')
    if terminal is not None:
        terminal = _TERM_PROGRAM.get(terminal, terminal)
    if terminal is None:
        terminal = os.getenv('__CFBundleIdentifier')
        if terminal is not None:
            terminal = _CF_BUNDLE_IDENTIFIER.get(terminal, terminal)

    version = os.getenv('TERM_PROGRAM_VERSION')
    if version is None:
        try:
            v = renderer.query('[>q')
        except (NotImplementedError, TimeoutError):
            v = None
        if v is not None:
            v = v[4:-2]
            if v[-1] == 41:
                parts = v.rsplit(b'(', maxsplit=1)
                if len(parts) == 2:
                    version = parts[1][:-1].decode('ascii')
            else:
                parts = v.rsplit(b' ', maxsplit=1)
                if len(parts) == 2:
                    version = parts[1].decode('ascii')

    return terminal, version


def integral_digits(num: int | float) -> int:
    return math.ceil(math.log10(num + 1)) if num >= 1.0 else 0


def pick_factor_unit(num: int | float) -> tuple[float, str]:
    digits = integral_digits(num)
    if digits >= 12:
        return 1E9, 's'
    elif digits >= 9:
        return 1E6, 'ms'
    elif digits >= 6:
        return 1E3, 'µs'
    else:
        return 1E0, 'ns'


def report_page_rendering(probe: Probe, renderer: Renderer) -> None:
    count = probe.count_readings(Probe.PAGE_AT_ONCE)
    count_line_by_line = probe.count_readings(Probe.PAGE_LINE_BY_LINE)
    assert count > 0
    assert count == count_line_by_line

    at_once = probe.statistics(Probe.PAGE_AT_ONCE)
    line_by_line = probe.statistics(Probe.PAGE_LINE_BY_LINE)
    ratio = line_by_line.mean / at_once.mean

    factor, unit = pick_factor_unit(min(*at_once, *line_by_line))
    at_once = at_once.scale(factor)
    line_by_line = line_by_line.scale(factor)
    max_digits = integral_digits(max(*at_once, *line_by_line))
    precision = max_digits + max_digits // 3

    terminal, terminal_version = identify_terminal(renderer)
    termid = terminal or 'Unknown Terminal'
    if terminal_version:
        termid = f'{termid} {terminal_version}'

    probe.validate()
    checker = cast(TerminalSizeChecker, probe.validate)
    width = checker.width
    height = checker.height

    json_data = {
        'terminal': {'name': terminal, 'version': terminal_version},
        'page-size': {'width': width, 'height': height},
        'ratio': ratio,
        'latency-unit': unit,
        'at-once': at_once._asdict(),
        'line-by-line': line_by_line._asdict(),
    }

    # Show results as JSON
    renderer.writeln('\n')
    renderer.writeln(json.dumps(json_data, indent='  '))
    renderer.writeln('\n')

    # Show human-readable report
    renderer.strong(f'{termid} Rendering {width}×{height} Page')
    renderer.writeln('\n')

    renderer.faint(f'         {" ":>12} ')
    for label in ('min', 'mean', 'q50', 'q90', 'max'):
        renderer.faint(f'  {label:>{precision}} {" " * len(unit)}')
    renderer.newline()

    def show(label: str, statistics: Statistics) -> None:
        renderer.faint(f'    {count:2d} × ')
        renderer.write(f'{label:>12}:')
        for num in statistics:
            renderer.write(f'  {num:{precision},.0f} {unit}')
        renderer.newline()
        renderer.flush()

    show('at-once', at_once)
    show('line-by-line', line_by_line)
    renderer.newline()

    ratio = line_by_line.mean / at_once.mean
    renderer.writeln(
        f'Rendering line-by-line is {ratio:.1f}× slower than page at-once!'
    )
    renderer.newline()
