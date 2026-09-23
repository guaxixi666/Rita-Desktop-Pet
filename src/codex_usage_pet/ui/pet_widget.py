from __future__ import annotations

import math

from PySide6.QtCore import QEasingCurve, QEvent, QPropertyAnimation, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QPainter, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

from codex_usage_pet.pet.animator import PetActivity, PetBehaviorController
from codex_usage_pet.pet.states import PetState
from codex_usage_pet.services.paths import resource_path

from . import theme


class PetWidget(QWidget):
    clicked = Signal()

    _CELLS = {
        PetActivity.IDLE: (0, 0),
        PetActivity.WALK: (1, 0),
        PetActivity.SIT: (2, 0),
        PetActivity.STRETCH: (0, 1),
        PetActivity.CRITICAL: (1, 1),
        PetActivity.SLEEP: (2, 1),
    }

    # The hand-painted poses have intentionally different silhouettes.  Keep
    # their visible mass aligned beside the bubble instead of centring the
    # transparent cell padding (which makes the narrow idle pose look remote).
    _X_NUDGE = {
        PetActivity.IDLE: -37.0,
        PetActivity.WALK: -22.0,
        PetActivity.SIT: -4.0,
        PetActivity.STRETCH: -19.0,
        PetActivity.CRITICAL: -10.0,
        PetActivity.SLEEP: -10.0,
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(232, 244)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.state = PetState.NORMAL
        self.behavior = PetBehaviorController()
        self.activity = PetActivity.IDLE
        self._frame = 0
        self._hovered = False
        self._sheet = QPixmap(str(resource_path("assets/rita/rita_sprite_sheet.png")))

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)
        self._transition = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._transition.setDuration(260)
        self._transition.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._timer = QTimer(self)
        self._timer.setInterval(700)
        self._timer.timeout.connect(self._advance)
        self._timer.start()

    @property
    def sprite_loaded(self) -> bool:
        return not self._sheet.isNull()

    def set_state(self, state: PetState) -> None:
        changed = state is not self.state
        self.state = state
        self.activity = self.behavior.set_quota_state(state)
        self.setToolTip(f"Rita · {state.value} · {self.activity.value}")
        if changed:
            self._transition.stop()
            self._transition.setStartValue(0.58)
            self._transition.setEndValue(1.0)
            self._transition.start()
        self.update()

    def enterEvent(self, event: QEvent) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def _advance(self) -> None:
        self._frame = (self._frame + 1) % 8
        self.activity = self.behavior.advance()
        self.setToolTip(f"Rita · {self.state.value} · {self.activity.value}")
        self.update()

    def paintEvent(self, _event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        if self._sheet.isNull():
            painter.setPen(theme.ROSE_PALE)
            painter.setFont(theme.font(10))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Rita asset unavailable")
            return

        column, row = self._CELLS[self.activity]
        cell_width = self._sheet.width() / 3
        cell_height = self._sheet.height() / 2
        source = QRectF(column * cell_width, row * cell_height, cell_width, cell_height)

        base = 222.0
        scale = 1.025 if self._hovered else 1.0
        size = base * scale
        # The source cells intentionally include replacement-safe padding.
        # Nudge the visible figure toward the bubble so the two read as one
        # compact desktop composition instead of separate floating islands.
        x = (self.width() - size) / 2 + self._X_NUDGE[self.activity]
        y = self.height() - size - 3
        if self.activity not in (PetActivity.SIT, PetActivity.CRITICAL, PetActivity.SLEEP):
            y += math.sin(self._frame * math.pi / 4) * 1.8
        if self.activity is PetActivity.WALK:
            x += math.sin(self._frame * math.pi / 4) * 3.2

        target = QRectF(x, y, size, size)
        painter.save()
        if self._hovered:
            center = target.center()
            painter.translate(center)
            painter.rotate(-1.0)
            painter.translate(-center)
        if self.state is PetState.EMPTY:
            painter.setOpacity(0.72)
        elif self.state is PetState.CRITICAL:
            painter.setOpacity(0.88)
        painter.drawPixmap(target, self._sheet, source)
        painter.restore()

        if self.activity is PetActivity.IDLE and self._frame == 7:
            # A tiny eyelid overlay creates an occasional blink without a
            # second bitmap and stays aligned with the normalized idle frame.
            eye_x = target.left() + target.width() * 0.37
            eye_y = target.top() + target.height() * 0.385
            pen = QPen(theme.ROSE_DEEP, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(int(eye_x - 5), int(eye_y), int(eye_x + 5), int(eye_y + 1))

