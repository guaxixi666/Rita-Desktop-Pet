"""Normalize generated animation grids to square 512 px transparent cells."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QImage, QPainter


ROOT = Path(__file__).resolve().parents[1]
GRIDS = {
    "blink.png": (3, 2, True),
    "hover.png": (3, 2, True),
    "click.png": (4, 2, False),
    "wave.png": (4, 2, False),
    "stretch.png": (4, 2, False),
    "sleep_react.png": (4, 2, True),
}


def normalize(path: Path, columns: int, rows: int, scale: bool) -> None:
    source = QImage(str(path)).convertToFormat(QImage.Format.Format_RGBA8888)
    if source.isNull():
        raise ValueError(f"Cannot read {path}")
    target = QImage(columns * 512, rows * 512, QImage.Format.Format_RGBA8888)
    target.fill(Qt.GlobalColor.transparent)
    painter = QPainter(target)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    for row in range(rows):
        for column in range(columns):
            left = round(column * source.width() / columns)
            right = round((column + 1) * source.width() / columns)
            top = round(row * source.height() / rows)
            bottom = round((row + 1) * source.height() / rows)
            source_rect = QRectF(left, top, right - left, bottom - top)
            if scale:
                target_rect = QRectF(column * 512, row * 512, 512, 512)
            else:
                x = column * 512 + (512 - source_rect.width()) / 2
                y = row * 512 + (512 - source_rect.height()) / 2
                target_rect = QRectF(x, y, source_rect.width(), source_rect.height())
            painter.drawImage(target_rect, source, source_rect)
    painter.end()
    target = align_alpha_bottoms(target, columns, rows)
    if not target.save(str(path), "PNG"):
        raise OSError(f"Cannot save {path}")


def alpha_bounds(image: QImage, threshold: int = 15) -> QRect:
    rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
    data = rgba.constBits()
    stride = rgba.bytesPerLine()
    left, top = rgba.width(), rgba.height()
    right = bottom = -1
    for y in range(rgba.height()):
        for x in range(rgba.width()):
            if data[y * stride + x * 4 + 3] > threshold:
                left, top = min(left, x), min(top, y)
                right, bottom = max(right, x), max(bottom, y)
    return QRect(left, top, right - left + 1, bottom - top + 1)


def align_alpha_bottoms(sheet: QImage, columns: int, rows: int) -> QImage:
    frames = [
        sheet.copy(column * 512, row * 512, 512, 512)
        for row in range(rows)
        for column in range(columns)
    ]
    bottoms = [alpha_bounds(frame).bottom() for frame in frames]
    target_bottom = max(bottoms)
    aligned = QImage(sheet.size(), QImage.Format.Format_RGBA8888)
    aligned.fill(Qt.GlobalColor.transparent)
    painter = QPainter(aligned)
    for index, (frame, bottom) in enumerate(zip(frames, bottoms, strict=True)):
        column, row = index % columns, index // columns
        painter.drawImage(column * 512, row * 512 + target_bottom - bottom, frame)
    painter.end()
    return aligned


def main() -> None:
    for skin_id in ("rita_umbral_rose", "rita_moonlit_rose"):
        directory = ROOT / "skins" / skin_id / "animations"
        for filename, (columns, rows, scale) in GRIDS.items():
            normalize(directory / filename, columns, rows, scale)


if __name__ == "__main__":
    main()
