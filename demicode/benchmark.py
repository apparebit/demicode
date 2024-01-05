from collections import defaultdict
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
import json
import math
import statistics
import time
from typing import NamedTuple, Self

from .ui.action import Action
from .ui.render import Renderer
from .ui.terminal import Terminal
from .ui.termio import TermIO


class Statistics(NamedTuple):
    """
    Basic statistics over a series of readings. Included quantities are minimum,
    mean, median (q50), 90th percentile (q90), and maximum. The median and 90th
    percentile values are *not* interpolated, but measured values.
    """

    min: int | float
    mean: int | float
    q50: int | float
    q90: int | float
    max: int | float

    @classmethod
    def of(cls, readings: Sequence[int | float]) -> "Statistics":
        readings = sorted(readings)
        count = len(readings)

        min = readings[0]
        mean = statistics.mean(readings)
        q50 = readings[round(0.5 * count)]
        q90 = readings[round(0.9 * count) - 1]
        max = readings[-1]

        return cls(min, mean, q50, q90, max)

    def scale(self, factor: float) -> "Statistics":
        """Scale all values by dividing them with the factor."""
        return type(self)(
            self.min / factor,
            self.mean / factor,
            self.q50 / factor,
            self.q90 / factor,
            self.max / factor,
        )


class Probe:
    """
    A probe for measuring page rendering latency. This class tracks the state
    necessary for repeatedly performing and measuring experiments. The overall
    run has a label and each experiment has its own label.
    """

    PAGE_LINE_BY_LINE = "page.line_by_line"
    PAGE_AT_ONCE = "page.at_once"

    def __init__(
        self,
        /,
        termio: None | TermIO = None,
        required_readings: int = 21,
    ) -> None:
        self._termio = termio or TermIO()
        self._termio.update_size()  # Lock in the terminal size
        self._required_readings = required_readings
        self._readings: dict[str, list[int]] = defaultdict(list)
        self._last_label = ""
        self._pages: dict[str, tuple[int, Action]] = {}

    @property
    def required_readings(self) -> int:
        return self._required_readings

    def validate(self) -> None:
        self._termio.check_same_size()

    @contextmanager
    def measure(self, label: str) -> Iterator[Self]:
        self.validate()
        start = time.perf_counter_ns()
        try:
            yield self
        finally:
            duration = time.perf_counter_ns() - start
            self._readings[label].append(duration)
            self._last_label = label
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

    def get_page_action(self, _: Renderer) -> Action:
        """
        Determine demicode's next step for measurements with the last used
        label. This method alternates between returning actions to go forward
        and backward until enough measurements have been made. Thereafter, it
        returns the action to terminate.
        """
        self._termio.write("\n")

        count, action = self._pages.get(self._last_label, (0, Action.BACKWARD))
        count += 1
        if count >= self._required_readings:
            action = Action.TERMINATE
        else:
            action = action.flip()
        self._pages[self._last_label] = count, action
        return action


# --------------------------------------------------------------------------------------


def integral_digits(num: int | float) -> int:
    return math.ceil(math.log10(num + 1)) if num >= 1.0 else 0


def pick_factor_unit(num: int | float) -> tuple[float, str]:
    digits = integral_digits(num)
    if digits >= 12:
        return 1e9, "s"
    elif digits >= 9:
        return 1e6, "ms"
    elif digits >= 6:
        return 1e3, "µs"
    else:
        return 1e0, "ns"


def report_page_rendering(probe: Probe, nonce: None | str) -> None:
    count = probe.count_readings(Probe.PAGE_AT_ONCE)
    count_line_by_line = probe.count_readings(Probe.PAGE_LINE_BY_LINE)
    assert count > 0
    assert count == count_line_by_line

    at_once = probe.statistics(Probe.PAGE_AT_ONCE)
    line_by_line = probe.statistics(Probe.PAGE_LINE_BY_LINE)
    slowdown = line_by_line.mean / at_once.mean

    factor, unit = pick_factor_unit(min(*at_once, *line_by_line))
    at_once = at_once.scale(factor)
    line_by_line = line_by_line.scale(factor)
    max_digits = integral_digits(max(*at_once, *line_by_line))
    precision = max_digits + max_digits // 3

    terminal = Terminal.current()
    termio = probe._termio  # type: ignore
    width, height = termio.width, termio.height

    # Write JSON to disk
    nonce = nonce or Terminal.nonce()
    json_data = {
        "nonce": nonce,
        "terminal": terminal.name,
        "page-size": {"width": width, "height": height},
        "mean-slowdown": slowdown,
        "unit": unit,
        "page-at-once": at_once._asdict(),
        "line-by-line": line_by_line._asdict(),
    }

    path = f"{terminal.name.lower()}-render-perf-{nonce}.json"
    with open(path, mode="w", encoding="utf8") as file:
        json.dump(json_data, file, indent="  ")

    # Show human-readable report
    termio.style(1).write(f"{terminal}: Rendering {width}×{height} Page").plain()
    termio.writeln("\n")

    termio.faint().write(f'         {" ":>12} ').plain().writeln()
    for label in ("min", "mean", "q50", "q90", "max"):
        (
            termio.faint()
            .write(f'  {label:>{precision}} {" " * len(unit)}')
            .plain()
            .writeln()
        )
    termio.writeln()

    def show(label: str, statistics: Statistics) -> None:
        termio.faint().write(f"    {count:2d} × ").plain().write(f"{label:>12}:")
        for num in statistics:
            termio.write(f"  {num:{precision},.0f} {unit}")
        termio.writeln()
        termio.flush()

    show("at-once", at_once)
    show("line-by-line", line_by_line)
    termio.writeln()

    slowdown = line_by_line.mean / at_once.mean
    termio.writeln(
        f"Rendering line-by-line is {slowdown:.1f}× slower than page at-once!\n"
    )

    termio.writeln().writeln(f'Results have been written to "{path}"')
