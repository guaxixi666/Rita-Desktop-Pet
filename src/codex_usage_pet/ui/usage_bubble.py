from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from codex_usage_pet.codex.models import UsageSnapshot, UsageWindow
from codex_usage_pet.pet.states import PetState
from codex_usage_pet.skins.models import SkinPack, SkinTheme

from . import theme
from .localization import tr


class UsageRow(QWidget):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title = QLabel(title)
        self._theme = theme.DEFAULT_THEME
        self.title.setObjectName("rowTitle")
        self.detail = QLabel("—")
        self.detail.setObjectName("percentage")
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(self.title)
        header.addStretch(1)
        header.addWidget(self.detail)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        self.bar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset = QLabel("")
        self.reset.setObjectName("reset")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addLayout(header)
        layout.addWidget(self.bar)
        layout.addWidget(self.reset)

    def set_window(self, window: UsageWindow | None, weekly: bool = False) -> None:
        self.setVisible(window is not None)
        if window is None:
            return
        remaining = int(round(window.remaining_percent))
        self.bar.setValue(remaining)
        color = _progress_color(remaining, self._theme)
        self.bar.setStyleSheet(
            f"QProgressBar{{background:{self._theme.progress_track};border:0;border-radius:3px;}}"
            f"QProgressBar::chunk{{background:{color};border-radius:3px;}}"
            f"QProgressBar:hover::chunk{{background:{self._theme.highlight};}}"
        )
        self.detail.setText(tr("usage.remaining", value=remaining))
        self.reset.setText(_format_reset(window.resets_at, weekly))

    def set_theme(self, palette: SkinTheme) -> None:
        self._theme = palette


class UsageBubble(QWidget):
    WIDTH = 218

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("usageBubbleContainer")
        self.setFixedWidth(self.WIDTH)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._snapshot: UsageSnapshot | None = None
        self._state = PetState.NORMAL
        self._theme = theme.DEFAULT_THEME

        self.panel = QWidget(self)
        self.panel.setObjectName("usageBubble")

        self.rose = QLabel(self._theme.decorator)
        self.rose.setObjectName("roseMark")
        title = QLabel("CODEX")
        title.setObjectName("title")
        self.plan = QLabel("")
        self.plan.setObjectName("plan")
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)
        header.addWidget(self.rose)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.plan)

        line = QWidget()
        line.setObjectName("decorLine")
        line.setFixedHeight(1)
        self.five_hour = UsageRow(tr("usage.five_hour"))
        self.weekly = UsageRow(tr("usage.weekly"))
        self.credits = QLabel("")
        self.credits.setObjectName("credits")
        self.status = QLabel(tr("usage.reading"))
        self.status.setObjectName("status")
        self.status.setWordWrap(True)

        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(15, 13, 15, 13)
        panel_layout.setSpacing(10)
        panel_layout.addLayout(header)
        panel_layout.addWidget(line)
        panel_layout.addWidget(self.five_hour)
        panel_layout.addWidget(self.weekly)
        panel_layout.addWidget(self.credits)
        panel_layout.addWidget(self.status)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 12)
        outer.addWidget(self.panel)

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)
        self._fade = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade.setDuration(190)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.finished.connect(self._finish_fade)
        self._hide_after_fade = False

        self._apply_style()
        timer = QTimer(self)
        timer.setInterval(60_000)
        timer.timeout.connect(self._refresh_text)
        timer.start()

    def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        shadow_rect = QRectF(self.panel.geometry()).translated(0, 3)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(7, 5, 9, 48))
        painter.drawRoundedRect(shadow_rect, 15, 15)
        super().paintEvent(event)

    def set_snapshot(self, snapshot: UsageSnapshot) -> None:
        self._snapshot = snapshot
        self.plan.setText(_format_plan(snapshot.account.plan_type))
        self.five_hour.set_window(snapshot.five_hour)
        self.weekly.set_window(snapshot.weekly, weekly=True)
        self.credits.setText(_format_credits(snapshot))
        self.credits.setVisible(bool(self.credits.text()))
        self.status.clear()
        self._refresh_text()

    def set_state(self, state: PetState) -> None:
        self._state = state
        self._apply_style()
        if self._snapshot:
            self._refresh_text()

    def set_skin(self, skin: SkinPack) -> None:
        self._theme = skin.theme
        self.rose.setText(skin.theme.decorator)
        self.five_hour.set_theme(skin.theme)
        self.weekly.set_theme(skin.theme)
        self._apply_style()
        self._refresh_text()

    def set_error(self, text: str) -> None:
        self.status.setText(text)

    def set_pet_message(self, text: str) -> None:
        self.status.setText(text)

    def set_animated_visible(self, visible: bool) -> None:
        self._fade.stop()
        self._hide_after_fade = not visible
        if visible:
            self.setVisible(True)
            self._opacity_effect.setOpacity(0.0)
            self._fade.setStartValue(0.0)
            self._fade.setEndValue(1.0)
        else:
            self._fade.setStartValue(self._opacity_effect.opacity())
            self._fade.setEndValue(0.0)
        self._fade.start()

    def _finish_fade(self) -> None:
        if self._hide_after_fade:
            self.setVisible(False)
        else:
            self._opacity_effect.setOpacity(1.0)

    def _refresh_text(self) -> None:
        if self._snapshot:
            self.five_hour.set_window(self._snapshot.five_hour)
            self.weekly.set_window(self._snapshot.weekly, weekly=True)

    def _apply_style(self) -> None:
        dimmed = self._state is PetState.EMPTY
        palette = self._theme
        background = theme.rgba(palette.background if dimmed else palette.panel, 220)
        border = palette.empty if dimmed else palette.border
        accent = palette.empty if dimmed else palette.primary
        self.panel.setStyleSheet(
            f"#usageBubble{{background:{background};border:1px solid {border};border-radius:15px;}}"
            f"QLabel{{color:{palette.text_primary};font-family:'{theme.FONT_FAMILY}';font-size:11px;font-weight:400;}}"
            f"#title{{font-size:13px;font-weight:600;letter-spacing:1px;}}"
            f"#roseMark{{color:{accent};font-size:10px;}}"
            f"#plan{{color:{palette.text_secondary};font-size:9px;letter-spacing:1px;}}"
            f"#rowTitle{{color:{palette.text_secondary};font-size:10px;font-weight:600;letter-spacing:1px;}}"
            f"#percentage{{color:{palette.low};font-size:14px;font-weight:600;}}"
            f"#reset{{color:{palette.text_secondary};font-size:9px;}}"
            f"#credits{{color:{palette.low};font-size:9px;font-weight:600;letter-spacing:1px;}}"
            f"#status{{color:{accent};font-size:10px;}}"
            f"#decorLine{{background:{theme.rgba(palette.primary, 55)};}}"
        )


def _progress_color(remaining: int, palette: SkinTheme) -> str:
    if remaining <= 0:
        return palette.empty
    if remaining < 10:
        return palette.critical
    if remaining <= 30:
        return palette.low
    return palette.primary


def _format_reset(value: datetime | None, weekly: bool) -> str:
    if value is None:
        return tr("usage.reset_unknown")
    if weekly:
        weekdays = "一二三四五六日"
        return f"周{weekdays[value.weekday()]} {value:%H:%M} 恢复"
    seconds = max(0, int((value - datetime.now().astimezone()).total_seconds()))
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    if hours:
        return f"{hours} 小时 {minutes} 分后恢复"
    return f"{minutes} 分后恢复"


def _format_credits(snapshot: UsageSnapshot) -> str:
    credits = snapshot.credits
    if credits:
        if credits.unlimited:
            return tr("usage.credits", value="∞")
        if credits.balance is not None:
            balance = (
                credits.balance.quantize(Decimal("1"))
                if credits.balance == credits.balance.to_integral()
                else credits.balance
            )
            return tr("usage.credits", value=balance)
    if snapshot.reset_credits_available:
        return tr("usage.reset_pass", value=snapshot.reset_credits_available)
    return ""


def _format_plan(value: str | None) -> str:
    if not value:
        return ""
    normalized = value.strip().lower().replace("-", "_")
    known = {
        "free": "免费版",
        "plus": "Plus 版",
        "pro": "Pro 版",
        "team": "团队版",
        "business": "商业版",
        "enterprise": "企业版",
        "edu": "教育版",
    }
    return known.get(normalized, value.replace("_", " "))

