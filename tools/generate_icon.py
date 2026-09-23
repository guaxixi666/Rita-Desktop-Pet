from __future__ import annotations

import argparse
import struct
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PySide6.QtGui import QGuiApplication, QPainter, QPixmap


def render_png(source_path: Path) -> bytes:
    pixmap = QPixmap(256, 256)
    pixmap.fill(Qt.GlobalColor.transparent)
    sheet = QPixmap(str(source_path))
    if sheet.isNull():
        raise RuntimeError(f"Could not load sprite sheet: {source_path}")
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    painter.drawPixmap(
        QRectF(0, 0, 256, 256),
        sheet,
        QRectF(0, 0, sheet.width() / 3, sheet.height() / 2),
    )
    painter.end()

    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not pixmap.save(buffer, "PNG"):
        raise RuntimeError("Could not encode icon PNG")
    return bytes(data)


def write_ico(path: Path, source_path: Path) -> None:
    png = render_png(source_path)
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(png), 22)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + entry + png)
    path.with_suffix(".png").write_bytes(png)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    app = QGuiApplication.instance() or QGuiApplication([])
    source = Path(__file__).resolve().parents[1] / "assets" / "rita" / "rita_sprite_sheet.png"
    write_ico(args.output, source)
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

