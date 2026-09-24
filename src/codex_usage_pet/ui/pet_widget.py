from __future__ import annotations

import logging
import math
import random
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QEvent, QPointF, QPropertyAnimation, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

from codex_usage_pet.pet.action_policy import (
    ActionDecision,
    ActionEvent,
    ActionSelector,
    enter_event,
    exit_event,
    persistent_event,
)
from codex_usage_pet.pet.animator import PetActivity, PetBehaviorController
from codex_usage_pet.pet.states import PetState
from codex_usage_pet.skins.models import SkinPack, SkinStateAsset

from . import theme


_SHARED_ANIMATION_BOUNDS: dict[
    tuple[Path, int, tuple[tuple[int, int], ...], tuple[int, int]], QRect
] = {}

logger = logging.getLogger(__name__)


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
    POST_ACTION_IDLE_MIN_MS = 15_000
    POST_ACTION_IDLE_MAX_MS = 30_000
    PRIORITY_IDLE = 1
    PRIORITY_HOVER = 2
    PRIORITY_CLICK = 3
    PRIORITY_SYSTEM = 4

    def __init__(
        self,
        skin: SkinPack,
        parent: QWidget | None = None,
        *,
        rng: random.Random | None = None,
        action_overrides: dict[str, list[str]] | None = None,
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
        self.action_selector = ActionSelector(
            skin.action_policy, rng=self._rng, overrides=action_overrides
        )
        self._pixmaps: dict[Path, QPixmap] = {}
        self._frame_cache: dict[tuple[Path, tuple[int, int], tuple[int, int]], QPixmap] = {}
        self._frame_bounds: dict[tuple[Path, tuple[int, int], tuple[int, int]], QRect] = {}
        self._frame_anchors: dict[
            tuple[Path, tuple[int, int], tuple[int, int]], QPointF
        ] = {}
        self._frame_targets: dict[
            tuple[Path, tuple[int, int], tuple[int, int]], QRectF
        ] = {}
        self._bounds: dict[tuple[Path, tuple[tuple[int, int], ...], tuple[int, int]], QRect] = {}
        self._current_frame_pixmap = QPixmap()
        self._source = QRectF()
        self._target = QRectF()
        self._full_target = QRectF()
        self._visual_logical_origin = QPointF()
        self._skin_union_bounds = QRectF()
        self._anchor_offset = QPointF()
        self._left_extent = self.CANVAS_WIDTH / 2
        self._right_extent = self.CANVAS_WIDTH / 2
        self._action_activity: PetActivity | str | None = None
        self._action_priority = 0
        self._pending_system_decisions: list[tuple[ActionDecision, PetState]] = []
        self._frame_index = 0
        self._quiet_mode = False

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

        self.apply_skin(skin, action_overrides)
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

    def apply_skin(
        self, skin: SkinPack, action_overrides: dict[str, list[str]] | None = None
    ) -> None:
        self._frame_timer.stop()
        self.skin = skin
        self.action_selector.set_policy(skin.action_policy)
        self.action_selector.set_overrides(action_overrides)
        self._pixmaps = {asset.path: QPixmap(str(asset.path)) for asset in skin.states.values()}
        self._frame_cache.clear()
        self._frame_bounds.clear()
        self._frame_anchors.clear()
        self._frame_targets.clear()
        self._bounds.clear()
        self._calculate_visual_envelope()
        # Bounds stay cached, but decoded frame crops are populated lazily and
        # released on the next skin change.
        self._frame_cache.clear()
        self._frame_index = 0
        base = self._choose_base_pose(self.state)
        self.activity = self.behavior.set_quota_state(self.state, base)
        self._prepare_visual()
        self._start_frame_timer()
        self._update_tooltip()
        self.update()

    def set_action_overrides(self, overrides: dict[str, list[str]] | None) -> None:
        self.action_selector.set_overrides(overrides)

    def set_quiet_mode(self, enabled: bool) -> None:
        self._quiet_mode = bool(enabled)

    def set_state(self, state: PetState) -> None:
        previous = self.state
        changed = state is not previous
        if not changed:
            return
        self.state = state
        self._action_timer.stop()
        self._frame_timer.stop()
        self._action_activity = None
        self._action_priority = 0
        self._pending_system_decisions.clear()
        base = self._choose_base_pose(state)
        self.activity = self.behavior.set_quota_state(state, base)
        self._frame_index = 0
        self._prepare_visual()
        self._start_frame_timer()
        self._update_tooltip()
        outgoing = exit_event(previous)
        incoming = enter_event(state)
        if outgoing is not None:
            self._pending_system_decisions.append(
                (self._choose(outgoing, previous, use_cooldown=False), previous)
            )
        if incoming is not None:
            self._pending_system_decisions.append(
                (self._choose(incoming, state, use_cooldown=False), state)
            )
        self._play_next_system_decision()
        self._transition.stop()
        self._transition.setStartValue(0.58)
        self._transition.setEndValue(1.0)
        self._transition.start()
        self.update()

    def play_hover_reaction(self, now: float | None = None) -> bool:
        if getattr(self, "_quiet_mode", False):
            return False
        decision = self._choose(ActionEvent.HOVER, self.state, now=now)
        return self._start_decision(decision, self.PRIORITY_HOVER, now)

    def play_click_reaction(self, now: float | None = None) -> bool:
        decision = self._choose(ActionEvent.CLICK, self.state, now=now)
        return self._start_decision(decision, self.PRIORITY_CLICK, now)

    def play_action(self, action_id: str) -> bool:
        """Play one supported action directly for diagnostics and visual QA."""
        resolved = self.skin.resolve_activity(action_id, required=False)
        if resolved is None or not self.skin.has_explicit_state(resolved):
            logger.debug("animation diagnostic rejected: action=%s", action_id)
            return False
        logger.debug("animation diagnostic play: action=%s", action_id)
        return self._start_action(resolved, priority=self.PRIORITY_SYSTEM)

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

    def _start_action(
        self,
        activity: PetActivity | str,
        duration_ms: int | None = None,
        *,
        priority: int = PRIORITY_IDLE,
    ) -> bool:
        if self._action_activity is not None:
            if priority <= self._action_priority:
                return False
            if not self.skin.asset_for(self._action_activity).interruptible:
                return False
            self._action_timer.stop()
            self._frame_timer.stop()
        self._action_activity = activity
        self._action_priority = priority
        self.activity = activity
        self._frame_timer.stop()
        self._frame_index = 0
        self._prepare_visual()
        asset = self.skin.asset_for(activity)
        self._start_frame_timer()
        logger.debug(
            "animation started: action=%s frames=%d timer_active=%s interval_ms=%d",
            activity.value if isinstance(activity, PetActivity) else activity,
            asset.frame_count,
            self._frame_timer.isActive(),
            self._frame_timer.interval(),
        )
        if asset.frame_count <= 1:
            self._action_timer.start(duration_ms or asset.duration_ms or 600)
        self._update_tooltip()
        self.update()
        return True

    def _finish_action(self) -> None:
        self._action_timer.stop()
        self._frame_timer.stop()
        finished = self._action_activity
        self._action_activity = None
        self._action_priority = 0
        self.activity = self.behavior.advance()
        self._frame_index = 0
        self._prepare_visual()
        self._start_frame_timer()
        self._update_tooltip()
        logger.debug(
            "animation finished: action=%s base=%s",
            finished.value if isinstance(finished, PetActivity) else finished,
            self.activity.value if isinstance(self.activity, PetActivity) else self.activity,
        )
        if self._pending_system_decisions:
            self._play_next_system_decision()
            return
        self._idle_timer.start(
            self._rng.randint(self.POST_ACTION_IDLE_MIN_MS, self.POST_ACTION_IDLE_MAX_MS)
        )
        self.update()

    def _schedule_idle_action(self) -> None:
        policy = self.action_selector.policy
        interval = self._rng.randint(
            policy.idle_interval_min_ms, policy.idle_interval_max_ms
        )
        self._idle_timer.start(interval)

    def _run_idle_action(self) -> None:
        try:
            if (
                not getattr(self, "_quiet_mode", False)
                and self.state is PetState.NORMAL
                and self._action_activity is None
            ):
                if self._rng.random() < self.action_selector.policy.idle_trigger_probability:
                    decision = self._choose(ActionEvent.IDLE_RANDOM, self.state)
                    self._start_decision(decision, self.PRIORITY_IDLE)
        finally:
            self._schedule_idle_action()

    def _choose(
        self,
        event: ActionEvent,
        state: PetState,
        *,
        now: float | None = None,
        use_cooldown: bool = True,
        avoid_repeat: bool = True,
    ) -> ActionDecision:
        return self.action_selector.choose(
            event,
            state=state,
            supported_actions=self.skin.supported_actions,
            now=now,
            use_cooldown=use_cooldown,
            avoid_repeat=avoid_repeat,
        )

    def _choose_base_pose(self, state: PetState) -> PetActivity | str:
        decision = self._choose(
            persistent_event(state),
            state,
            use_cooldown=False,
            avoid_repeat=False,
        )
        if decision.action is None:
            return PetActivity.IDLE
        return self._resolve_activity(decision.action)

    def _start_decision(
        self, decision: ActionDecision, priority: int, now: float | None = None
    ) -> bool:
        if decision.action is None:
            logger.debug(
                "animation decision: event=%s selected=none reason=%s",
                decision.event,
                decision.reason,
            )
            return False
        activity = self._resolve_activity(decision.action)
        logger.debug("animation decision: event=%s selected=%s", decision.event, decision.action)
        if not self._start_action(activity, priority=priority):
            return False
        asset = self.skin.asset_for(activity)
        self.action_selector.commit(
            decision,
            now=now,
            fallback_cooldown_ms=asset.cooldown_ms,
        )
        return True

    def _play_next_system_decision(self) -> None:
        while self._pending_system_decisions:
            decision, _selection_state = self._pending_system_decisions.pop(0)
            if self._start_decision(decision, self.PRIORITY_SYSTEM):
                return

    def _resolve_activity(self, action: str) -> PetActivity | str:
        resolved = self.skin.resolve_activity(action)
        assert resolved is not None
        return resolved

    def _update_tooltip(self) -> None:
        activity = self.activity.value if isinstance(self.activity, PetActivity) else self.activity
        from .localization import action_name, state_name

        self.setToolTip(f"{self.skin.name} · {state_name(self.state.value)} · {action_name(activity)}")

    def _prepare_visual(self) -> None:
        asset = self.skin.asset_for(self.activity)
        pixmap = self._frame_pixmap(asset, asset.cell_at(self._frame_index))
        self._current_frame_pixmap = pixmap
        if pixmap is None or pixmap.isNull():
            self._source = QRectF()
            self._target = QRectF()
            return
        frame_key = (asset.path, asset.cell_at(self._frame_index), asset.grid)
        logical_target = self._frame_targets[frame_key]
        self._source = QRectF(0, 0, pixmap.width(), pixmap.height())
        self._target = logical_target.translated(
            -self._skin_union_bounds.left() + self.SAFE_PADDING,
            -self._skin_union_bounds.top() + self.SAFE_PADDING,
        )
        self._full_target = QRectF(self._target)

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
        union = QRectF()
        seen: set[tuple[Path, tuple[int, int], tuple[int, int], float, float]] = set()
        for asset in self.skin.states.values():
            frames = asset.frames or (asset.cell or (0, 0),)
            bounds_key = (asset.path, frames, asset.grid)
            animation_union = QRect()
            for cell in frames:
                key = (asset.path, cell, asset.grid, asset.offset_x, asset.offset_y)
                if key in seen:
                    continue
                seen.add(key)
                frame = self._frame_pixmap(asset, cell)
                if frame.isNull():
                    continue
                frame_key = (asset.path, cell, asset.grid)
                bounds = alpha_bounding_rect(frame.toImage(), 15)
                anchor = self._bottom_center_anchor(frame.toImage(), bounds)
                self._frame_bounds[frame_key] = bounds
                self._frame_anchors[frame_key] = anchor
                scale_x = self.skin.preferred_width / frame.width()
                scale_y = self.skin.preferred_height / frame.height()
                origin = QPointF(
                    self.CANVAS_WIDTH / 2
                    + self.skin.anchor_x
                    + asset.offset_x
                    - anchor.x() * scale_x,
                    self.CANVAS_HEIGHT
                    + self.skin.anchor_y
                    + asset.offset_y
                    - anchor.y() * scale_y,
                )
                target = QRectF(
                    origin.x(), origin.y(), self.skin.preferred_width, self.skin.preferred_height
                )
                self._frame_targets[frame_key] = target
                logical_bounds = QRectF(
                    origin.x() + bounds.x() * scale_x,
                    origin.y() + bounds.y() * scale_y,
                    bounds.width() * scale_x,
                    bounds.height() * scale_y,
                )
                union = logical_bounds if union.isNull() else union.united(logical_bounds)
                animation_union = (
                    bounds if animation_union.isNull() else animation_union.united(bounds)
                )
            self._bounds[bounds_key] = animation_union
        if union.isNull():
            union = QRectF(0, 0, 96, 96)
        self._skin_union_bounds = union
        self._visual_logical_origin = union.topLeft()
        old_size = self.size()
        old_anchor = QPointF(self._anchor_offset)
        self.setFixedSize(
            math.ceil(union.width()) + self.SAFE_PADDING * 2,
            math.ceil(union.height()) + self.SAFE_PADDING * 2,
        )
        self._anchor_offset = QPointF(
            self.CANVAS_WIDTH / 2 - union.left() + self.SAFE_PADDING,
            self.CANVAS_HEIGHT - union.top() + self.SAFE_PADDING,
        )
        self._left_extent = max(1.0, self.CANVAS_WIDTH / 2 - union.left())
        self._right_extent = max(1.0, union.right() - self.CANVAS_WIDTH / 2)
        if self.size() != old_size or self._anchor_offset != old_anchor:
            self.visual_bounds_changed.emit()

    @staticmethod
    def _bottom_center_anchor(image: QImage, bounds: QRect) -> QPointF:
        """Return a stable ground-contact anchor for one transparent frame."""
        if image.isNull() or bounds.isNull():
            return QPointF(image.width() / 2, image.height())
        rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
        data = rgba.constBits()
        stride = rgba.bytesPerLine()
        band_height = max(6, round(bounds.height() * 0.05))
        first_y = max(bounds.top(), bounds.bottom() - band_height + 1)
        xs: list[int] = []
        for y in range(first_y, bounds.bottom() + 1):
            row = y * stride
            for x in range(bounds.left(), bounds.right() + 1):
                if data[row + x * 4 + 3] > 15:
                    xs.append(x)
        xs.sort()
        center_x = float(xs[len(xs) // 2]) if xs else bounds.center().x()
        return QPointF(center_x, bounds.bottom() + 1)

    @property
    def skin_union_bounds(self) -> QRectF:
        return QRectF(self._skin_union_bounds)

    @property
    def current_foot_anchor(self) -> QPointF:
        """Current normalized foot anchor in widget coordinates (QA hook)."""
        return QPointF(self._anchor_offset.x(), self._anchor_offset.y() + self.skin.anchor_y)

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
        logger.debug(
            "animation frame: action=%s frame=%d/%d interval_ms=%d",
            self.activity.value if isinstance(self.activity, PetActivity) else self.activity,
            self._frame_index,
            asset.frame_count,
            interval,
        )
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
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "皮肤素材不可用")
            return
        painter.save()
        if self.state is PetState.EMPTY:
            painter.setOpacity(0.72)
        elif self.state is PetState.CRITICAL:
            painter.setOpacity(0.88)
        painter.drawPixmap(self._target, pixmap, self._source)
        painter.restore()
