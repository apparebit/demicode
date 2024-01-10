from pathlib import Path
from typing import ContextManager, Literal, NotRequired, TypeAlias, TypedDict


_ModeT: TypeAlias = str
_SizeT: TypeAlias = tuple[int, int]
_BoxT: TypeAlias = tuple[int, int, int, int]
_ColorT: TypeAlias = int | str | tuple[int, int, int] | tuple[int, int, int, int]


class _Info(TypedDict):
    dpi: float
    icc_profile: NotRequired[bytes]


class Image:
    @property
    def info(self) -> _Info: ...
    @property
    def width(self) -> int: ...
    @property
    def height(self) -> int: ...
    @property
    def size(self) -> _SizeT: ...
    @property
    def mode(self) -> _ModeT: ...

    def getpixel(self, xy: tuple[int, int]) -> _ColorT: ...
    def getbbox(self) -> None | _BoxT: ...
    def copy(self) -> 'Image': ...
    def crop(self, box: _BoxT) -> 'Image': ...
    def convert(self, mode: _ModeT) -> 'Image': ...
    def paste(
        self, im: 'Image', box: _SizeT | _BoxT, mask: None | 'Image' = None
    ) -> 'Image': ...
    def save(
        self, fp: str | Path, dpi: float, icc_profile: None | bytes = None
    ) -> None: ...


def new(
    mode: _ModeT,
    size: _SizeT,
    color: _ColorT = 0,
) -> Image: ...


def open(
    fp: str | Path,
    mode: Literal['r'] = 'r',
    formats: None | tuple[str] | list[str] = None,
) -> ContextManager[Image]: ...
