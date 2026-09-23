from __future__ import annotations

import os

from PySide6.QtCore import QEasingCurve, QEvent, QPoint, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup, QCursor, QGuiApplication
from PySide6.QtWidgets import QApplication, QInputDialog, QMenu, QMessageBox, QWidget

from codex_usage_pet.codex.models import UsageSnapshot
from codex_usage_pet.pet.states import PetState, PetStateTracker, state_for_remaining
from codex_usage_pet.services.paths import log_dir
from codex_usage_pet.services.settings import AppSettings, SettingsStore
from codex_usage_pet.services.startup import StartupManager
from codex_usage_pet.skins.loader import user_skin_dir
from codex_usage_pet.skins.manager import SkinManager
from codex_usage_pet.skins.models import SkinPack

from .pet_widget import PetWidget
from .theme import menu_style
from .usage_bubble import UsageBubble


class PetWindow(QWidget):
    refresh_requested = Signal()
    interval_changed = Signal(int)
    quit_requested = Signal()
    skin_changed = Signal(object)
    menu_changed = Signal()

    BUBBLE_GAP = 8

    def __init__(
        self,
        settings: AppSettings,
        store: SettingsStore,
        startup: StartupManager,
        skin_manager: SkinManager | None = None,
    ) -> None:
        super().__init__()
        self.settings = settings
        self.store = store
        self.startup = startup
        self.skin_manager = skin_manager or SkinManager(settings, store)
        self.current_skin = self.skin_manager.current
        self._anchor: QPoint | None = None
        self._drag_offset: QPoint | None = None
        self._press_global: QPoint | None = None
        self._snapshot: UsageSnapshot | None = None
        self._state_tracker = PetStateTracker()

        self.pet = PetWidget(self.current_skin, self)
        self.pet.move(0, 0)
        self.resize(self.pet.size())
        self.bubble = UsageBubble()
        self.bubble.set_skin(self.current_skin)
        self.bubble.adjustSize()
        self.pet.visual_bounds_changed.connect(self._on_pet_bounds_changed)
        self.pet.clicked.connect(self.toggle_usage_panel)

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(350)
        self._save_timer.timeout.connect(self.save_settings)
        self._pending_skin: SkinPack | None = None
        self._skin_fade_out = QPropertyAnimation(self.pet._opacity_effect, b"opacity", self)
        self._skin_fade_out.setDuration(190)
        self._skin_fade_out.setEasingCurve(QEasingCurve.Type.InCubic)
        self._skin_fade_out.finished.connect(self._finish_skin_swap)
        self._skin_fade_in = QPropertyAnimation(self.pet._opacity_effect, b"opacity", self)
        self._skin_fade_in.setDuration(230)
        self._skin_fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._auto_skin_timer = QTimer(self)
        self._auto_skin_timer.setInterval(60_000)
        self._auto_skin_timer.timeout.connect(self.check_auto_skin)
        self._auto_skin_timer.start()

        self._apply_window_flags()
        for window in (self, self.bubble):
            window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            window.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
            window.setWindowOpacity(settings.opacity)
        self.setWindowTitle("Codex Usage Pet")
        self.bubble.setWindowTitle("Codex Usage Pet · Usage")
        for target in (self, self.pet, self.bubble, self.bubble.panel):
            target.installEventFilter(self)
        QTimer.singleShot(0, self._restore_position)
        QTimer.singleShot(0, self.check_auto_skin)

    @property
    def pet_anchor(self) -> QPoint:
        if self._anchor is not None:
            return QPoint(self._anchor)
        offset = self.pet.anchor_offset
        return self.pos() + QPoint(round(offset.x()), round(offset.y()))

    @property
    def bubble_side(self) -> str:
        return getattr(self, "_bubble_side", "left")

    def set_snapshot(self, snapshot: UsageSnapshot) -> None:
        self._snapshot = snapshot
        self.bubble.set_snapshot(snapshot)
        state = self._state_tracker.update(snapshot.remaining_percent)
        self.pet.set_state(state)
        self.bubble.set_state(state)
        message = {
            PetState.NORMAL: "",
            PetState.LOW: "额度不多啦。",
            PetState.CRITICAL: "额度快见底了…",
            PetState.EMPTY: "今天先休息一下吧… Zzz",
            PetState.RECOVERED: "额度恢复啦 ♡",
        }[state]
        self.bubble.set_pet_message(message)
        if state is PetState.RECOVERED:
            QTimer.singleShot(max(850, self.pet.current_animation_duration_ms + 100), self._finish_recovered)

    def set_error(self, text: str) -> None:
        self.bubble.set_error(text)

    def build_menu(self) -> QMenu:
        menu = QMenu()
        menu.setStyleSheet(menu_style(self.current_skin.theme))
        refresh = menu.addAction("刷新额度")
        refresh.triggered.connect(self.refresh_requested.emit)
        show_usage = menu.addAction("显示额度")
        show_usage.setCheckable(True)
        show_usage.setChecked(self.settings.show_usage)
        show_usage.triggered.connect(self.set_usage_visible)
        top = menu.addAction("始终置顶")
        top.setCheckable(True)
        top.setChecked(self.settings.always_on_top)
        top.triggered.connect(self.set_always_on_top)
        locked = menu.addAction("锁定位置")
        locked.setCheckable(True)
        locked.setChecked(self.settings.locked)
        locked.triggered.connect(self.set_locked)

        skin_menu = menu.addMenu("皮肤")
        current = skin_menu.addAction(f"当前：{self.current_skin.name}")
        current.setEnabled(False)
        skin_menu.addSeparator()
        skin_group = QActionGroup(skin_menu)
        for pack in sorted(self.skin_manager.packs.values(), key=lambda item: item.name.casefold()):
            action = skin_menu.addAction(pack.name)
            action.setCheckable(True)
            action.setChecked(pack.id == self.current_skin.id)
            action.triggered.connect(
                lambda _checked=False, skin_id=pack.id: self.change_skin(skin_id, reason="manual")
            )
            skin_group.addAction(action)
        skin_menu.addSeparator()
        random_action = skin_menu.addAction("随机换一个")
        random_action.triggered.connect(self.random_skin)
        auto_menu = skin_menu.addMenu("自动换肤")
        auto_group = QActionGroup(auto_menu)
        auto_group.setExclusive(True)
        off = auto_menu.addAction("关闭")
        off.setCheckable(True)
        off.setChecked(not self.settings.auto_skin_enabled)
        off.triggered.connect(lambda: self.set_auto_skin_interval(None))
        auto_group.addAction(off)
        for hours in (6, 12, 24, 48):
            action = auto_menu.addAction(f"每 {hours} 小时")
            action.setCheckable(True)
            action.setChecked(
                self.settings.auto_skin_enabled
                and self.settings.auto_skin_mode == "interval"
                and self.settings.auto_skin_interval_hours == hours
            )
            action.triggered.connect(
                lambda _checked=False, value=hours: self.set_auto_skin_interval(value)
            )
            auto_group.addAction(action)
        fixed_menu = auto_menu.addMenu("每天固定时间")
        fixed_group = QActionGroup(fixed_menu)
        for value in ("00:00", "08:00", "12:00", "18:00"):
            action = fixed_menu.addAction(value)
            action.setCheckable(True)
            action.setChecked(
                self.settings.auto_skin_enabled
                and self.settings.auto_skin_mode == "fixed_time"
                and self.settings.auto_skin_fixed_time == value
            )
            action.triggered.connect(
                lambda _checked=False, fixed=value: self.set_auto_skin_fixed_time(fixed)
            )
            fixed_group.addAction(action)
        custom = fixed_menu.addAction("自定义时间…")
        custom.triggered.connect(self.choose_auto_skin_fixed_time)
        skin_menu.addSeparator()
        rescan = skin_menu.addAction("重新扫描皮肤")
        rescan.triggered.connect(self.rescan_skins)
        open_skins = skin_menu.addAction("打开皮肤目录")
        open_skins.triggered.connect(self.open_skin_directory)

        opacity_menu = menu.addMenu("透明度")
        opacity_group = QActionGroup(opacity_menu)
        for percent in (60, 80, 100):
            action = opacity_menu.addAction(f"{percent}%")
            action.setCheckable(True)
            action.setChecked(round(self.settings.opacity * 100) == percent)
            action.triggered.connect(lambda _checked=False, value=percent: self.set_opacity(value / 100))
            opacity_group.addAction(action)
        interval_menu = menu.addMenu("刷新间隔")
        interval_group = QActionGroup(interval_menu)
        for seconds, label in ((60, "1 分钟"), (120, "2 分钟"), (300, "5 分钟")):
            action = interval_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(self.settings.refresh_interval == seconds)
            action.triggered.connect(lambda _checked=False, value=seconds: self.set_refresh_interval(value))
            interval_group.addAction(action)
        startup = menu.addAction("开机启动")
        startup.setCheckable(True)
        startup.setEnabled(self.startup.supported)
        startup.setChecked(self.startup.is_enabled())
        startup.triggered.connect(self.set_startup_enabled)
        menu.addSeparator()
        logs = menu.addAction("打开日志目录")
        logs.triggered.connect(self.open_logs)
        about = menu.addAction("关于")
        about.triggered.connect(self.show_about)
        menu.addSeparator()
        quit_action = menu.addAction("退出")
        quit_action.triggered.connect(self.quit_requested.emit)
        return menu

    def toggle_visible(self) -> None:
        if self.isVisible():
            self.hide()
            self.bubble.hide()
        else:
            self.show()
            self.raise_()
            if self.settings.show_usage:
                self._position_bubble()
                self.bubble.show()

    def save_settings(self) -> None:
        anchor = self.pet_anchor
        self.settings.pet_anchor_x = anchor.x()
        self.settings.pet_anchor_y = anchor.y()
        self.settings.window_x = self.x()
        self.settings.window_y = self.y()
        self.store.save(self.settings)

    def set_usage_visible(self, visible: bool) -> None:
        anchor_before = self.pet_anchor
        position_before = self.pos()
        self.settings.show_usage = visible
        if visible:
            self._position_bubble()
        self.bubble.set_animated_visible(visible)
        self._anchor = anchor_before
        if self.pos() != position_before:
            self.move(position_before)
        self.save_settings()

    def toggle_usage_panel(self) -> None:
        self.set_usage_visible(not self.settings.show_usage)

    def set_always_on_top(self, enabled: bool) -> None:
        self.settings.always_on_top = enabled
        pet_visible = self.isVisible()
        bubble_visible = self.bubble.isVisible()
        self._apply_window_flags()
        if pet_visible:
            self.show()
        if bubble_visible:
            self.bubble.show()
        self._move_to_anchor(self.pet_anchor)
        self.save_settings()

    def set_locked(self, enabled: bool) -> None:
        self.settings.locked = enabled
        self.save_settings()

    def set_opacity(self, opacity: float) -> None:
        self.settings.opacity = opacity
        self.setWindowOpacity(opacity)
        self.bubble.setWindowOpacity(opacity)
        self.save_settings()

    def set_refresh_interval(self, seconds: int) -> None:
        self.settings.refresh_interval = seconds
        self.interval_changed.emit(seconds)
        self.save_settings()

    def set_startup_enabled(self, enabled: bool) -> None:
        try:
            self.startup.set_enabled(enabled)
            self.settings.startup_enabled = enabled
            self.save_settings()
        except Exception as exc:
            QMessageBox.warning(self, "Codex Usage Pet", f"无法修改开机启动：{exc}")

    def change_skin(self, skin_id: str, *, reason: str = "manual") -> None:
        pack = self.skin_manager.change(skin_id, reason=reason)
        if pack is None or pack.id == self.current_skin.id:
            return
        self._queue_skin_swap(pack)

    def random_skin(self) -> None:
        previous = self.current_skin.id
        pack = self.skin_manager.random_change(reason="random")
        if pack.id != previous:
            self._queue_skin_swap(pack)

    def check_auto_skin(self) -> None:
        previous = self.current_skin.id
        pack = self.skin_manager.maybe_auto_change()
        if pack is not None and pack.id != previous:
            self._queue_skin_swap(pack)

    def set_auto_skin_interval(self, hours: int | None) -> None:
        self.skin_manager.set_auto_interval(hours)
        self.menu_changed.emit()

    def set_auto_skin_fixed_time(self, value: str) -> None:
        self.skin_manager.set_auto_fixed_time(value)
        self.menu_changed.emit()

    def choose_auto_skin_fixed_time(self) -> None:
        value, accepted = QInputDialog.getText(
            self,
            "每天固定时间换肤",
            "本地时间（HH:MM）：",
            text=self.settings.auto_skin_fixed_time,
        )
        if not accepted:
            return
        try:
            self.set_auto_skin_fixed_time(value.strip())
        except ValueError:
            QMessageBox.warning(self, "Codex Usage Pet", "时间格式应为 HH:MM，例如 08:30。")

    def rescan_skins(self) -> None:
        self._queue_skin_swap(self.skin_manager.rescan())
        self.menu_changed.emit()

    def open_skin_directory(self) -> None:
        path = user_skin_dir()
        path.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]

    def _finish_skin_swap(self) -> None:
        pack = self._pending_skin
        if pack is None:
            return
        self._pending_skin = None
        anchor = self.pet_anchor
        self.current_skin = pack
        self.pet.apply_skin(pack)
        self.bubble.set_skin(pack)
        self._move_to_anchor(anchor)
        self.pet._opacity_effect.setOpacity(0.0)
        self._skin_fade_in.setStartValue(0.0)
        self._skin_fade_in.setEndValue(1.0)
        self._skin_fade_in.start()
        self.skin_changed.emit(pack)
        self.menu_changed.emit()

    def _queue_skin_swap(self, pack: SkinPack) -> None:
        self._pending_skin = pack
        self.pet._transition.stop()
        self._skin_fade_in.stop()
        self._skin_fade_out.stop()
        self._skin_fade_out.setStartValue(self.pet._opacity_effect.opacity())
        self._skin_fade_out.setEndValue(0.0)
        self._skin_fade_out.start()

    def open_logs(self) -> None:
        path = log_dir()
        path.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            "关于 Codex Usage Pet",
            "Codex Usage Pet 0.1.0\n\n独立人物窗口与 Skin Pack 交互动画。\n"
            "额度来自本机官方 Codex App Server。\n不读取浏览器 Cookie，不保存认证凭据。",
        )

    def eventFilter(self, watched, event) -> bool:  # type: ignore[no-untyped-def]
        if event.type() == QEvent.Type.ContextMenu:
            self.build_menu().exec(QCursor.pos())
            return True
        if watched not in (self, self.pet):
            return super().eventFilter(watched, event)
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self._press_global = event.globalPosition().toPoint()
            if self.settings.locked:
                return watched is self.pet or super().eventFilter(watched, event)
            self._drag_offset = event.globalPosition().toPoint() - self.pos()
            return True
        if event.type() == QEvent.Type.MouseMove and self._drag_offset and event.buttons() & Qt.MouseButton.LeftButton:
            desired = event.globalPosition().toPoint() - self._drag_offset
            self._move_to_anchor(self._anchor_for_top_left(desired))
            return True
        if event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            release_position = event.globalPosition().toPoint()
            clicked = (
                watched is self.pet
                and self._press_global is not None
                and (release_position - self._press_global).manhattanLength() <= 5
            )
            self._drag_offset = None
            self._press_global = None
            if clicked:
                self.pet.play_click_reaction()
                self.pet.clicked.emit()
            if not self.settings.locked:
                self._save_timer.start()
            return True
        return super().eventFilter(watched, event)

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        event.ignore()
        self.hide()
        self.bubble.hide()

    def _apply_window_flags(self) -> None:
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        if self.settings.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.bubble.setWindowFlags(flags)

    def _restore_position(self) -> None:
        self.resize(self.pet.size())
        if self.settings.pet_anchor_x is not None and self.settings.pet_anchor_y is not None:
            anchor = QPoint(self.settings.pet_anchor_x, self.settings.pet_anchor_y)
        elif self.settings.window_x is not None and self.settings.window_y is not None:
            legacy_pet_left = self.settings.window_x + (226 if self.settings.show_usage else 8)
            anchor = QPoint(legacy_pet_left + 116, self.settings.window_y + 252)
        else:
            screen = QGuiApplication.primaryScreen()
            if not screen:
                anchor = QPoint(0, 0)
            else:
                area = screen.availableGeometry()
                anchor = QPoint(area.right() - 30, area.bottom() - 30)
        self._move_to_anchor(anchor)
        if self.settings.show_usage:
            self._position_bubble()
            self.bubble.show()
        else:
            self.bubble.hide()
        self.save_settings()

    def _on_pet_bounds_changed(self) -> None:
        anchor = self.pet_anchor if self._anchor is not None else None
        self.resize(self.pet.size())
        self.pet.move(0, 0)
        if anchor is not None:
            self._move_to_anchor(anchor, clamp=False)

    def _anchor_for_top_left(self, top_left: QPoint) -> QPoint:
        offset = self.pet.anchor_offset
        return top_left + QPoint(round(offset.x()), round(offset.y()))

    def _top_left_for_anchor(self, anchor: QPoint) -> QPoint:
        offset = self.pet.anchor_offset
        return anchor - QPoint(round(offset.x()), round(offset.y()))

    def _move_to_anchor(self, anchor: QPoint, *, clamp: bool = True) -> None:
        bounded = self._bounded_anchor(anchor) if clamp else QPoint(anchor)
        self._anchor = QPoint(bounded)
        self.move(self._top_left_for_anchor(bounded))
        self._position_bubble()

    def _bounded_anchor(self, anchor: QPoint) -> QPoint:
        top_left = self._top_left_for_anchor(anchor)
        screen = QGuiApplication.screenAt(anchor) or QGuiApplication.primaryScreen()
        if not screen:
            return anchor
        area = screen.availableGeometry()
        bounded_top_left = QPoint(
            max(area.left(), min(top_left.x(), area.right() - self.width() + 1)),
            max(area.top(), min(top_left.y(), area.bottom() - self.height() + 1)),
        )
        return self._anchor_for_top_left(bounded_top_left)

    def _bounded_position(self, point: QPoint) -> QPoint:
        return self._top_left_for_anchor(self._bounded_anchor(self._anchor_for_top_left(point)))

    def _clamp_to_screen(self) -> None:
        self._move_to_anchor(self.pet_anchor)

    def _position_bubble(self) -> None:
        if self._anchor is None:
            return
        self.bubble.adjustSize()
        screen = QGuiApplication.screenAt(self._anchor) or QGuiApplication.primaryScreen()
        if not screen:
            return
        area = screen.availableGeometry()
        left_extent, right_extent = self.pet.visual_extents
        left_edge = self._anchor.x() - left_extent
        right_edge = self._anchor.x() + right_extent
        left_space = left_edge - area.left() - self.BUBBLE_GAP
        right_space = area.right() - right_edge - self.BUBBLE_GAP
        if right_space >= self.bubble.width() and (left_space < self.bubble.width() or right_space > left_space):
            x = right_edge + self.BUBBLE_GAP
            self._bubble_side = "right"
        else:
            x = left_edge - self.BUBBLE_GAP - self.bubble.width()
            self._bubble_side = "left"
        x = max(area.left(), min(x, area.right() - self.bubble.width() + 1))
        y = self._anchor.y() - self.bubble.height()
        y = max(area.top(), min(y, area.bottom() - self.bubble.height() + 1))
        self.bubble.move(x, y)

    def _finish_recovered(self) -> None:
        if self._snapshot:
            state = state_for_remaining(self._snapshot.remaining_percent)
            self.pet.set_state(state)
            self.bubble.set_state(state)
            if state is PetState.NORMAL:
                self.bubble.set_pet_message("")
