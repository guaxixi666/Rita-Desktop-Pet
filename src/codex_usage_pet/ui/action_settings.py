from __future__ import annotations

from PySide6.QtCore import QEasingCurve, Property, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QScrollArea, QToolButton, QVBoxLayout, QWidget,
)

from codex_usage_pet.pet.action_policy import ActionEvent, NONE_ACTION
from codex_usage_pet.skins.models import SkinPack

from .localization import action_name, tr
from .theme import rgba


_CARDS: tuple[tuple[str, tuple[ActionEvent, ...], bool], ...] = (
    ("click", (ActionEvent.CLICK,), True),
    ("idle_random", (ActionEvent.IDLE_RANDOM,), True),
)


def _event_part_name(event: ActionEvent) -> str:
    if event.value.endswith("_on_enter"):
        return tr("event.enter")
    if event.value.endswith("_idle"):
        return tr("event.idle")
    if event.value.endswith("_on_exit"):
        return tr("event.exit")
    return ""


class ActionChip(QPushButton):
    def __init__(self, action_id: str, parent: QWidget | None = None) -> None:
        super().__init__(action_name(action_id), parent)
        self.action_id = action_id
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("action_id", action_id)
        self.toggled.connect(self._refresh_text)

    def _refresh_text(self, checked: bool) -> None:
        self.setText(("✓ " if checked else "") + action_name(self.action_id))


class EventCard(QFrame):
    changed = Signal()

    def __init__(self, card_id: str, events: tuple[ActionEvent, ...], skin: SkinPack,
                 overrides: dict[str, list[str]], expanded: bool,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.card_id = card_id
        self.events = events
        self.skin = skin
        self._expanded = expanded
        self._chips: dict[str, list[ActionChip]] = {}
        self.setObjectName("eventCard")

        self.toggle = QToolButton(self)
        self.toggle.setObjectName("cardToggle")
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        self.toggle.setText(tr(f"event.{card_id}"))
        self.toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle.clicked.connect(self.set_expanded)
        description = QLabel(tr(f"event.{card_id}.description"), self)
        description.setObjectName("cardDescription")
        description.setWordWrap(True)
        header = QVBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(2)
        header.addWidget(self.toggle)
        header.addWidget(description)

        self.body = QWidget(self)
        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(0, 8, 0, 0)
        body_layout.setSpacing(9)
        for event in events:
            candidates = skin.action_policy.pool(event)
            if not candidates:
                continue
            part = _event_part_name(event)
            if part:
                label = QLabel(part, self.body)
                label.setObjectName("eventPart")
                body_layout.addWidget(label)
            chips = QWidget(self.body)
            grid = QGridLayout(chips)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(7)
            grid.setVerticalSpacing(7)
            enabled = set(overrides[event.value]) if event.value in overrides else None
            items: list[ActionChip] = []
            for index, candidate in enumerate(candidates):
                action = candidate.action
                chip = ActionChip(action, chips)
                chip.setChecked(enabled is None or action in enabled)
                chip._refresh_text(chip.isChecked())
                supported = action == NONE_ACTION or action in skin.supported_actions
                chip.setEnabled(supported)
                if not supported:
                    chip.setToolTip("当前皮肤没有这个动作素材，运行时会自动忽略。")
                chip.toggled.connect(self._selection_changed)
                grid.addWidget(chip, index // 3, index % 3)
                items.append(chip)
            self._chips[event.value] = items
            body_layout.addWidget(chips)
        self.source = QLabel(self)
        self.source.setObjectName("configSource")
        body_layout.addWidget(self.source)
        self._refresh_source()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(5)
        layout.addLayout(header)
        layout.addWidget(self.body)
        self.body.setVisible(expanded)
        self._body_height = self.body.sizeHint().height()
        self._animation = QPropertyAnimation(self, b"bodyHeight", self)
        self._animation.setDuration(190)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._set_body_height(self._body_height if expanded else 0)

    def _get_body_height(self) -> int:
        return self.body.maximumHeight()

    def _set_body_height(self, value: int) -> None:
        self.body.setMaximumHeight(max(0, value))
        self.body.setMinimumHeight(0)

    bodyHeight = Property(int, _get_body_height, _set_body_height)

    def set_expanded(self) -> None:
        self._expanded = not self._expanded
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if self._expanded else Qt.ArrowType.RightArrow)
        self._animation.stop()
        if self._expanded:
            self.body.setVisible(True)
            self._body_height = self.body.sizeHint().height()
            self._animation.setStartValue(0)
            self._animation.setEndValue(self._body_height)
        else:
            self._animation.setStartValue(self.body.height())
            self._animation.setEndValue(0)
        try:
            self._animation.finished.disconnect(self._finish_animation)
        except RuntimeError:
            pass
        self._animation.finished.connect(self._finish_animation)
        self._animation.start()

    def _finish_animation(self) -> None:
        if not self._expanded:
            self.body.setVisible(False)

    def _selection_changed(self) -> None:
        self._refresh_source()
        self.changed.emit()

    def _refresh_source(self) -> None:
        custom = any(self.selection(event.value) != self.defaults(event.value) for event in self.events)
        self.source.setText(tr("source.custom" if custom else "source.default"))

    def defaults(self, event: str) -> list[str]:
        return [candidate.action for candidate in self.skin.action_policy.pool(event)]

    def selection(self, event: str) -> list[str]:
        return [chip.action_id for chip in self._chips.get(event, []) if chip.isChecked()]

    def restore_defaults(self) -> None:
        for event, chips in self._chips.items():
            defaults = set(self.defaults(event))
            for chip in chips:
                chip.setChecked(chip.action_id in defaults)
        self._refresh_source()


class ActionSettingsDialog(QDialog):
    preview_changed = Signal(dict)
    quiet_mode_changed = Signal(bool)

    def __init__(self, skin: SkinPack, overrides: dict[str, list[str]] | None,
                 parent: QWidget | None = None, *, quiet_mode: bool = False) -> None:
        super().__init__(parent)
        self.skin = skin
        self._cards: list[EventCard] = []
        self.setObjectName("actionSettingsDialog")
        self.setWindowTitle(f"{tr('dialog.interactions.title')} · {skin.name}")
        self.setMinimumSize(600, 660)
        self.resize(620, 720)
        palette = skin.theme
        self.setStyleSheet(f"""
            QDialog#actionSettingsDialog {{ background: {palette.background}; color: {palette.text_primary}; }}
            QLabel {{ color: {palette.text_primary}; font-family: 'Microsoft YaHei UI'; }}
            #pageTitle {{ font-size: 22px; font-weight: 600; }}
            #pageSubtitle, #cardDescription {{ color: {palette.text_secondary}; font-size: 11px; }}
            QFrame#quietCard, QFrame#eventCard {{ background: {rgba(palette.panel, 238)}; border: 1px solid {rgba(palette.border, 105)}; border-radius: 13px; }}
            QToolButton#cardToggle {{ border: 0; color: {palette.text_primary}; font-size: 13px; font-weight: 600; text-align: left; padding: 0; }}
            QToolButton#cardToggle:hover {{ color: {palette.highlight}; }}
            QLabel#eventPart {{ color: {palette.low}; font-size: 10px; font-weight: 600; }}
            QLabel#configSource {{ color: {palette.text_secondary}; font-size: 10px; padding-top: 3px; }}
            QPushButton[action_id] {{ background: {rgba(palette.background, 165)}; color: {palette.text_secondary}; border: 1px solid {rgba(palette.border, 72)}; border-radius: 12px; padding: 6px 10px; min-height: 16px; }}
            QPushButton[action_id]:hover {{ color: {palette.text_primary}; border-color: {palette.highlight}; }}
            QPushButton[action_id]:checked {{ background: {rgba(palette.primary, 92)}; color: {palette.text_primary}; border-color: {palette.highlight}; }}
            QPushButton[action_id]:disabled {{ color: {rgba(palette.text_secondary, 80)}; border-color: {rgba(palette.border, 38)}; }}
            QPushButton#quietToggle {{ background: {rgba(palette.background, 165)}; color: {palette.text_secondary}; border: 1px solid {rgba(palette.border, 90)}; border-radius: 15px; padding: 7px 13px; }}
            QPushButton#quietToggle:checked {{ background: {rgba(palette.primary, 105)}; color: {palette.text_primary}; border-color: {palette.highlight}; }}
            QPushButton#secondaryButton {{ background: transparent; color: {palette.text_secondary}; border: 1px solid {rgba(palette.border, 90)}; border-radius: 9px; padding: 8px 13px; }}
            QPushButton#secondaryButton:hover {{ color: {palette.text_primary}; border-color: {palette.highlight}; }}
            QPushButton#primaryButton {{ background: {palette.primary}; color: {palette.text_primary}; border: 1px solid {palette.highlight}; border-radius: 9px; padding: 8px 18px; font-weight: 600; }}
            QPushButton#primaryButton:hover {{ background: {palette.highlight}; }}
            QScrollArea {{ border: 0; background: transparent; }}
            QScrollBar:vertical {{ width: 7px; background: transparent; margin: 4px 0; }}
            QScrollBar::handle:vertical {{ background: {rgba(palette.primary, 90)}; border-radius: 3px; min-height: 28px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        title = QLabel(tr("dialog.interactions.title"), self)
        title.setObjectName("pageTitle")
        subtitle = QLabel(tr("dialog.interactions.subtitle"), self)
        subtitle.setObjectName("pageSubtitle")
        quiet_card = QFrame(self)
        quiet_card.setObjectName("quietCard")
        quiet_title = QLabel(tr("dialog.quiet.title"), quiet_card)
        quiet_title.setStyleSheet("font-size: 13px; font-weight: 600;")
        quiet_description = QLabel(tr("dialog.quiet.description"), quiet_card)
        quiet_description.setObjectName("cardDescription")
        quiet_text = QVBoxLayout()
        quiet_text.setContentsMargins(0, 0, 0, 0)
        quiet_text.setSpacing(2)
        quiet_text.addWidget(quiet_title)
        quiet_text.addWidget(quiet_description)
        self.quiet_toggle = QPushButton("已关闭", quiet_card)
        self.quiet_toggle.setObjectName("quietToggle")
        self.quiet_toggle.setCheckable(True)
        self.quiet_toggle.setChecked(quiet_mode)
        self.quiet_toggle.setText("已开启" if quiet_mode else "已关闭")
        self.quiet_toggle.toggled.connect(self._quiet_toggled)
        quiet_layout = QHBoxLayout(quiet_card)
        quiet_layout.setContentsMargins(14, 12, 14, 12)
        quiet_layout.addLayout(quiet_text)
        quiet_layout.addStretch(1)
        quiet_layout.addWidget(self.quiet_toggle)

        content = QWidget(self)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(3, 3, 8, 3)
        content_layout.setSpacing(10)
        for card_id, events, expanded in _CARDS:
            card = EventCard(card_id, events, skin, overrides or {}, expanded, content)
            card.changed.connect(self._emit_preview)
            self._cards.append(card)
            content_layout.addWidget(card)
        content_layout.addStretch(1)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        scroll.viewport().setStyleSheet(f"background: {palette.background};")

        restore = QPushButton(tr("dialog.restore"), self)
        restore.setObjectName("secondaryButton")
        restore.clicked.connect(self._confirm_restore)
        cancel = QPushButton(tr("dialog.cancel"), self)
        cancel.setObjectName("secondaryButton")
        cancel.clicked.connect(self.reject)
        save = QPushButton(tr("dialog.save"), self)
        save.setObjectName("primaryButton")
        save.clicked.connect(self.accept)
        controls = QHBoxLayout()
        controls.addWidget(restore)
        controls.addStretch(1)
        controls.addWidget(cancel)
        controls.addWidget(save)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(4)
        layout.addWidget(quiet_card)
        layout.addWidget(scroll, 1)
        layout.addLayout(controls)
        QTimer.singleShot(0, lambda: scroll.verticalScrollBar().setValue(0))

    @property
    def quiet_mode(self) -> bool:
        return self.quiet_toggle.isChecked()

    def _quiet_toggled(self, enabled: bool) -> None:
        self.quiet_toggle.setText("已开启" if enabled else "已关闭")
        self.quiet_mode_changed.emit(enabled)

    def _emit_preview(self) -> None:
        self.preview_changed.emit(self.selected_overrides())

    def _confirm_restore(self) -> None:
        prompt = QMessageBox(self)
        prompt.setWindowTitle(tr("dialog.interactions.title"))
        prompt.setText(tr("dialog.restore.confirm", skin=self.skin.name))
        prompt.setIcon(QMessageBox.Icon.Question)
        cancel = prompt.addButton(tr("dialog.cancel"), QMessageBox.ButtonRole.RejectRole)
        restore = prompt.addButton("恢复默认", QMessageBox.ButtonRole.AcceptRole)
        prompt.setDefaultButton(cancel)
        prompt.exec()
        if prompt.clickedButton() is restore:
            self.restore_defaults()

    def restore_defaults(self) -> None:
        for card in self._cards:
            card.restore_defaults()
        self._emit_preview()

    def selected_overrides(self) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for card in self._cards:
            for event in card.events:
                defaults = card.defaults(event.value)
                selected = card.selection(event.value)
                if selected != defaults:
                    result[event.value] = selected
        return result
