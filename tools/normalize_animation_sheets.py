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

GENERATED_GRIDS = {
    "tidy_hair-source.png": ("tidy_hair.png", 4, 3),
    "sit_transition-source.png": ("sit_transition.png", 5, 2),
}


def normalize(
    path: Path,
    columns: int,
    rows: int,
    scale: bool,
    *,
    output: Path | None = None,
    adaptive_rows: bool = False,
    preserve_aspect: bool = False,
) -> None:
    source = QImage(str(path)).convertToFormat(QImage.Format.Format_RGBA8888)
    if source.isNull():
        raise ValueError(f"Cannot read {path}")
    target = QImage(columns * 512, rows * 512, QImage.Format.Format_RGBA8888)
    target.fill(Qt.GlobalColor.transparent)
    painter = QPainter(target)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    row_edges = _row_edges(source, rows) if adaptive_rows else [round(i * source.height() / rows) for i in range(rows + 1)]
    for row in range(rows):
        for column in range(columns):
            left = round(column * source.width() / columns)
            right = round((column + 1) * source.width() / columns)
            top = row_edges[row]
            bottom = row_edges[row + 1]
            source_rect = QRectF(left, top, right - left, bottom - top)
            if scale and not preserve_aspect:
                target_rect = QRectF(column * 512, row * 512, 512, 512)
            elif scale:
                safe_size = 480
                ratio = min(safe_size / source_rect.width(), safe_size / source_rect.height())
                width = source_rect.width() * ratio
                height = source_rect.height() * ratio
                target_rect = QRectF(
                    column * 512 + (512 - width) / 2,
                    row * 512 + (512 - height) - 16,
                    width,
                    height,
                )
            else:
                x = column * 512 + (512 - source_rect.width()) / 2
                y = row * 512 + (512 - source_rect.height()) / 2
                target_rect = QRectF(x, y, source_rect.width(), source_rect.height())
            painter.drawImage(target_rect, source, source_rect)
    painter.end()
    target = align_alpha_bottoms(target, columns, rows)
    destination = output or path
    if not target.save(str(destination), "PNG"):
        raise OSError(f"Cannot save {destination}")


def _row_edges(image: QImage, rows: int) -> list[int]:
    """Find quiet alpha seams near nominal row boundaries in generated grids."""
    if rows <= 1:
        return [0, image.height()]
    rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
    data = rgba.constBits()
    stride = rgba.bytesPerLine()
    cell_height = image.height() / rows
    edges = [0]
    for boundary in range(1, rows):
        nominal = round(boundary * cell_height)
        radius = max(8, round(cell_height * 0.16))
        candidates = range(max(edges[-1] + 1, nominal - radius), min(image.height(), nominal + radius + 1))
        seam = min(
            candidates,
            key=lambda y: sum(data[y * stride + x * 4 + 3] > 15 for x in range(image.width())),
        )
        edges.append(seam)
    edges.append(image.height())
    return edges


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
        for source_name, (output_name, columns, rows) in GENERATED_GRIDS.items():
            source_path = ROOT / "artifacts" / "animations" / "sources" / skin_id / source_name
            if not source_path.exists():
                continue
            normalize(
                source_path,
                columns,
                rows,
                True,
                output=directory / output_name,
                adaptive_rows=True,
                preserve_aspect=True,
            )


if __name__ == "__main__":
    main()
