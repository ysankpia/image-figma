from __future__ import annotations

from collections import Counter

from PIL import Image

from .schema import BBox


def sample_background(image: Image.Image) -> str:
    w, h = image.size
    pixels = []
    for x, y in [(2, 2), (w - 3, 2), (2, h - 3), (w - 3, h - 3)]:
        pixels.append(image.getpixel((x, y))[:3])
    return rgb_to_hex(tuple(sum(pixel[i] for pixel in pixels) // len(pixels) for i in range(3)))


def sample_fill(image: Image.Image, box: BBox) -> str:
    crop = image.crop((box.x, box.y, box.x2, box.y2)).convert("RGB")
    if crop.width <= 0 or crop.height <= 0:
        return "#E5E7EB"
    thumb = crop.resize((min(24, crop.width), min(24, crop.height)))
    pixels = [quantize(pixel) for pixel in image_pixels(thumb)]
    if not pixels:
        return "#E5E7EB"
    color, _ = Counter(pixels).most_common(1)[0]
    return rgb_to_hex(color)


def sample_text_color(image: Image.Image, box: BBox) -> str:
    crop = image.crop((box.x, box.y, box.x2, box.y2)).convert("RGB")
    pixels = list(image_pixels(crop))
    if not pixels:
        return "#111111"
    dark = [pixel for pixel in pixels if luminance(pixel) < 128]
    if len(dark) >= max(4, len(pixels) // 20):
        avg = tuple(sum(pixel[i] for pixel in dark) // len(dark) for i in range(3))
        return rgb_to_hex(avg)
    return "#111111"


def quantize(pixel: tuple[int, int, int]) -> tuple[int, int, int]:
    return tuple((channel // 16) * 16 for channel in pixel)


def luminance(pixel: tuple[int, int, int]) -> float:
    return 0.2126 * pixel[0] + 0.7152 * pixel[1] + 0.0722 * pixel[2]


def rgb_to_hex(pixel: tuple[int, int, int]) -> str:
    return f"#{pixel[0]:02X}{pixel[1]:02X}{pixel[2]:02X}"


def image_pixels(image: Image.Image):
    getter = getattr(image, "get_flattened_data", None)
    if getter is not None:
        return getter()
    return image.getdata()
