#!/usr/bin/env python3
"""Generate a simple PPM image for demo image-to-video runs."""
from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a sample PPM image.")
    parser.add_argument("output", type=Path, help="Output PPM file path")
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--height", type=int, default=512)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    width = args.width
    height = args.height
    header = f"P6\n{width} {height}\n255\n".encode("ascii")
    pixels = bytearray()
    for y in range(height):
        for x in range(width):
            r = int(255 * x / max(width - 1, 1))
            g = int(255 * y / max(height - 1, 1))
            b = int(255 * (1 - x / max(width - 1, 1)))
            pixels.extend((r, g, b))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(header + pixels)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
