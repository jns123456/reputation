#!/usr/bin/env python3
"""Crop whitespace from the Auth0 Universal Login logo asset."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "static" / "images" / "predictstamp-auth0-logo.jpg"
WHITE_THRESHOLD = 240
PADDING_X = 28
PADDING_Y = 20


def _content_bbox(im: Image.Image) -> tuple[int, int, int, int]:
    rgb = im.convert("RGB")
    w, h = rgb.size
    pixels = rgb.load()
    min_x, min_y, max_x, max_y = w, h, 0, 0
    for y in range(h):
        for x in range(w):
            r, g, b = pixels[x, y]
            if r < WHITE_THRESHOLD or g < WHITE_THRESHOLD or b < WHITE_THRESHOLD:
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
    if max_x <= min_x or max_y <= min_y:
        return 0, 0, w, h
    return min_x, min_y, max_x, max_y


def optimize(source: Path, dest: Path) -> None:
    im = Image.open(source).convert("RGB")
    min_x, min_y, max_x, max_y = _content_bbox(im)
    left = max(0, min_x - PADDING_X)
    top = max(0, min_y - PADDING_Y)
    right = min(im.width, max_x + PADDING_X)
    bottom = min(im.height, max_y + PADDING_Y)
    cropped = im.crop((left, top, right, bottom))
    dest.parent.mkdir(parents=True, exist_ok=True)
    cropped.save(dest, format="JPEG", quality=92, optimize=True)
    print(f"Wrote {dest} ({cropped.width}x{cropped.height})")


if __name__ == "__main__":
    source = ROOT / "static" / "images" / "predictstamp-auth0-logo.jpg"
    if not source.is_file():
        raise SystemExit(f"Missing source image: {source}")
    optimize(source, OUTPUT)
