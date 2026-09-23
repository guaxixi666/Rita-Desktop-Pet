from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QEvent, QPropertyAnimation, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

from codex_usage_pet.pet.animator import PetActivity, PetBehaviorController
from codex_usage_pet.pet.states import PetState
from codex_usage_pet.skins.models import SkinPack

from . import theme


class PetWidget(QWidget):
    clicked = Signal()

    def __init__(self, skin: SkinPack, parent: QWidget | None = None) -> None:
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
        self.skin = skin
        self._pixmaps: dict[Path, QPixmap] = {}
        self.apply_skin(skin)

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
        asset = self.skin.asset_for(self.activity)
        pixmap = self._pixmaps.get(asset.path)
        return pixmap is not None and not pixmap.isNull()

    def apply_skin(self, skin: SkinPack) -> None:
        self.skin = skin
        self._pixmaps = {asset.path: QPixmap(str(asset.path)) for asset in skin.states.values()}
        self.setToolTip(f"{skin.name} · {self.state.value} · {self.activity.value}")
        self.update()

    def set_state(self, state: PetState) -> None:
        changed = state is not self.state
        self.state = state
        self.activity = self.behavior.set_quota_state(state)
        self.setToolTip(f"{self.skin.name} · {state.value} · {self.activity.value}")
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
        self.setToolTip(f"{self.skin.name} · {self.state.value} · {self.activity.value}")
        self.update()

    def paintEvent(self, _event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        asset = self.skin.asset_for(self.activity)
        pixmap = self._pixmaps.get(asset.path)
        if pixmap is None or pixmap.isNull():
            painter.setPen(self.skin.theme.low)
            painter.setFont(theme.font(10))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Skin asset unavailable")
            return

        if asset.cell is None:
            source = QRectF(0, 0, pixmap.width(), pixmap.height())
        else:
            columns, rows = asset.grid
            cell_width = pixmap.width() / columns
            cell_height = pixmap.height() / rows
            source = QRectF(
                asset.cell[0] * cell_width,
                asset.cell[1] * cell_height,
                cell_width,
                cell_height,
            )

        scale = 1.025 if self._hovered else 1.0
        width = self.skin.preferred_width * scale
        height = self.skin.preferred_height * scale
        x = (self.width() - width) / 2 + self.skin.anchor_x + asset.offset_x
        y = self.height() - height + self.skin.anchor_y + asset.offset_y
        if self.activity not in (PetActivity.SIT, PetActivity.CRITICAL, PetActivity.SLEEP):
            y += math.sin(self._frame * math.pi / 4) * 1.8
        if self.activity is PetActivity.WALK:
            x += math.sin(self._frame * math.pi / 4) * 3.2

        target = QRectF(x, y, width, height)
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
        painter.drawPixmap(target, pixmap, source)
        painter.restore()

        if self.activity is PetActivity.IDLE and self._frame == 7:
            eye_x = target.left() + target.width() * 0.37
            eye_y = target.top() + target.height() * 0.385
            pen = QPen(
                QColor(self.skin.theme.critical),
                2.2,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
            )
            painter.setPen(pen)
            painter.drawLine(int(eye_x - 5), int(eye_y), int(eye_x + 5), int(eye_y + 1))
