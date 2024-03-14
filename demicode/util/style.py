from collections.abc import Iterator
import dataclasses
import enum
import itertools
import math
from typing import (
    cast,
    ClassVar,
    Literal,
    Never,
    Protocol,
    Self,
    TypedDict,
    TypeVar,
    Unpack
)

class Attribute(Protocol):
    """The common interface for all classes modelling attributes"""

    def is_none(self) -> bool:
        """Determine whether the attribute is none."""
        ...

    def __invert__(self) -> 'Attribute':
        """Return the inverse attribute to restore default appearance."""
        ...

    def terms(self) -> tuple[str, ...]:
        """Return the terms for fluently setting the attribute."""
        ...

    def parameters(self) -> tuple[int, ...]:
        """Return the SGR parameters for setting the attribute."""
        ...


# --------------------------------------------------------------------------------------


_T = TypeVar('_T', bound='TextAttribute')


class TextAttribute(enum.Enum):
    """
    The superclass of all enumerations representing attributes other than color.
    Each such enumeration models attributes that are mutually exclusive. It must
    have a member with name `NONE` and value `0` that represents the absence of
    that attribute. It also must have a member with name `DEFAULT` that aliases
    the default. The value of each member is the corresponding SGR parameter
    value.
    """

    def is_none(self) -> bool:
        return self.value == type(self)['NONE'].value

    def is_default(self) -> bool:
        return self.value == type(self)['DEFAULT'].value

    def __invert__(self: _T) -> _T:
        if self.is_none() or self.is_default():
            return type(self)['NONE']
        else:
            return type(self)['DEFAULT']

    def terms(self) -> tuple[str, ...]:
        return () if self.is_none() else (self.name.lower(),)

    def parameters(self) -> tuple[int, ...]:
        return () if self.is_none() else (self.value,)


class Weight(TextAttribute):
    NONE = 0
    REGULAR = 22
    DEFAULT = 22
    LIGHT = 2
    BOLD = 1


class Slant(TextAttribute):
    NONE = 0
    UPRIGHT = 23
    DEFAULT = 23
    ITALIC = 3


class Underline(TextAttribute):
    NONE = 0
    NOT_UNDERLINED = 24
    DEFAULT = 24
    UNDERLINED = 4


class Blinking(TextAttribute):
    NONE = 0
    NOT_BLINKING = 25
    DEFAULT = 25
    SLOW_BLINKING = 5
    RAPID_BLINKING = 6


class Coloring(TextAttribute):
    NONE = 0
    NOT_REVERSED = 27
    DEFAULT = 27
    REVERSED = 7


class Visibility(TextAttribute):
    NONE = 0
    VISIBLE = 28
    DEFAULT = 28
    INVISIBLE = 8



class Color:

    __slots__ = ()

    def is_none(self) -> bool:
        return type(self) is NoColor

    def __invert__(self) -> 'Color':
        if type(self) is Color256:
            return DefaultColor.DEFAULT
        else:
            return NoColor.NONE

    def terms(self) -> tuple[str, ...]:
        return ()

    def parameters(self) -> tuple[int, ...]:
        return ()

    def color(self, value: int) -> 'Color':
        return Color256(value)


class NoColor(Color, enum.Enum):
    NONE = enum.auto()
    PLAIN_PENDING = enum.auto()
    BRIGHT_PENDING = enum.auto()


class DefaultColor(Color):

    __slots__ = ()

    DEFAULT: 'ClassVar[DefaultColor]'


DefaultColor.DEFAULT = DefaultColor()
def new_default_color(_) -> Never:
    raise TypeError('DefaultColor.DEFAULT is a singleton')
DefaultColor.__new__ = new_default_color  # type: ignore


@dataclasses.dataclass(frozen=True, slots=True)
class Color256(Color):

    value: int

    def __post_init__(self) -> None:
        pass


# --------------------------------------------------------------------------------------


_COLOR_NAMES = (
    'black',
    'red',
    'green',
    'yellow',
    'blue',
    'magenta',
    'cyan',
    'white',
)


_COLOR_CODES = {
    1: (3, 0, 0),
    2: (0, 3, 0),
    4: (0, 0, 3),
    3: (3, 3, 0),
    5: (3, 0, 3),
    6: (0, 3, 3),
    9: (4, 0, 0),
    10: (0, 4, 0),
    12: (0, 0, 4),
    11: (4, 4, 0),
    13: (4, 0, 4),
    14: (0, 4, 4),
    0: (0, 0, 0),
    8: (2, 2, 2),
    7: (4, 4, 4),
    15: (5, 5, 5),
}


@dataclasses.dataclass(frozen=True, slots=True)
class ColorAttribute:

    value: NoColor | Literal['default'] | int = NoColor.NONE

    def __post_init__(self) -> None:
        if type(self) is ColorAttribute:
            raise ValueError('ColorAttribute is abstract')
        if isinstance(self.value, int) and not (0 <= self.value <= 255):
            raise ValueError(f'"{self.value}" is not a valid color code')

    @property
    def description(self) -> str:
        return (
            'background color' if type(self) is BackgroundColor else 'foreground color'
        )

    def __invert__(self) -> Self:
        if self.is_none() or self.is_default():
            return type(self)(NoColor.NONE)
        else:
            return type(self)('default')

    def is_none(self) -> bool:
        return isinstance(self.value, NoColor)

    def is_pending(self) -> bool:
        return self.value in (NoColor.PLAIN_PENDING, NoColor.BRIGHT_PENDING)

    def check_not_pending(self) -> Self:
        if self.is_pending():
            raise ValueError(f'{self.description} is pending')
        return self

    def mark_pending(self) -> Self:
        self.check_not_pending()
        return type(self)(NoColor.PLAIN_PENDING)

    def mark_bright(self) -> Self:
        if self.value is not NoColor.PLAIN_PENDING:
            raise ValueError(f'cannot brighten {self.description}')
        return type(self)(NoColor.BRIGHT_PENDING)

    def set_color(self, value: Literal['default'] | int) -> Self:
        if self.value is NoColor.PLAIN_PENDING:
            return type(self)(value)
        elif self.value is NoColor.BRIGHT_PENDING:
            if value == 'default' or not 0 <= value <= 7:
                raise ValueError(f'"{value}" is not a valid bright color code')
            return type(self)(value + 8)
        else:
            raise ValueError(f'cannot set {self.description} to {value}')

    def is_default(self) -> bool:
        """Determine whether this color is the default color."""
        return self.value == 'default'

    def is_rgb(self) -> bool:
        """Determine whether this color is in the 6x6x6 RGB cube."""
        return isinstance(self.value, int) and 16 <= self.value <= 231

    def rgb(self) -> tuple[int, int, int]:
        """Get the components for the 6x6x6 RGB cube."""
        if not isinstance(self.value, int) or not 16 <= self.value <= 231:
            raise ValueError(f'"{self.value}" is not a color in the 6x6x6 RGB cube')

        b = self.value - 16
        r = b // 36
        b -= r * 36
        g = b // 6
        b -= g * 6
        return r, g, b

    def bw_complement(self) -> Self:
        """"Determine black/white that has the strongest contrast with this color."""
        if not isinstance(self.value, int):
            raise ValueError(f'"{self.value}" is not an 8-bit color')

        if self.value in (7, 10, 11, 14, 15) or 244 <= self.value <= 255:
            return type(self)(0)
        if 0 <= self.value <= 15 or 232 <= self.value <= 243:
            return type(self)(15)

        r, g, b = self.rgb()
        return type(self)(0) if g >= 4 or g >= 2 and r+2.5*g+b > 10 else type(self)(15)

    def four_bit(self) -> Self:
        """Convert this 8-bit color to the closest 4-bit color."""
        if not isinstance(self.value, int) or 0 <= self.value <= 15:
            return self

        if 232 <= self.value <= 239:
            return type(self)(0)
        if 240 <= self.value <= 245:
            return type(self)(8)
        if 246 <= self.value <= 251:
            return type(self)(7)
        if 252 <= self.value <= 255:
            return type(self)(15)

        r0, g0, b0 = self.rgb()
        value = 0
        distance = math.inf
        for code, (r, g, b) in _COLOR_CODES.items():
            d = (r0 - r)**2 + (g0 - g)**2 + (b0 -b)**2
            if r == g == b and d > 3:
                continue
            if d < distance:
                value = code
                distance = d

        return type(self)(value)

    def terms(self) -> tuple[str, ...]:
        if isinstance(self.value, NoColor):
            return ()

        if self.value == 'default':
            terms = ('default',)
        elif 0 <= self.value <= 7:
            terms = (_COLOR_NAMES[self.value],)
        elif 8 <= self.value <= 15:
            terms = ('bright', _COLOR_NAMES[self.value - 8])
        else:
            terms = (f'color({self.value})',)

        return ('on', *terms) if type(self) is BackgroundColor else terms

    def parameters(self) -> tuple[int,...]:
        offset = 10 if type(self) is BackgroundColor else 0
        if isinstance(self.value, NoColor):
            return ()
        elif self.value == 'default':
            return (39 + offset,)
        elif 0 <= self.value <= 7:
            return (30 + self.value + offset,)
        elif 8 <= self.value <= 15:
            return (90 + self.value - 8 + offset,)
        else:
            return 38 + offset, 5, self.value

    def __repr__(self) -> str:
        if isinstance(self.value, NoColor):
            value = ''
        elif self.value == 'default':
            value = '<default>'
        elif 0 <= self.value <= 7:
            value = f'<{_COLOR_NAMES[self.value]}>'
        elif 8 <= self.value <= 15:
            value = f'<bright_{_COLOR_NAMES[self.value - 8]}>'
        else:
            value = str(self.value)

        return f'{type(self).__name__}({value})'


class ForegroundColor(ColorAttribute):
    """The foreground color."""

    __slots__ = ()

    def bg(self) -> 'BackgroundColor':
        """Return this foreground color as a background color."""
        return BackgroundColor(self.value)


class BackgroundColor(ColorAttribute):
    """The background color."""

    __slots__ = ()

    def fg(self) -> ForegroundColor:
        """Return this background color as a foreground color"""
        return ForegroundColor(self.value)


# --------------------------------------------------------------------------------------


class _AttributeValues(TypedDict, total=False):
    weight: Weight
    slant: Slant
    underline: Underline
    blinking: Blinking
    coloring: Coloring
    visibility: Visibility
    foreground: ForegroundColor
    background: BackgroundColor


@dataclasses.dataclass(frozen=True, kw_only=True, slots=True)
class Style:
    """
    A select graphics rendition style. This class enables the fluent definition
    of such styles, while also ensuring that the styles are well-formed.
    """
    weight: Weight = Weight.NONE
    slant: Slant = Slant.NONE
    underline: Underline = Underline.NONE
    blinking: Blinking = Blinking.NONE
    coloring: Coloring = Coloring.NONE
    visibility: Visibility = Visibility.NONE
    foreground: ForegroundColor = ForegroundColor()
    background: BackgroundColor = BackgroundColor()

    def attributes(self) -> Iterator[tuple[str, Attribute]]:
        """Return an iterator over this style's non-none attributes and their names."""
        self._check_not_pending()
        return (
            (f.name, v)
            for f in dataclasses.fields(self)
            if not (v := getattr(self, f.name)).is_none()
        )

    def __invert__(self) -> Self:
        """Invert this style. The resulting style restores the default appearance."""
        attributes = {n: ~a for n, a in self.attributes()}
        return type(self)(**cast(_AttributeValues, attributes))

    def __or__(self, other: object) -> Self:
        """
        Combine this style with another one. The resulting style has the
        non-none attributes of both this and the other style, with this style's
        attributes taking precedence.
        """
        if not isinstance(other, Style):
            return NotImplemented
        return type(self)(**cast(_AttributeValues, (
            {n: a for n, a in other.attributes()}
            | {n: a for n, a in self.attributes()}  # 2nd so that self has priority
        )))

    def _with(self, **attributes: Unpack[_AttributeValues]) -> Self:
        self._check_not_pending()
        for key in attributes.keys():
            if not getattr(self, key).is_none():
                raise ValueError(f'attribute "{key}" is already set')
        return dataclasses.replace(self, **attributes)

    @property
    def regular(self) -> Self:
        return self._with(weight=Weight.REGULAR)

    @property
    def light(self) -> Self:
        return self._with(weight=Weight.LIGHT)

    @property
    def bold(self) -> Self:
        return self._with(weight=Weight.BOLD)

    @property
    def upright(self) -> Self:
        return self._with(slant=Slant.UPRIGHT)

    @property
    def italic(self) -> Self:
        return self._with(slant=Slant.ITALIC)

    @property
    def not_underlined(self) -> Self:
        return self._with(underline=Underline.NOT_UNDERLINED)

    @property
    def underlined(self) -> Self:
        return self._with(underline=Underline.UNDERLINED)

    @property
    def not_blinking(self) -> Self:
        return self._with(blinking=Blinking.NOT_BLINKING)

    @property
    def slow_blinking(self) -> Self:
        return self._with(blinking=Blinking.SLOW_BLINKING)

    @property
    def rapid_blinking(self) -> Self:
        return self._with(blinking=Blinking.RAPID_BLINKING)

    @property
    def not_reversed(self) -> Self:
        return self._with(coloring=Coloring.NOT_REVERSED)

    @property
    def reversed(self) -> Self:
        return self._with(coloring=Coloring.REVERSED)

    @property
    def visible(self) -> Self:
        return self._with(visibility=Visibility.VISIBLE)

    @property
    def invisible(self) -> Self:
        return self._with(visibility=Visibility.INVISIBLE)

    def _check_not_pending(self) -> Self:
        self.foreground.check_not_pending()
        self.background.check_not_pending()
        return self

    def _set_color(self, value: Literal['default'] | int) -> Self:
        if self.foreground.is_pending():
            return dataclasses.replace(
                self, foreground=self.foreground.set_color(value)
            )
        if self.background.is_pending():
            return dataclasses.replace(
                self, background=self.background.set_color(value)
            )
        if self.foreground.is_none() and self.background.is_none():
            return dataclasses.replace(
                self, foreground=ForegroundColor(value)
            )
        raise ValueError(f'cannot tell if "{value}" is foreground or background code')

    @property
    def fg(self) -> Self:
        self._check_not_pending()
        return dataclasses.replace(self, foreground=self.foreground.mark_pending())

    @property
    def bg(self) -> Self:
        self._check_not_pending()
        return dataclasses.replace(self, background=self.background.mark_pending())

    @property
    def on(self) -> Self:
        return self.bg

    @property
    def bright(self) -> Self:
        if self.foreground.is_pending():
            return dataclasses.replace(
                self, foreground=self.foreground.mark_bright()
            )
        if self.background.is_pending():
            return dataclasses.replace(
                self, background=self.background.mark_bright()
            )
        if self.foreground.is_none() and self.background.is_none():
            return dataclasses.replace(
                self, foreground=ForegroundColor(NoColor.BRIGHT_PENDING)
            )
        raise ValueError(f'cannot distinguish bright foreground from background color')

    @property
    def default(self) -> Self:
        return self._set_color('default')

    @property
    def black(self) -> Self:
        return self._set_color(0)

    @property
    def red(self) -> Self:
        return self._set_color(1)

    @property
    def green(self) -> Self:
        return self._set_color(2)

    @property
    def yellow(self) -> Self:
        return self._set_color(3)

    @property
    def blue(self) -> Self:
        return self._set_color(4)

    @property
    def magenta(self) -> Self:
        return self._set_color(5)

    @property
    def cyan(self) -> Self:
        return self._set_color(6)

    @property
    def white(self) -> Self:
        return self._set_color(7)

    def color(self, value: int) -> Self:
        return self._set_color(value)

    @property
    def bw_complement(self) -> Self:
        """
        Set missing color to black or white, depending on which of the two has
        more contrast with existing color.
        """
        if self.foreground.is_none():
            if self.background.is_none():
                raise ValueError('cannot contrast no colors')
            return dataclasses.replace(
                self, foreground=self.background.bw_complement().fg()
            )

        if not self.background.is_none():
            raise ValueError('cannot contrast both colors')
        return dataclasses.replace(
            self, background=self.foreground.bw_complement().bg()
        )

    @property
    def four_bit(self) -> Self:
        self._check_not_pending()
        return dataclasses.replace(
            self,
            foreground=self.foreground.four_bit(),
            background=self.background.four_bit(),
        )

    @property
    def to_black_white(self) -> Self:
        self._check_not_pending()
        return dataclasses.replace(
            self, foreground=ForegroundColor(), background=BackgroundColor()
        )

    def terms(self) -> list[str]:
        return [*itertools.chain.from_iterable(
            a.terms() for _, a in self.attributes()
        )]

    def parameters(self) -> list[int]:
        return [*itertools.chain.from_iterable(
            a.parameters() for _, a in self.attributes()
        )]

    def __repr__(self) -> str:
        return f'{type(self).__name__}().{".".join(self.terms())}'

    def __str__(self) -> str:
        return f'\x1b[{";".join(str(p) for p in self.parameters())}m'


if __name__ == '__main__':
    import os
    import sys

    if not sys.stdout.isatty():
        print('stdout is not a tty', file=sys.stderr)
        sys.exit(1)

    width, _ = os.get_terminal_size()

    frame = Style().italic

    box_width = 0
    panel_width = 0

    def topframe(text: str, boxes: int) -> None:
        global box_width, panel_width
        box_width = (width - 2) // boxes
        panel_width = box_width * boxes

        print(f'\n{frame}┏{f" {text.strip()} ".center(panel_width, "━")}┓{~frame}')

    def sideframe() -> None:
        print(f'{frame}┃{~frame}', end ='')

    def bottomframe() -> None:
        print(f'{frame}┗{"━" * panel_width}┛{~frame}\n')

    topframe('16 Base Colors', 2)
    for color in range(8):
        sideframe()
        for offset in (0, 8):
            style = Style(background=BackgroundColor(color + offset)).bold.bw_complement
            label = ' '.join(style.background.terms()[1:]).center(box_width)
            print(f'{style}{label}{~style}', end='')
        sideframe()
        print()
    bottomframe()

    topframe('24 Grey Tones', 24)
    for line in range(3):
        sideframe()
        for color in range(232, 256):
            style = Style(background=BackgroundColor(color)).bold.bw_complement
            label = str(color).center(3)[line].center(box_width)
            print(f'{style}{label}{~style}', end='')
        sideframe()
        print()
    bottomframe()

    topframe('6x6x6 Background Colors', 6)
    for r in range(0, 6):
        for b in range(0, 6):
            sideframe()
            for g in range(0, 6):
                style = Style(
                    background=BackgroundColor(16 + r * 36 + g * 6 + b)
                ).bold.bw_complement
                label = f'{r}•{g}•{b}'.center(box_width)
                print(f'{style}{label}{~style}', end='')
            sideframe()
            print()
    bottomframe()

    topframe('6x6x6 Background Colors Reduced to 4-bits', 6)
    for r in range(0, 6):
        for b in range(0, 6):
            sideframe()
            for g in range(0, 6):
                style = Style(
                    background=BackgroundColor(16 + r * 36 + g * 6 + b)
                ).bold.four_bit.bw_complement
                label = f'{r}•{g}•{b}'.center(box_width)
                print(f'{style}{label}{~style}', end='')
            sideframe()
            print()
    bottomframe()

    topframe('6x6x6 Foreground Colors', 6)
    for r in range(0, 6):
        for b in range(0, 6):
            sideframe()
            for g in range(0, 6):
                style = Style(
                    foreground=ForegroundColor(16 + r * 36 + g * 6 + b)
                ).bold.bw_complement
                label = f'{r}•{g}•{b}'.center(box_width)
                print(f'{style}{label}{~style}', end='')
            sideframe()
            print()
    bottomframe()
