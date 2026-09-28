"""Deterministically assemble one-shot actions from approved Rita frames."""

from __future__ import annotations

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SKINS = ("rita_umbral_rose", "rita_moonlit_rose")


def frame(sheet: Image.Image, columns: int, rows: int, index: int) -> Image.Image:
    width = sheet.width // columns
    height = sheet.height // rows
    column, row = index % columns, index // columns
    return sheet.crop((column * width, row * height, (column + 1) * width, (row + 1) * height))


def align_foot(image: Image.Image, target_bottom: int = 495) -> Image.Image:
    """Keep mixed source sheets on the same contact point without scaling."""
    bounds = image.getchannel("A").point(lambda value: 255 if value > 15 else 0).getbbox()
    if bounds is None:
        return image
    offset_y = target_bottom - (bounds[3] - 1)
    aligned = Image.new("RGBA", image.size, (0, 0, 0, 0))
    aligned.alpha_composite(image, (0, offset_y))
    return aligned


def main() -> int:
    for skin_id in SKINS:
        directory = ROOT / "skins" / skin_id / "animations"
        sit = Image.open(directory / "sit_transition.png").convert("RGBA")
        sleep = Image.open(directory / "sleep_react.png").convert("RGBA")
        selected = [
            *(frame(sit, 5, 2, index) for index in (0, 2, 4, 6, 8, 9)),
            *(frame(sleep, 4, 2, index) for index in (0, 2, 4, 6, 7)),
            *(frame(sit, 5, 2, index) for index in (8, 6, 4, 2, 0)),
        ]
        selected = [align_foot(image) for image in selected]
        canvas = Image.new("RGBA", (2048, 2048), (0, 0, 0, 0))
        for index, image in enumerate(selected):
            canvas.alpha_composite(image, ((index % 4) * 512, (index // 4) * 512))
        canvas.save(directory / "sleepy.png", optimize=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
