"""
Treat Unicode property values as set and compose them with each other as Python
expressions. While it would be possible to support query expressions for
enumeration constants, that also would be rather invasive, adding quite a bit of
code to critical data structures. Instead, I decided to keep this functionality
separate and optional. However, for Python operator overloading to work, at
least the left-most (or second left-most) enumeration constant must be
explicitly injected into the space of query expressions with `query()`. For
example:

```py
from demicode.model import BinaryProperty, East_Asian_Width
from demicode.query import query

ambiguous_picto = (
    query(East_Asian_Width.Ambiguous) & BinaryProperty.Extended_Pictographic
)
```
"""

from dataclasses import dataclass
import enum
import functools
import itertools
import operator
from typing import Callable, ClassVar, Self


from .codepoint import CodePoint, CodePointRange
from .model import BinaryProperty, Property
from .ucd import UnicodeCharacterDatabase


def ensure_other_is_composable(
    fn: 'Callable[[Composable, Composable], App]'
) -> 'Callable[[Composable, object], App]':
    @functools.wraps(fn)
    def wrapper(self: 'Composable', other: object) -> 'App':
        if isinstance(other, Composable):
            return fn(self, other)
        elif isinstance(other, (BinaryProperty, Property)):
            return fn(self, Prop(other))
        return NotImplemented
    return wrapper


class Operator(enum.Enum):
    AND = 'and_'
    INVERT = 'invert'
    OR = 'or_'
    SUB = 'sub'

    @property
    def is_unary(self) -> bool:
        return self is Operator.INVERT

    @property
    def fn(self) -> Callable[..., set[CodePoint]]:
        return getattr(operator, self.value)

    @property
    def token(self) -> str:
        match self:
            case Operator.AND:
                return '&'
            case Operator.INVERT:
                return '~'
            case Operator.OR:
                return '|'
            case Operator.SUB:
                return '-'


class Composable:

    def is_bottom(self) -> bool:
        return False

    def is_top(self) -> bool:
        return False

    def is_prop(self) -> bool:
        return False

    def to_prop(self) -> 'Prop':
        raise TypeError(f"{self} isn't a `Prop`")

    def is_app(self) -> bool:
        return False

    def applies(self, op: Operator) -> bool:
        return False

    def to_app(self) -> 'App':
        raise TypeError(f"{self} isn't an `App`")

    def __invert__(self) -> 'App':
        return App(Operator.INVERT, self)

    @ensure_other_is_composable
    def __and__(self, other: 'Composable') -> 'App':
        return App(Operator.AND, self, other)

    @ensure_other_is_composable
    def __rand__(self, other: 'Composable') -> 'App':
        return App(Operator.AND, other, self)

    @ensure_other_is_composable
    def __or__(self, other: 'Composable') -> 'App':
        return App(Operator.OR, self, other)

    @ensure_other_is_composable
    def __ror__(self, other: 'Composable') -> 'App':
        return App(Operator.OR, other, self)

    @ensure_other_is_composable
    def __sub__(self, other: 'Composable') -> 'App':
        return App(Operator.SUB, self, other)

    @ensure_other_is_composable
    def __rsub__(self, other: 'Composable') -> 'App':
        return App(Operator.SUB, other, self)

    def simplify(self) -> 'Composable':
        raise NotImplementedError()

    def materialize(self, ucd: UnicodeCharacterDatabase) -> set[CodePoint]:
        raise NotImplementedError()


@dataclass(frozen=True, slots=True)
class Void(Composable):

    NONE: 'ClassVar[Void]'

    def is_bottom(self) -> bool:
        return True

    def simplify(self) -> Self:
        return self

    def materialize(self, ucd: UnicodeCharacterDatabase) -> set[CodePoint]:
        return set()

    def __repr__(self) -> str:
        return '⊥'

    def __str__(self) -> str:
        return '⊥'

Void.NONE = Void()


@dataclass(frozen=True, slots=True)
class Universe(Composable):

    ALL: 'ClassVar[Universe]'

    def is_top(self) -> bool:
        return True

    def simplify(self) -> Self:
        return self

    def materialize(self, ucd: UnicodeCharacterDatabase) -> set[CodePoint]:
        return set(CodePoint(cp) for cp in CodePointRange.ALL.codepoints())

    def __repr__(self) -> str:
        return '⊤'

    def __str__(self) -> str:
        return '⊤'


Universe.ALL = Universe()


@dataclass(frozen=True, slots=True)
class Prop(Composable):

    property: BinaryProperty | Property

    def is_prop(self) -> bool:
        return True

    def to_prop(self) -> 'Prop':
        return self

    def simplify(self) -> Self:
        return self

    def materialize(self, ucd: UnicodeCharacterDatabase) -> set[CodePoint]:
        return ucd.materialize(self.property)

    def __repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return f'{self.property.__class__.__name__}.{self.property.label}'


@dataclass(frozen=True, slots=True)
class App(Composable):

    op: Operator
    args: tuple[Composable, ...]

    def __init__(self, op: Operator, *args: Composable) -> None:
        object.__setattr__(self, 'op', op)
        object.__setattr__(self, 'args', tuple(args))

    @property
    def only_arg(self) -> Composable:
        actual = len(self.args)
        if actual != 1:
            raise AssertionError(f'{actual} instead of 1 argument')
        return self.args[0]

    def is_app(self) -> bool:
        return True

    def applies(self, op: Operator) -> bool:
        return self.op is op

    def to_app(self) -> 'App':
        return self

    def simplify(self) -> Composable:
        match self.op:
            case Operator.INVERT:
                arg = self.only_arg
                if arg.applies(Operator.INVERT):
                    return arg.to_app().only_arg.simplify()
                return App(Operator.INVERT, self.only_arg.simplify())
            case Operator.AND:
                args = list(dict.fromkeys(itertools.chain.from_iterable(
                    a.to_app().args if a.applies(self.op) else (a,)
                    for a in (a.simplify() for a in self.args)
                )))
                if len(args) == 1:
                    return args[0]
                args = [a for a in args if not a.is_top()]
                if len(args) == 0:
                    return Universe.ALL
                return App(self.op, *args)
            case Operator.OR:
                args = list(dict.fromkeys(itertools.chain.from_iterable(
                    a.to_app().args if a.applies(self.op) else (a,)
                    for a in (a.simplify() for a in self.args)
                )))
                if len(args) == 1:
                    return args[0]
                args = [a for a in args if not a.is_bottom()]
                if len(args) == 0:
                    return Void.NONE
                return App(self.op, *args)
            case _:
                return App(self.op, *(a.simplify() for a in self.args))

    def materialize(self, ucd: UnicodeCharacterDatabase) -> set[CodePoint]:
        if self.op is Operator.INVERT:
            source = self.only_arg.materialize(ucd)
            return {
                cp for cp in CodePointRange.ALL.codepoints() if cp not in source
            }

        assert len(self.args) >= 2, \
            f'{self.op.token}() requires at least 2 arguments but has {len(self.args)}'
        total = self.args[0].materialize(ucd)
        for element in self.args[1:]:
            materialized = element.materialize(ucd)
            total = self.op.fn(total, materialized)
        return total

    def __repr__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        match self.op:
            case Operator.AND:
                return ' & '.join(
                    f'({a})'
                    if a.applies(Operator.SUB) or a.applies(Operator.OR)
                    else str(a)
                    for a in self.args
                )
            case Operator.INVERT:
                expr = self.only_arg
                while expr.applies(Operator.INVERT):
                    expr = expr.to_app().only_arg
                parenthesize = expr.is_app()
                return f'~({self.only_arg})' if parenthesize else f'~{self.only_arg}'
            case Operator.OR:
                return ' | '.join(
                    f'({a})' if a.applies(Operator.SUB) else str(a) for a in self.args
                )
            case Operator.SUB:
                return ' - '.join(f'({a})' if a.is_app() else str(a) for a in self.args)


def extend(property: BinaryProperty | Property) -> Prop:
    return Prop(property)
