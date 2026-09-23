from __future__ import annotations

import math
import random
import time
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QEvent, QPointF, QPropertyAnimation, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

from codex_usage_pet.pet.animator import PetActivity, PetBehaviorController
from codex_usage_pet.pet.states import PetState
from codex_usage_pet.skins.models import SkinPack, SkinStateAsset

from . import theme


def alpha_bounding_rect(image: QImage, threshold: int = 15) -> QRect:
    """Return the smallest rectangle containing pixels above alpha threshold."""
    if image.isNull() or image.width() <= 0 or image.height() <= 0:
        return QRect()
    rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
    data = rgba.constBits()
    stride = rgba.bytesPerLine()
    left, top = rgba.width(), rgba.height()
    right = bottom = -1
    for y in range(rgba.height()):
        row = y * stride
        for x in range(rgba.width()):
            if data[row + x * 4 + 3] > threshold:
                left = min(left, x)
                top = min(top, y)
                right = max(right, x)
                bottom = max(bottom, y)
    if right < left or bottom < top:
        return QRect(0, 0, rgba.width(), rgba.height())
    return QRect(left, top, right - left + 1, bottom - top + 1)


class PetWidget(QWidget):
    clicked = Signal()
    visual_bounds_changed = Signal()

    CANVAS_WIDTH = 232.0
    CANVAS_HEIGHT = 244.0
    SAFE_PADDING = 4
    HOVER_COOLDOWN_SECONDS = 1.5
    CLICK_COOLDOWN_SECONDS = 1.0
    IDLE_INTERVAL_MIN_MS = 30_000
    IDLE_INTERVAL_MAX_MS = 120_000

    def __init__(
        self,
        skin: SkinPack,
        parent: QWidget | None = None,
        *,
        rng: random.Random | None = None,
    ) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.state = PetState.NORMAL
        self.behavior = PetBehaviorController()
        self.activity = PetActivity.IDLE
        self.skin = skin
        self._rng = rng or random.Random()
        self._pixmaps: dict[Path, QPixmap] = {}
        self._bounds: dict[tuple[Path, tuple[int, int] | None, tuple[int, int]], QRect] = {}
        self._source = QRectF()
        self._target = QRectF()
        self._full_target = QRectF()
        self._visual_logical_origin = QPointF()
        self._anchor_offset = QPointF()
        self._action_activity: PetActivity | None = None
        self._last_hover_at = -10_000.0
        self._last_click_at = -10_000.0

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)
        self._transition = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._transition.setDuration(260)
        self._transition.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._action_timer = QTimer(self)
        self._action_timer.setSingleShot(True)
        self._action_timer.timeout.connect(self._finish_action)
        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self._run_idle_action)

        self.apply_skin(skin)
        self._schedule_idle_action()

    @property
    def sprite_loaded(self) -> bool:
        asset = self.skin.asset_for(self.activity)
        pixmap = self._pixmaps.get(asset.path)
        return pixmap is not None and not pixmap.isNull()

    @property
    def anchor_offset(self) -> QPointF:
        """Bottom-center canvas anchor expressed in current widget coordinates."""
        return QPointF(self._anchor_offset)

    @property
    def idle_timer_interval(self) -> int:
        return self._idle_timer.interval()

    def apply_skin(self, skin: SkinPack) -> None:
        self.skin = skin
        self._pixmaps = {asset.path: QPixmap(str(asset.path)) for asset in skin.states.values()}
        self._bounds.clear()
        self._prepare_visual()
        self.setToolTip(f"{skin.name} · {self.state.value} · {self.activity.value}")
        self.update()

    def set_state(self, state: PetState) -> None:
        changed = state is not self.state
        self.state = state
        self._action_timer.stop()
        self._action_activity = None
        self.activity = self.behavior.set_quota_state(state)
        self._prepare_visual()
        self.setToolTip(f"{self.skin.name} · {state.value} · {self.activity.value}")
        if changed:
            self._transition.stop()
            self._transition.setStartValue(0.58)
            self._transition.setEndValue(1.0)
            self._transition.start()
        self.update()

    def play_hover_reaction(self, now: float | None = None) -> bool:
        moment = time.monotonic() if now is None else now
        if self.state is not PetState.NORMAL or self._action_activity is not None:
            return False
        if moment - self._last_hover_at < self.HOVER_COOLDOWN_SECONDS:
            return False
        activity = None
        if self.skin.has_explicit_state(PetActivity.HOVER):
            activity = PetActivity.HOVER
        elif self.skin.has_explicit_state(PetActivity.BLINK):
            activity = PetActivity.BLINK
        if activity is None:
            return False
        self._last_hover_at = moment
        return self._start_action(activity, 520)

    def play_click_reaction(self, now: float | None = None) -> bool:
        moment = time.monotonic() if now is None else now
        if self.state in {PetState.CRITICAL, PetState.EMPTY, PetState.RECOVERED}:
            return False
        if moment - self._last_click_at < self.CLICK_COOLDOWN_SECONDS:
            return False
        if not self.skin.has_explicit_state(PetActivity.CLICK):
            return False
        # Click outranks hover and autonomous idle actions.  This matters in
        # real use because a pointer entry usually happens just before a click.
        if self._action_activity is PetActivity.CLICK:
            return False
        if self._action_activity is not None:
            self._action_timer.stop()
            self._action_activity = None
        self._last_click_at = moment
        return self._start_action(PetActivity.CLICK, 720)

    def enterEvent(self, event: QEvent) -> None:
        self.play_hover_reaction()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        super().leaveEvent(event)

    def _advance(self) -> None:
        """Compatibility hook: restore the quota-driven base pose without motion."""
        if self._action_activity is None:
            self.activity = self.behavior.advance()
            self._prepare_visual()
            self.update()

    def _start_action(self, activity: PetActivity, duration_ms: int) -> bool:
        if self._action_activity is not None:
            return False
        self._action_activity = activity
        self.activity = activity
        self._prepare_visual()
        self._action_timer.start(duration_ms)
        self.setToolTip(f"{self.skin.name} · {self.state.value} · {activity.value}")
        self.update()
        return True

    def _finish_action(self) -> None:
        self._action_activity = None
        self.activity = self.behavior.set_quota_state(self.state)
        self._prepare_visual()
        self.setToolTip(f"{self.skin.name} · {self.state.value} · {self.activity.value}")
        self.update()

    def _schedule_idle_action(self) -> None:
        interval = self._rng.randint(self.IDLE_INTERVAL_MIN_MS, self.IDLE_INTERVAL_MAX_MS)
        self._idle_timer.start(interval)

    def _run_idle_action(self) -> None:
        try:
            if (
                self.state is PetState.NORMAL
                and self._action_activity is None
                and self._rng.random() < 0.7
            ):
                candidates = [
                    activity
                    for activity in (PetActivity.BLINK, PetActivity.STRETCH, PetActivity.SIT)
                    if self.skin.has_explicit_state(activity)
                ]
                if candidates:
                    activity = self._rng.choice(candidates)
                    duration = 460 if activity is PetActivity.BLINK else 850
                    self._start_action(activity, duration)
        finally:
            self._schedule_idle_action()

    def _prepare_visual(self) -> None:
        asset = self.skin.asset_for(self.activity)
        pixmap = self._pixmaps.get(asset.path)
        if pixmap is None or pixmap.isNull():
            old_size = self.size()
            self.setFixedSize(96, 96)
            self._source = QRectF()
            self._target = QRectF(self.SAFE_PADDING, self.SAFE_PADDING, 88, 88)
            self._anchor_offset = QPointF(48, 92)
            if self.size() != old_size:
                self.visual_bounds_changed.emit()
            return

        columns, rows = asset.grid
        cell_width = pixmap.width() / columns
        cell_height = pixmap.height() / rows
        column, row = asset.cell or (0, 0)
        cell_rect = QRect(
            round(column * cell_width),
            round(row * cell_height),
            round(cell_width),
            round(cell_height),
        )
        key = (asset.path, asset.cell, asset.grid)
        bounds = self._bounds.get(key)
        if bounds is None:
            bounds = alpha_bounding_rect(pixmap.toImage().copy(cell_rect), 15)
            self._bounds[key] = bounds

        scale_x = self.skin.preferred_width / cell_width
        scale_y = self.skin.preferred_height / cell_height
        full_left = (
            (self.CANVAS_WIDTH - self.skin.preferred_width) / 2
            + self.skin.anchor_x
            + asset.offset_x
        )
        full_top = (
            self.CANVAS_HEIGHT
            - self.skin.preferred_height
            + self.skin.anchor_y
            + asset.offset_y
        )
        logical_left = full_left + bounds.x() * scale_x
        logical_top = full_top + bounds.y() * scale_y
        visual_width = max(1.0, bounds.width() * scale_x)
        visual_height = max(1.0, bounds.height() * scale_y)
        widget_width = math.ceil(visual_width) + self.SAFE_PADDING * 2
        widget_height = math.ceil(visual_height) + self.SAFE_PADDING * 2
        old_size = self.size()
        old_anchor = QPointF(self._anchor_offset)
        self.setFixedSize(widget_width, widget_height)
        self._source = QRectF(
            cell_rect.x() + bounds.x(),
            cell_rect.y() + bounds.y(),
            bounds.width(),
            bounds.height(),
        )
        self._target = QRectF(
            self.SAFE_PADDING,
            self.SAFE_PADDING,
            visual_width,
            visual_height,
        )
        self._full_target = QRectF(full_left, full_top, self.skin.preferred_width, self.skin.preferred_height)
        self._visual_logical_origin = QPointF(logical_left, logical_top)
        self._anchor_offset = QPointF(
            self.CANVAS_WIDTH / 2 - logical_left + self.SAFE_PADDING,
            self.CANVAS_HEIGHT - logical_top + self.SAFE_PADDING,
        )
        if self.size() != old_size or self._anchor_offset != old_anchor:
            self.visual_bounds_changed.emit()

    def paintEvent(self, _event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        asset = self.skin.asset_for(self.activity)
        pixmap = self._pixmaps.get(asset.path)
        if pixmap is None or pixmap.isNull():
            painter.setPen(self.skin.theme.low)
            painter.setFont(theme.font(10))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Skin unavailable")
            return
        painter.save()
        if self.state is PetState.EMPTY:
            painter.setOpacity(0.72)
        elif self.state is PetState.CRITICAL:
            painter.setOpacity(0.88)
        painter.drawPixmap(self._target, pixmap, self._source)
        painter.restore()

        if self.activity is PetActivity.BLINK:
            # The visible eye on the bundled Rita portraits sits near the
            # horizontal centre of the normalized character canvas.  Draw the
            # eyelid in logical coordinates so cropping never shifts it.
            eye_logical_x = self._full_target.left() + self._full_target.width() * 0.50
            eye_logical_y = self._full_target.top() + self._full_target.height() * 0.41
            eye_x = eye_logical_x - self._visual_logical_origin.x() + self.SAFE_PADDING
            eye_y = eye_logical_y - self._visual_logical_origin.y() + self.SAFE_PADDING
            painter.setPen(
                QPen(
                    QColor(self.skin.theme.critical),
                    2.2,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                )
            )
            painter.drawLine(int(eye_x - 5), int(eye_y), int(eye_x + 5), int(eye_y + 1))
