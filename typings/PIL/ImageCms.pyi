from enum import IntEnum
from typing import BinaryIO, Literal
from PIL import Image


class Intent(IntEnum):
    PERCEPTUAL: int
    RELATIVE_COLORIMETRIC: int
    SATURATION: int
    ABSOLUTE_COLORIMETRIC: int


class _CmsProfile:
    @property
    def profile_description(self) -> str: ...


class ImageCmsProfile:
    def __init__(self, profile: str | BinaryIO | _CmsProfile) -> None: ...
    @property
    def profile(self) -> _CmsProfile: ...
    def tobytes(self) -> bytes: ...


class ImageCmsTransform:
    ...


def createProfile(
    colorSpace: Literal['LAB', 'XYZ', 'sRGB'],
    colorTemp: int = -1
) -> _CmsProfile: ...


def buildTransform(
    inputProfile: ImageCmsProfile,
    outputProfile: ImageCmsProfile,
    inMode: str,
    outMode: str,
    renderingIntent: Intent = Intent.PERCEPTUAL,
    flags: int = 0
) -> ImageCmsTransform:
    ...


def applyTransform(
    im: Image.Image,
    transform: ImageCmsTransform,
    inPlace: bool = False,
) -> Image.Image:
    ...
