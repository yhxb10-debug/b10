#!/usr/bin/env python3
"""Simple video generation pipeline inspired by Kling 2.6 workflows.

This script does NOT ship a real Kling model. It provides a modular
"prompt -> storyboard -> frames -> video" pipeline so you can plug in
actual model weights later.
"""
from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import json
import random
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Sequence, Tuple


RGB = Tuple[int, int, int]


@dataclass
class PromptConfig:
    prompt: str
    duration_s: float = 4.0
    fps: int = 12
    width: int = 512
    height: int = 512
    seed: int | None = None


@dataclass
class ScenePlan:
    scene_id: int
    description: str
    start_s: float
    end_s: float


class KlingLikeModel:
    """Placeholder model that generates stylized frames.

    Replace `generate_frames` with real model inference.
    """

    def __init__(self, seed: int | None = None) -> None:
        self._random = random.Random(seed)

    def generate_frames(
        self,
        plan: Sequence[ScenePlan],
        *,
        width: int,
        height: int,
        fps: int,
    ) -> List[List[RGB]]:
        frames: List[List[RGB]] = []
        for scene in plan:
            frame_count = int((scene.end_s - scene.start_s) * fps)
            for frame_index in range(frame_count):
                frames.append(
                    self._render_frame(
                        scene=scene,
                        frame_index=frame_index,
                        total_frames=frame_count,
                        width=width,
                        height=height,
                    )
                )
        return frames

    def generate_frames_from_image(
        self,
        pixels: Sequence[RGB],
        *,
        width: int,
        height: int,
        fps: int,
        duration_s: float,
    ) -> List[List[RGB]]:
        frame_count = int(duration_s * fps)
        frames: List[List[RGB]] = []
        for frame_index in range(frame_count):
            frames.append(
                self._render_image_frame(
                    pixels=pixels,
                    width=width,
                    height=height,
                    frame_index=frame_index,
                    total_frames=frame_count,
                )
            )
        return frames

    def _render_frame(
        self,
        *,
        scene: ScenePlan,
        frame_index: int,
        total_frames: int,
        width: int,
        height: int,
    ) -> List[RGB]:
        base_color = self._scene_color(scene.scene_id)
        progress = frame_index / max(total_frames - 1, 1)
        wobble = self._random.randint(-10, 10)
        pixels: List[RGB] = []
        for y in range(height):
            for x in range(width):
                mix = (x / max(width - 1, 1)) * 0.6 + (y / max(height - 1, 1)) * 0.4
                shade = int(80 + 120 * progress + wobble)
                pixels.append(
                    (
                        _clamp(base_color[0] + int(shade * mix), 0, 255),
                        _clamp(base_color[1] + int(shade * (1 - mix)), 0, 255),
                        _clamp(base_color[2] + int(shade * 0.5), 0, 255),
                    )
                )
        return pixels

    def _scene_color(self, scene_id: int) -> RGB:
        palette = [
            (30, 120, 200),
            (160, 90, 200),
            (40, 160, 120),
            (200, 140, 60),
        ]
        return palette[scene_id % len(palette)]

    def _render_image_frame(
        self,
        *,
        pixels: Sequence[RGB],
        width: int,
        height: int,
        frame_index: int,
        total_frames: int,
    ) -> List[RGB]:
        progress = frame_index / max(total_frames - 1, 1)
        tint = int(20 * progress)
        output: List[RGB] = []
        for r, g, b in pixels:
            output.append(
                (
                    _clamp(r + tint, 0, 255),
                    _clamp(g + int(tint * 0.6), 0, 255),
                    _clamp(b + int(tint * 0.3), 0, 255),
                )
            )
        return output


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def build_storyboard(config: PromptConfig) -> List[ScenePlan]:
    """Create a simple storyboard that splits the prompt into two scenes."""
    midpoint = config.duration_s / 2
    return [
        ScenePlan(
            scene_id=0,
            description=f"Opening shot: {config.prompt}",
            start_s=0.0,
            end_s=midpoint,
        ),
        ScenePlan(
            scene_id=1,
            description=f"Closing shot: {config.prompt}",
            start_s=midpoint,
            end_s=config.duration_s,
        ),
    ]


def write_ppm(path: Path, width: int, height: int, pixels: Sequence[RGB]) -> None:
    header = f"P6\n{width} {height}\n255\n".encode("ascii")
    with path.open("wb") as handle:
        handle.write(header)
        for r, g, b in pixels:
            handle.write(bytes((r, g, b)))


def encode_video(
    frames_dir: Path,
    output_path: Path,
    fps: int,
) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    input_pattern = str(frames_dir / "frame_%05d.ppm")
    command = [
        ffmpeg,
        "-y",
        "-framerate",
        str(fps),
        "-i",
        input_pattern,
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]
    subprocess.run(command, check=False)
    return output_path.exists()


def ensure_output_dir(base_dir: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = base_dir / f"render_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def read_ppm(path: Path) -> Tuple[int, int, List[RGB]]:
    data = path.read_bytes()
    if not data.startswith(b"P6"):
        raise ValueError("Only binary P6 PPM files are supported.")
    tokens: List[bytes] = []
    index = 2
    while len(tokens) < 3 and index < len(data):
        if data[index:index + 1] in (b"\n", b"\r", b" ", b"\t"):
            index += 1
            continue
        if data[index:index + 1] == b"#":
            while index < len(data) and data[index:index + 1] not in (b"\n", b"\r"):
                index += 1
            continue
        start = index
        while index < len(data) and data[index:index + 1] not in (b"\n", b"\r", b" ", b"\t"):
            index += 1
        tokens.append(data[start:index])
    if len(tokens) < 3:
        raise ValueError("Invalid PPM header.")
    width = int(tokens[0])
    height = int(tokens[1])
    max_value = int(tokens[2])
    if max_value != 255:
        raise ValueError("Only max value 255 is supported for PPM.")
    pixel_data = data[index:]
    expected = width * height * 3
    if len(pixel_data) < expected:
        raise ValueError("PPM file is truncated.")
    pixels: List[RGB] = []
    for offset in range(0, expected, 3):
        r = pixel_data[offset]
        g = pixel_data[offset + 1]
        b = pixel_data[offset + 2]
        pixels.append((r, g, b))
    return width, height, pixels


def load_image_pixels(path: Path, width: int, height: int) -> List[RGB]:
    if importlib.util.find_spec("PIL") is not None:
        from PIL import Image

        with Image.open(path) as image:
            image = image.convert("RGB").resize((width, height))
            return list(image.getdata())
    if path.suffix.lower() == ".ppm":
        ppm_width, ppm_height, pixels = read_ppm(path)
        if ppm_width != width or ppm_height != height:
            raise ValueError(
                f"PPM dimensions {ppm_width}x{ppm_height} do not match {width}x{height}."
            )
        return pixels
    raise ValueError("Pillow is required for non-PPM images. Install pillow to proceed.")


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a video via a Kling-like placeholder pipeline.",
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        default="",
        help="Prompt describing the desired video (optional when using --image)",
    )
    parser.add_argument(
        "--image",
        type=Path,
        help="Path to a source image for image-to-video generation",
    )
    parser.add_argument("--duration", type=float, default=4.0, help="Video duration in seconds")
    parser.add_argument("--fps", type=int, default=12, help="Frames per second")
    parser.add_argument("--width", type=int, default=512, help="Frame width")
    parser.add_argument("--height", type=int, default=512, help="Frame height")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs"),
        help="Base output directory",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    if not args.prompt and not args.image:
        raise SystemExit("Provide a prompt or an --image for video generation.")
    config = PromptConfig(
        prompt=args.prompt or (f"Image-driven clip from {args.image.name}" if args.image else ""),
        duration_s=args.duration,
        fps=args.fps,
        width=args.width,
        height=args.height,
        seed=args.seed,
    )
    output_dir = ensure_output_dir(args.output_dir)
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    storyboard = build_storyboard(config)
    plan_path = output_dir / "storyboard.json"
    plan_path.write_text(
        json.dumps([dataclasses.asdict(scene) for scene in storyboard], indent=2),
        encoding="utf-8",
    )

    model = KlingLikeModel(seed=config.seed)
    if args.image:
        pixels = load_image_pixels(args.image, config.width, config.height)
        frames = model.generate_frames_from_image(
            pixels,
            width=config.width,
            height=config.height,
            fps=config.fps,
            duration_s=config.duration_s,
        )
    else:
        frames = model.generate_frames(
            storyboard,
            width=config.width,
            height=config.height,
            fps=config.fps,
        )

    for index, pixels in enumerate(frames, start=1):
        frame_path = frames_dir / f"frame_{index:05d}.ppm"
        write_ppm(frame_path, config.width, config.height, pixels)

    video_path = output_dir / "output.mp4"
    encoded = encode_video(frames_dir, video_path, config.fps)
    if encoded:
        print(f"Video written to {video_path}")
    else:
        print("ffmpeg not found; frames written only.")
    print(f"Storyboard saved to {plan_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
