from dataclasses import dataclass
from enum import StrEnum


CSI = '\x1b['


def SGR(code: str) -> str:
    return f'{CSI}{code}m'


def CHA(column: int) -> str:
    return f'{CSI}{column}G'


@dataclass(frozen=True, slots=True)
class Theme:
    legend: str
    blot_highlight: str
    blot_obstruction: str
    very_strong: str
    error: str

    @classmethod
    def of(
        cls,
        legend: str,
        blot_highlight: str,
        blot_obstruction: str,
        very_strong: str,
        error: str,
    ) -> 'Theme':
        return cls(
            SGR(legend),
            SGR(blot_highlight),
            SGR(blot_obstruction),
            SGR(very_strong),
            SGR(error),
        )


class Styles:
    RESET = SGR('0')
    BOLD = SGR('1')

    LIGHT = (
        Theme.of('48;5;252', '48;5;254', '38;5;244', '1', '1;38;5;160'),
        Theme.of('48;5;252', '48;5;220', '38;5;244', '1', '1;38;5;160'),
        Theme.of('48;5;252', '48;5;220', '38;5;202', '1;48;5;218', '1;38;5;160'),
    )

    DARK = (
        Theme.of('48;5;240', '48;5;238', '38;5;244', '1', '1;38;5;88'),
        Theme.of('48;5;240', '48;5;53', '38;5;244', '1', '1;38;5;88'),
        Theme.of('48;5;240', '48;5;53', '38;5;93', '1;48;5;218', '1;38;5;88'),
    )


class Mode(StrEnum):
    LIGHT = 'LIGHT'
    DARK = 'DARK'


class Padding(StrEnum):
    BACKGROUND = ' '
    FOREGROUND = '\u2588'


class Renderer:
    """A line-oriented console renderer using ANSI escape codes."""

    def __init__(self, width: int, mode: Mode, brightness: int) -> None:
        self._width = min(120, width)
        self._theme = getattr(Styles, mode.value)[min(2, max(0, brightness))]

    @property
    def width(self) -> int:
        return self._width

    def column(self, column: int) -> str:
        return CHA(column)

    def legend(self, text: str) -> str:
        return f'{self._theme.legend}{text}{Styles.RESET}'

    def blot(self, text: str, padding: Padding, width: int) -> str:
        if padding is Padding.BACKGROUND:
            return (
                text
                + self._theme.blot_highlight
                + (padding.value * width)
                + Styles.RESET
            )
        else:
            return (
                text
                + self._theme.blot_obstruction
                + (padding.value * width)
                + Styles.RESET
            )

    def strong(self, text: str) -> str:
        return f'{Styles.BOLD}{text}{Styles.RESET}'

    def very_strong(self, text: str) -> str:
        return f'{self._theme.very_strong}{text}{Styles.RESET}'

    def error(self, text: str) -> str:
        return f'{self._theme.error}{text}{Styles.RESET}'
