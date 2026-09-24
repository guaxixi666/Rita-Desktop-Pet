from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from codex_usage_pet.pet.action_policy import ActionEvent, NONE_ACTION
from codex_usage_pet.skins.models import SkinPack

from .theme import rgba

_ACTION_LABELS = {
    "none": "无反应",
    "idle": "Idle",
    "blink": "Blink",
    "hover": "微笑 / 注视",
    "click": "Click React",
    "wave": "Wave",
    "stretch": "Tidy Hair",
    "sit_transition": "Sit Transition",
    "sit": "Sit",
    "critical": "Critical",
    "sleep": "Sleep",
    "sleep_react": "Sleep React",
}

_GROUPS: tuple[tuple[str, tuple[ActionEvent, ...]], ...] = (
    ("Hover", (ActionEvent.HOVER,)),
    ("Click", (ActionEvent.CLICK,)),
    ("随机待机", (ActionEvent.IDLE_RANDOM,)),
    (
        "LOW",
        (ActionEvent.LOW_ON_ENTER, ActionEvent.LOW_IDLE, ActionEvent.LOW_ON_EXIT),
    ),
    (
        "CRITICAL",
        (
            ActionEvent.CRITICAL_ON_ENTER,
            ActionEvent.CRITICAL_IDLE,
            ActionEvent.CRITICAL_ON_EXIT,
        ),
    ),
    (
        "EMPTY",
        (ActionEvent.EMPTY_ON_ENTER, ActionEvent.EMPTY_IDLE, ActionEvent.EMPTY_ON_EXIT),
    ),
    ("RECOVERED", (ActionEvent.RECOVERED,)),
)

_EVENT_LABELS = {
    ActionEvent.HOVER: "候选动作",
    ActionEvent.CLICK: "候选动作",
    ActionEvent.IDLE_RANDOM: "候选动作",
    ActionEvent.RECOVERED: "恢复动作",
    ActionEvent.LOW_ON_ENTER: "进入状态",
    ActionEvent.LOW_IDLE: "持续姿态",
    ActionEvent.LOW_ON_EXIT: "离开状态",
    ActionEvent.CRITICAL_ON_ENTER: "进入状态",
    ActionEvent.CRITICAL_IDLE: "持续姿态",
    ActionEvent.CRITICAL_ON_EXIT: "离开状态",
    ActionEvent.EMPTY_ON_ENTER: "进入状态",
    ActionEvent.EMPTY_IDLE: "持续姿态",
    ActionEvent.EMPTY_ON_EXIT: "离开状态",
}


class ActionSettingsDialog(QDialog):
    def __init__(
        self,
        skin: SkinPack,
        overrides: dict[str, list[str]] | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.skin = skin
        self._checkboxes: dict[str, list[QCheckBox]] = {}
        self.setWindowTitle(f"动作设置 · {skin.name}")
        self.setMinimumSize(520, 440)
        palette = skin.theme
        self.setStyleSheet(
            f"""
            QDialog {{ background: {palette.background}; color: {palette.text_primary}; }}
            QTabWidget::pane, QGroupBox {{ border: 1px solid {rgba(palette.border, 110)}; border-radius: 8px; }}
            QTabBar::tab {{ background: {palette.panel}; color: {palette.text_secondary}; padding: 7px 10px; }}
            QTabBar::tab:selected {{ color: {palette.text_primary}; background: {rgba(palette.primary, 90)}; }}
            QCheckBox {{ padding: 4px; }}
            QPushButton {{ background: {palette.panel}; color: {palette.text_primary}; border: 1px solid {palette.border}; border-radius: 6px; padding: 6px 12px; }}
            """
        )

        layout = QVBoxLayout(self)
        tabs = QTabWidget(self)
        for title, events in _GROUPS:
            tabs.addTab(self._make_tab(events, overrides or {}), title)
        layout.addWidget(tabs)

        controls = QHBoxLayout()
        reset = QPushButton("恢复当前皮肤默认设置", self)
        reset.clicked.connect(self.restore_defaults)
        controls.addWidget(reset)
        controls.addStretch(1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        controls.addWidget(buttons)
        layout.addLayout(controls)

    def _make_tab(
        self, events: tuple[ActionEvent, ...], overrides: dict[str, list[str]]
    ) -> QWidget:
        content = QWidget(self)
        content_layout = QVBoxLayout(content)
        for event in events:
            candidates = self.skin.action_policy.pool(event)
            if not candidates:
                continue
            group = QGroupBox(_EVENT_LABELS[event], content)
            group_layout = QVBoxLayout(group)
            enabled = set(overrides[event.value]) if event.value in overrides else None
            boxes: list[QCheckBox] = []
            for candidate in candidates:
                action = candidate.action
                label = _ACTION_LABELS.get(action, action.replace("_", " ").title())
                box = QCheckBox(label, group)
                box.setProperty("action_id", action)
                box.setChecked(enabled is None or action in enabled)
                supported = action == NONE_ACTION or action in self.skin.supported_actions
                box.setEnabled(supported)
                if not supported:
                    box.setToolTip("当前皮肤没有这个动作素材，会在选择时自动过滤。")
                group_layout.addWidget(box)
                boxes.append(box)
            self._checkboxes[event.value] = boxes
            content_layout.addWidget(group)
        content_layout.addStretch(1)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(content)
        wrapper = QWidget(self)
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.addWidget(scroll)
        return wrapper

    def restore_defaults(self) -> None:
        for boxes in self._checkboxes.values():
            for box in boxes:
                box.setChecked(True)

    def selected_overrides(self) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for event, boxes in self._checkboxes.items():
            defaults = [candidate.action for candidate in self.skin.action_policy.pool(event)]
            selected = [
                str(box.property("action_id")) for box in boxes if box.isChecked()
            ]
            if selected != defaults:
                result[event] = selected
        return result
