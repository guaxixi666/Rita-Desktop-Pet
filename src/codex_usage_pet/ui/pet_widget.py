from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from codex_usage_pet.pet.states import PetState


class PetWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(150, 170)
        self.state = PetState.NORMAL
        self._frame = 0
        timer = QTimer(self)
        timer.setInterval(700)
        timer.timeout.connect(self._advance)
        timer.start()

    def set_state(self, state: PetState) -> None:
        self.state = state
        self.update()

    def _advance(self) -> None:
        self._frame = (self._frame + 1) % 8
        self.update()

    def paintEvent(self, _event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bounce = 0 if self.state in (PetState.EMPTY, PetState.CRITICAL) else math.sin(self._frame * math.pi / 4) * 2
        painter.translate(0, bounce)
        outline = QPen(QColor("#393342"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(outline)
        color = {
            PetState.NORMAL: "#b9a7ff",
            PetState.LOW: "#e2bd73",
            PetState.CRITICAL: "#d88b8b",
            PetState.EMPTY: "#8c91a3",
            PetState.RECOVERED: "#73d9b0",
        }[self.state]
        painter.setBrush(QColor(color))

        if self.state is PetState.EMPTY:
            painter.drawEllipse(QRectF(24, 92, 106, 54))
            head = QRectF(18, 62, 70, 66)
        else:
            painter.drawEllipse(QRectF(37, 82, 82, 72))
            head = QRectF(24, 35 if self.state is PetState.NORMAL else 49, 88, 83)
        painter.drawEllipse(head)

        ears = QPainterPath()
        ears.moveTo(head.left() + 8, head.top() + 17)
        ears.lineTo(head.left() + 17, head.top() - 10)
        ears.lineTo(head.left() + 35, head.top() + 8)
        ears.moveTo(head.right() - 35, head.top() + 8)
        ears.lineTo(head.right() - 17, head.top() - 10)
        ears.lineTo(head.right() - 8, head.top() + 17)
        painter.drawPath(ears)

        eye_y = head.top() + 39
        face_pen = QPen(QColor("#393342"), 4)
        face_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(face_pen)
        if self.state in (PetState.EMPTY, PetState.CRITICAL):
            painter.drawLine(QPointF(head.left() + 24, eye_y), QPointF(head.left() + 36, eye_y + 2))
            painter.drawLine(QPointF(head.right() - 36, eye_y + 2), QPointF(head.right() - 24, eye_y))
        else:
            blink = self._frame == 7 and self.state is PetState.NORMAL
            if blink:
                painter.drawLine(QPointF(head.left() + 24, eye_y), QPointF(head.left() + 36, eye_y))
                painter.drawLine(QPointF(head.right() - 36, eye_y), QPointF(head.right() - 24, eye_y))
            else:
                painter.drawEllipse(QPointF(head.left() + 30, eye_y), 2.5, 4.5)
                painter.drawEllipse(QPointF(head.right() - 30, eye_y), 2.5, 4.5)
        mouth_pen = QPen(QColor("#664d65"), 3)
        mouth_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(mouth_pen)
        mouth_y = eye_y + 19
        if self.state in (PetState.CRITICAL, PetState.EMPTY):
            painter.drawArc(QRectF(head.center().x() - 8, mouth_y, 16, 11), 0, 180 * 16)
        else:
            painter.drawArc(QRectF(head.center().x() - 9, mouth_y - 5, 9, 9), 180 * 16, 180 * 16)
            painter.drawArc(QRectF(head.center().x(), mouth_y - 5, 9, 9), 180 * 16, 180 * 16)

        painter.setPen(outline)
        if self.state is not PetState.EMPTY:
            tail_wave = 7 if self._frame % 2 else -4
            painter.drawArc(QRectF(103, 91 + tail_wave / 2, 38, 54), -80 * 16, 190 * 16)
        else:
            painter.setPen(QPen(QColor("#d8dcff"), 2))
            painter.drawText(QRectF(104, 50, 35, 25), Qt.AlignmentFlag.AlignCenter, "Z z")
