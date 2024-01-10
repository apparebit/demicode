from PIL import Image


def add(
    image1: Image.Image,
    image2: Image.Image,
    scale: float = 1.0,
    offset: float = 0
) -> Image.Image:
    ...


def difference(
    image1: Image.Image,
    image2: Image.Image
) -> Image.Image:
    ...
