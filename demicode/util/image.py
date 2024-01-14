import io
from typing import Callable, cast, TypeAlias

from PIL.Image import Image
from PIL.Image import new as newImage
from PIL.Image import open as openImage
import PIL.ImageChops as ImageChops

from PIL.ImageCms import (
    applyTransform,
    buildTransform,
    createProfile,
    ImageCmsProfile,
    ImageCmsTransform,
)


__all__ = (
    'BoxT',
    'ColorT',
    'HasColorT',
    'SRGB',
    'open',
    'get_profile',
    'convert_to_srgb',
    'resolve_alpha',
    'is_bar',
    'scan_bars',
    'size_matte',
    'crop_box',
)


BoxT: TypeAlias = tuple[int, int, int, int]
ColorT: TypeAlias = str | int | tuple[int, int, int] | tuple[int, int, int, int]
HasColorT: TypeAlias = Callable[[tuple[int, int, int]], bool]

# Strangely, createProfile() returns the underlying _CmsProfile type.
SRGB = ImageCmsProfile(createProfile('sRGB'))

_DEBUG = False
_XFORM_CACHE: dict[tuple[str, str], ImageCmsTransform] = {}

# In the Mac-specific colorspaces, FF0000 becomes E74025 or EB3223. After
# conversion of the screenshot to sRGB, the color is FF0000 again.
_has_color_default: HasColorT
if True:
    _has_color_default = lambda c: c[0] > 0xF0 and c[1] < 0x10 and c[2] < 0x10
else:
    _has_color_default = lambda c: c[0] > 0xE0 and c[1] < 0x48 and c[2] < 0x30


# Re-export for convenience
open = openImage


def get_profile(im: Image) -> ImageCmsProfile:
    icc = im.info.get('icc_profile')
    if icc is None:
        return SRGB
    return ImageCmsProfile(io.BytesIO(icc))


def convert_to_srgb(im: Image, profile: ImageCmsProfile) -> Image:
    if profile == SRGB:
        return im
    label = profile.profile.profile_description, im.mode
    if label not in _XFORM_CACHE:
        _XFORM_CACHE[label] = buildTransform(profile, SRGB, im.mode, im.mode)
    return applyTransform(im, _XFORM_CACHE[label])


def resolve_alpha(im: Image, color: ColorT = 'WHITE') -> Image:
    if im.mode == 'RGB':
        return im
    elif im.mode != 'RGBA':
        raise ValueError(f'unsupported mode "{im.mode}"')
    bg = newImage('RGBA', im.size, color)
    bg.paste(im, (0, 0), im)
    return bg.convert('RGB')


def is_bar(im: Image, line: int, probes: slice, has_color: HasColorT) -> bool:
    if im.mode != 'RGB':
        raise ValueError(f'unsupported mode "{im.mode}"')

    for probe in range(*probes.indices(im.width)):
        pixel = cast(tuple[int, int, int], im.getpixel((probe, line)))
        if _DEBUG:
            print(
                f'pixel {probe:4d}, {line:4d}: '
                f'#{pixel[0]:02x}{pixel[1]:02x}{pixel[2]:02x}'
            )
        if not has_color(pixel):
            return False

    return True


def scan_bars(
    im: Image,
    probes: slice,
    has_color: None | HasColorT = None
) -> list[tuple[int, int]]:
    if im.mode != 'RGB':
        raise ValueError(f'unsupported mode "{im.mode}"')
    if has_color is None:
        has_color = _has_color_default

    indices: list[int] = []

    previously: None | bool = None
    for y in range(im.height):
        bar = is_bar(im, y, probes, has_color)
        if previously == bar:
            continue
        if previously is not None and (not bar or len(indices) > 0):
            # Ignore first line as well as first transition onto bar
            indices.append(y - 1 if bar else y)
        previously = bar

    # Ignore any trailing, unmatched index
    return [(indices[i], indices[i+1]) for i in range(0, len(indices) & ~1, 2)]


def size_matte(
    im: Image,
    color: None | tuple[int, int, int] = None,
    tolerance: int = 3,
) -> None | BoxT:
    if im.mode != 'RGB':
        raise ValueError(f'unsupported mode "{im.mode}"')

    if color is None:
        color = cast(tuple[int, int, int], im.getpixel((0, 0)))

    bg = newImage(im.mode, im.size, color)
    diff = ImageChops.difference(im, bg)
    diff = ImageChops.add(diff, diff, 2.0, -abs(tolerance))
    return diff.getbbox()


def crop_box(im: Image, box: BoxT, padding: int = 0) -> Image:
    return im.crop((
        max(0, box[0] - padding),
        max(0, box[1] - padding),
        min(im.width, box[2] + padding),
        min(im.height, box[3] + padding),
    ))


def box_in_box(inner: BoxT, outer: BoxT) -> BoxT:
    return cast(BoxT, tuple(
        o + i
        for o, i in zip(outer, inner)
    ))
