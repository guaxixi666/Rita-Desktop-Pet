from __future__ import annotations

import os
from collections.abc import Callable

from PySide6.QtCore import QEvent, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup, QCursor, QGuiApplication
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMenu, QMessageBox, QWidget

from codex_usage_pet.codex.models import UsageSnapshot
from codex_usage_pet.pet.states import PetState, PetStateTracker, state_for_remaining
from codex_usage_pet.services.paths import log_dir
from codex_usage_pet.services.settings import AppSettings, SettingsStore
from codex_usage_pet.services.startup import StartupManager

from .pet_widget import PetWidget
from .theme import MENU_STYLE
from .usage_bubble import UsageBubble


class PetWindow(QWidget):
    refresh_requested = Signal()
    interval_changed = Signal(int)
    quit_requested = Signal()

    def __init__(
        self,
        settings: AppSettings,
        store: SettingsStore,
        startup: StartupManager,
    ) -> None:
        super().__init__()
        self.settings = settings
        self.store = store
        self.startup = startup
        self._drag_offset: QPoint | None = None
        self._press_global: QPoint | None = None
        self._snapshot: UsageSnapshot | None = None
        self._state_tracker = PetStateTracker()
        self.pet = PetWidget(self)
        self.bubble = UsageBubble(self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)
        layout.addWidget(self.bubble, alignment=Qt.AlignmentFlag.AlignBottom)
        layout.addWidget(self.pet, alignment=Qt.AlignmentFlag.AlignBottom)
        self.bubble.setVisible(settings.show_usage)
        self.pet.clicked.connect(self.toggle_usage_panel)
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(350)
        self._save_timer.timeout.connect(self.save_settings)
        self._apply_window_flags()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("Codex Usage Pet")
        self.setWindowOpacity(settings.opacity)
        for target in (self, self.pet, self.bubble):
            target.installEventFilter(self)
        QTimer.singleShot(0, self._restore_position)

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
            QTimer.singleShot(4500, self._finish_recovered)

    def set_error(self, text: str) -> None:
        self.bubble.set_error(text)

    def build_menu(self) -> QMenu:
        menu = QMenu()
        menu.setStyleSheet(MENU_STYLE)
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
        else:
            self.show()
            self.raise_()

    def save_settings(self) -> None:
        self.settings.window_x = self.x()
        self.settings.window_y = self.y()
        self.store.save(self.settings)

    def set_usage_visible(self, visible: bool) -> None:
        self.settings.show_usage = visible
        self.bubble.set_animated_visible(visible)
        QTimer.singleShot(220, self._finish_panel_animation)
        self.save_settings()

    def toggle_usage_panel(self) -> None:
        self.set_usage_visible(not self.settings.show_usage)

    def _finish_panel_animation(self) -> None:
        self.adjustSize()
        self._clamp_to_screen()

    def set_always_on_top(self, enabled: bool) -> None:
        self.settings.always_on_top = enabled
        self._apply_window_flags()
        self.show()
        self.save_settings()

    def set_locked(self, enabled: bool) -> None:
        self.settings.locked = enabled
        self.save_settings()

    def set_opacity(self, opacity: float) -> None:
        self.settings.opacity = opacity
        self.setWindowOpacity(opacity)
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

    def open_logs(self) -> None:
        path = log_dir()
        path.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            "关于 Codex Usage Pet",
            "Codex Usage Pet 0.1.0\n\nRita 风格原创 Q 版桌宠素材。\n"
            "额度来自本机官方 Codex App Server。\n不读取浏览器 Cookie，不保存认证凭据。",
        )

    def eventFilter(self, watched, event) -> bool:  # type: ignore[no-untyped-def]
        if event.type() == QEvent.Type.ContextMenu:
            self.build_menu().exec(QCursor.pos())
            return True
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self._press_global = event.globalPosition().toPoint()
            if self.settings.locked:
                return watched is self.pet or super().eventFilter(watched, event)
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            return True
        if event.type() == QEvent.Type.MouseMove and self._drag_offset and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(self._bounded_position(event.globalPosition().toPoint() - self._drag_offset))
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
                self.pet.clicked.emit()
            if not self.settings.locked:
                self._save_timer.start()
            if watched is self.pet or not self.settings.locked:
                return True
        return super().eventFilter(watched, event)

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        event.ignore()
        self.hide()

    def _apply_window_flags(self) -> None:
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if self.settings.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)

    def _restore_position(self) -> None:
        self.adjustSize()
        if self.settings.window_x is None or self.settings.window_y is None:
            screen = QGuiApplication.primaryScreen()
            if screen:
                area = screen.availableGeometry()
                self.move(area.right() - self.width() - 30, area.bottom() - self.height() - 30)
        else:
            self.move(self.settings.window_x, self.settings.window_y)
        self._clamp_to_screen()

    def _bounded_position(self, point: QPoint) -> QPoint:
        screen = QGuiApplication.screenAt(point + QPoint(self.width() // 2, self.height() // 2))
        screen = screen or QGuiApplication.primaryScreen()
        if not screen:
            return point
        area = screen.availableGeometry()
        return QPoint(
            max(area.left(), min(point.x(), area.right() - self.width() + 1)),
            max(area.top(), min(point.y(), area.bottom() - self.height() + 1)),
        )

    def _clamp_to_screen(self) -> None:
        self.move(self._bounded_position(self.pos()))

    def _finish_recovered(self) -> None:
        if self._snapshot:
            state = state_for_remaining(self._snapshot.remaining_percent)
            self.pet.set_state(state)
            self.bubble.set_state(state)
            if state is PetState.NORMAL:
                self.bubble.set_pet_message("")

