"""Render contact sheets and timed motion previews through the real Qt pet widget."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image, ImageDraw
from PySide6.QtCore import QPoint
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from codex_usage_pet.pet.animator import PetActivity
from codex_usage_pet.skins.loader import SkinRepository
from codex_usage_pet.ui.pet_widget import PetWidget


OUTPUT = ROOT / "artifacts" / "animations"
CANVAS = (280, 280)
ANCHOR = QPoint(CANVAS[0] // 2, CANVAS[1] - 12)
ACTIONS = (
    ("blink", "blink"),
    ("smile", "smile"),
    ("surprised", "surprised"),
    ("wave", "wave"),
    ("tidy_hair", "tidy-hair"),
    ("sit", "sit"),
    ("sleepy", "sleepy"),
)


def _to_pillow(image: QImage) -> Image.Image:
    rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
    return Image.frombuffer(
        "RGBA",
        (rgba.width(), rgba.height()),
        rgba.constBits(),
        "raw",
        "RGBA",
        rgba.bytesPerLine(),
        1,
    ).copy()


def _render_frames(widget: PetWidget, activity: PetActivity | str) -> list[Image.Image]:
    asset = widget.skin.asset_for(activity)
    widget.activity = activity
    rendered: list[Image.Image] = []
    for index in range(asset.frame_count):
        widget._frame_index = index
        widget._prepare_visual()
        QApplication.processEvents()
        pet = _to_pillow(widget.grab().toImage())
        canvas = Image.new("RGBA", CANVAS, "#24222B")
        left = ANCHOR.x() - round(widget.anchor_offset.x())
        top = ANCHOR.y() - round(widget.anchor_offset.y())
        canvas.alpha_composite(pet, (left, top))
        rendered.append(canvas)
    return rendered


def _save_contact_sheet(rows: list[tuple[str, list[Image.Image]]], output: Path) -> None:
    thumb = 132
    label_width = 132
    gap = 6
    columns = max(len(frames) for _name, frames in rows)
    sheet = Image.new(
        "RGB",
        (label_width + columns * (thumb + gap) + gap, len(rows) * (thumb + gap) + gap),
        "#17171D",
    )
    draw = ImageDraw.Draw(sheet)
    for row, (name, frames) in enumerate(rows):
        top = gap + row * (thumb + gap)
        draw.text((12, top + 10), name, fill="#F3ECEE")
        for column, frame in enumerate(frames):
            preview = frame.resize((thumb, thumb), Image.Resampling.LANCZOS).convert("RGB")
            left = label_width + column * (thumb + gap)
            sheet.paste(preview, (left, top))
    sheet.save(output, "PNG")


def main() -> int:
    app = QApplication.instance() or QApplication([])
    packs = SkinRepository([ROOT / "skins"]).scan()
    for skin_id in ("rita_umbral_rose", "rita_moonlit_rose"):
        skin = packs[skin_id]
        widget = PetWidget(skin)
        widget.show()
        app.processEvents()
        destination = OUTPUT / skin_id
        destination.mkdir(parents=True, exist_ok=True)
        contact_rows: list[tuple[str, list[Image.Image]]] = []
        for activity, output_name in ACTIONS:
            frames = _render_frames(widget, activity)
            asset = skin.asset_for(activity)
            durations = list(asset.frame_durations_ms) or [asset.frame_duration_ms(0)] * len(frames)
            frames[0].save(
                destination / f"{output_name}.gif",
                save_all=True,
                append_images=frames[1:],
                duration=durations,
                disposal=2,
                loop=0,
                optimize=False,
            )
            contact_rows.append((output_name, frames))
        _save_contact_sheet(contact_rows, destination / "contact-sheet.png")
        widget.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
