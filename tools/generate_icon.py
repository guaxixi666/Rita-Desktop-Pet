from __future__ import annotations

import argparse
import struct
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPainterPath, QPen, QPixmap


def render_png() -> bytes:
    pixmap = QPixmap(256, 256)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    painter.setPen(QPen(QColor("#393342"), 10))
    painter.setBrush(QColor("#9b87f5"))
    painter.drawEllipse(QRectF(38, 38, 180, 180))

    ears = QPainterPath()
    ears.moveTo(55, 87)
    ears.lineTo(72, 25)
    ears.lineTo(111, 64)
    ears.moveTo(145, 64)
    ears.lineTo(184, 25)
    ears.lineTo(201, 87)
    painter.drawPath(ears)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#f7f3ff"))
    painter.drawEllipse(QPointF(96, 116), 10, 16)
    painter.drawEllipse(QPointF(160, 116), 10, 16)

    mouth = QPen(QColor("#594b72"), 8)
    mouth.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(mouth)
    painter.drawArc(QRectF(105, 132, 24, 23), 180 * 16, 180 * 16)
    painter.drawArc(QRectF(128, 132, 24, 23), 180 * 16, 180 * 16)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#65d6a6"))
    for index, height in enumerate((18, 31, 44, 55)):
        painter.drawRoundedRect(QRectF(62 + index * 34, 194 - height, 22, height), 6, 6)
    painter.end()

    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not pixmap.save(buffer, "PNG"):
        raise RuntimeError("Could not encode icon PNG")
    return bytes(data)


def write_ico(path: Path) -> None:
    png = render_png()
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
    write_ico(args.output)
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

