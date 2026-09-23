from __future__ import annotations

import math
import random
import time
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QEvent, QPointF, QPropertyAnimation, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

from codex_usage_pet.pet.animator import PetActivity, PetBehaviorController
from codex_usage_pet.pet.states import PetState
from codex_usage_pet.skins.models import SkinPack, SkinStateAsset

from . import theme


_SHARED_ANIMATION_BOUNDS: dict[
    tuple[Path, int, tuple[tuple[int, int], ...], tuple[int, int]], QRect
] = {}


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
    IDLE_INTERVAL_MIN_MS = 45_000
    IDLE_INTERVAL_MAX_MS = 150_000
    POST_ACTION_IDLE_MIN_MS = 15_000
    POST_ACTION_IDLE_MAX_MS = 30_000

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
        self._frame_cache: dict[tuple[Path, tuple[int, int], tuple[int, int]], QPixmap] = {}
        self._bounds: dict[tuple[Path, tuple[tuple[int, int], ...], tuple[int, int]], QRect] = {}
        self._current_frame_pixmap = QPixmap()
        self._source = QRectF()
        self._target = QRectF()
        self._full_target = QRectF()
        self._visual_logical_origin = QPointF()
        self._anchor_offset = QPointF()
        self._left_extent = self.CANVAS_WIDTH / 2
        self._right_extent = self.CANVAS_WIDTH / 2
        self._action_activity: PetActivity | None = None
        self._frame_index = 0
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
        self._frame_timer = QTimer(self)
        self._frame_timer.timeout.connect(self._advance_frame)
        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self._run_idle_action)

        self.apply_skin(skin)
        self._schedule_idle_action()

    @property
    def sprite_loaded(self) -> bool:
        return not self._current_frame_pixmap.isNull()

    @property
    def anchor_offset(self) -> QPointF:
        """Bottom-center canvas anchor expressed in current widget coordinates."""
        return QPointF(self._anchor_offset)

    @property
    def idle_timer_interval(self) -> int:
        return self._idle_timer.interval()

    @property
    def frame_cache_size(self) -> int:
        return len(self._frame_cache)

    @property
    def current_animation_duration_ms(self) -> int:
        return self.skin.asset_for(self.activity).duration_ms

    @property
    def visual_extents(self) -> tuple[int, int]:
        """Maximum visible pixels left/right of the shared screen anchor."""
        return math.ceil(self._left_extent), math.ceil(self._right_extent)

    def apply_skin(self, skin: SkinPack) -> None:
        self._frame_timer.stop()
        self.skin = skin
        self._pixmaps = {asset.path: QPixmap(str(asset.path)) for asset in skin.states.values()}
        self._frame_cache.clear()
        self._bounds.clear()
        self._calculate_visual_envelope()
        # Bounds stay cached, but decoded frame crops are populated lazily and
        # released on the next skin change.
        self._frame_cache.clear()
        self._frame_index = 0
        self._prepare_visual()
        self._start_frame_timer()
        self.setToolTip(f"{skin.name} · {self.state.value} · {self.activity.value}")
        self.update()

    def set_state(self, state: PetState) -> None:
        changed = state is not self.state
        self.state = state
        self._action_timer.stop()
        self._frame_timer.stop()
        self._action_activity = None
        self.activity = self.behavior.set_quota_state(state)
        if (
            changed
            and state is PetState.LOW
            and self.skin.has_explicit_state(PetActivity.SIT_TRANSITION)
        ):
            self._action_activity = PetActivity.SIT_TRANSITION
            self.activity = PetActivity.SIT_TRANSITION
        self._frame_index = 0
        self._prepare_visual()
        self._start_frame_timer()
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
        asset = self.skin.asset_for(PetActivity.HOVER)
        cooldown = asset.cooldown_ms / 1000 or self.HOVER_COOLDOWN_SECONDS
        if moment - self._last_hover_at < cooldown:
            return False
        if not self.skin.has_explicit_state(PetActivity.HOVER):
            return False
        self._last_hover_at = moment
        return self._start_action(PetActivity.HOVER)

    def play_click_reaction(self, now: float | None = None) -> bool:
        moment = time.monotonic() if now is None else now
        if self.state in {PetState.CRITICAL, PetState.RECOVERED}:
            return False
        activity = PetActivity.SLEEP_REACT if self.state is PetState.EMPTY else PetActivity.CLICK
        asset = self.skin.asset_for(activity)
        cooldown = asset.cooldown_ms / 1000 or self.CLICK_COOLDOWN_SECONDS
        if moment - self._last_click_at < cooldown:
            return False
        if not self.skin.has_explicit_state(activity):
            return False
        # Click outranks hover and autonomous idle actions.  This matters in
        # real use because a pointer entry usually happens just before a click.
        if self._action_activity is activity or (
            self._action_activity is not None
            and not self.skin.asset_for(self._action_activity).interruptible
        ):
            return False
        if self._action_activity is not None:
            self._action_timer.stop()
            self._action_activity = None
        self._last_click_at = moment
        return self._start_action(activity)

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

    def _start_action(self, activity: PetActivity, duration_ms: int | None = None) -> bool:
        if self._action_activity is not None:
            return False
        self._action_activity = activity
        self.activity = activity
        self._frame_timer.stop()
        self._frame_index = 0
        self._prepare_visual()
        asset = self.skin.asset_for(activity)
        self._start_frame_timer()
        if asset.frame_count <= 1:
            self._action_timer.start(duration_ms or asset.duration_ms or 600)
        self.setToolTip(f"{self.skin.name} · {self.state.value} · {activity.value}")
        self.update()
        return True

    def _finish_action(self) -> None:
        self._action_timer.stop()
        self._frame_timer.stop()
        self._action_activity = None
        self.activity = self.behavior.set_quota_state(self.state)
        self._frame_index = 0
        self._prepare_visual()
        self._start_frame_timer()
        self.setToolTip(f"{self.skin.name} · {self.state.value} · {self.activity.value}")
        self._idle_timer.start(
            self._rng.randint(self.POST_ACTION_IDLE_MIN_MS, self.POST_ACTION_IDLE_MAX_MS)
        )
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
                weighted = [
                    (PetActivity.BLINK, 50),
                    (PetActivity.WAVE, 20),
                    (PetActivity.STRETCH, 20),
                    (PetActivity.LOOK_LEFT, 5),
                    (PetActivity.LOOK_RIGHT, 5),
                ]
                candidates = [item for item in weighted if self.skin.has_explicit_state(item[0])]
                if candidates:
                    activity = self._rng.choices(
                        [item[0] for item in candidates],
                        weights=[item[1] for item in candidates],
                        k=1,
                    )[0]
                    self._start_action(activity)
        finally:
            self._schedule_idle_action()

    def _prepare_visual(self) -> None:
        asset = self.skin.asset_for(self.activity)
        pixmap = self._frame_pixmap(asset, asset.cell_at(self._frame_index))
        self._current_frame_pixmap = pixmap
        if pixmap is None or pixmap.isNull():
            old_size = self.size()
            self.setFixedSize(96, 96)
            self._source = QRectF()
            self._target = QRectF(self.SAFE_PADDING, self.SAFE_PADDING, 88, 88)
            self._anchor_offset = QPointF(48, 92)
            if self.size() != old_size:
                self.visual_bounds_changed.emit()
            return

        cell_width = pixmap.width()
        cell_height = pixmap.height()
        frames = asset.frames or (asset.cell or (0, 0),)
        key = (asset.path, frames, asset.grid)
        bounds = self._bounds.get(key)
        if bounds is None:
            bounds = self._animation_bounds(asset)
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
            bounds.x(),
            bounds.y(),
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

    def _frame_pixmap(self, asset: SkinStateAsset, cell: tuple[int, int]) -> QPixmap:
        key = (asset.path, cell, asset.grid)
        cached = self._frame_cache.get(key)
        if cached is not None:
            return cached
        sheet = self._pixmaps.get(asset.path, QPixmap())
        if sheet.isNull():
            return QPixmap()
        columns, rows = asset.grid
        left = round(cell[0] * sheet.width() / columns)
        right = round((cell[0] + 1) * sheet.width() / columns)
        top = round(cell[1] * sheet.height() / rows)
        bottom = round((cell[1] + 1) * sheet.height() / rows)
        frame = sheet.copy(QRect(left, top, right - left, bottom - top))
        self._frame_cache[key] = frame
        return frame

    def _animation_bounds(self, asset: SkinStateAsset) -> QRect:
        frames = asset.frames or (asset.cell or (0, 0),)
        try:
            modified_ns = asset.path.stat().st_mtime_ns
        except OSError:
            modified_ns = 0
        shared_key = (asset.path, modified_ns, frames, asset.grid)
        shared = _SHARED_ANIMATION_BOUNDS.get(shared_key)
        if shared is not None:
            return QRect(shared)
        union = QRect()
        for cell in frames:
            frame = self._frame_pixmap(asset, cell)
            bounds = alpha_bounding_rect(frame.toImage(), 15)
            union = bounds if union.isNull() else union.united(bounds)
        if len(_SHARED_ANIMATION_BOUNDS) >= 128:
            _SHARED_ANIMATION_BOUNDS.pop(next(iter(_SHARED_ANIMATION_BOUNDS)))
        _SHARED_ANIMATION_BOUNDS[shared_key] = QRect(union)
        return union

    def _calculate_visual_envelope(self) -> None:
        left_extent = right_extent = 0.0
        seen: set[tuple[Path, tuple[tuple[int, int], ...], tuple[int, int], float, float]] = set()
        for asset in self.skin.states.values():
            frames = asset.frames or (asset.cell or (0, 0),)
            key = (asset.path, frames, asset.grid, asset.offset_x, asset.offset_y)
            if key in seen:
                continue
            seen.add(key)
            bounds_key = (asset.path, frames, asset.grid)
            bounds = self._bounds.get(bounds_key)
            if bounds is None:
                bounds = self._animation_bounds(asset)
                self._bounds[bounds_key] = bounds
            sample = self._frame_pixmap(asset, frames[0])
            if sample.isNull():
                continue
            scale_x = self.skin.preferred_width / sample.width()
            full_left = (
                (self.CANVAS_WIDTH - self.skin.preferred_width) / 2
                + self.skin.anchor_x
                + asset.offset_x
            )
            logical_left = full_left + bounds.left() * scale_x
            logical_right = full_left + (bounds.right() + 1) * scale_x
            left_extent = max(left_extent, self.CANVAS_WIDTH / 2 - logical_left)
            right_extent = max(right_extent, logical_right - self.CANVAS_WIDTH / 2)
        self._left_extent = max(1.0, left_extent)
        self._right_extent = max(1.0, right_extent)

    def _start_frame_timer(self) -> None:
        asset = self.skin.asset_for(self.activity)
        interval = asset.frame_duration_ms(self._frame_index)
        if asset.frame_count > 1 and interval > 0:
            self._frame_timer.start(interval)

    def _advance_frame(self) -> None:
        asset = self.skin.asset_for(self.activity)
        next_index = self._frame_index + 1
        if next_index >= asset.frame_count:
            if asset.loop:
                next_index = 0
            elif self._action_activity is not None:
                self._finish_action()
                return
            else:
                self._frame_timer.stop()
                next_index = asset.frame_count - 1
        self._frame_index = next_index
        self._prepare_visual()
        interval = asset.frame_duration_ms(self._frame_index)
        if interval > 0:
            self._frame_timer.start(interval)
        self.update()

    def paintEvent(self, _event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        asset = self.skin.asset_for(self.activity)
        pixmap = self._current_frame_pixmap
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
