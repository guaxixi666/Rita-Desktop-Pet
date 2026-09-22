from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget

from codex_usage_pet.codex.models import UsageSnapshot, UsageWindow


class UsageRow(QWidget):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title = QLabel(title)
        self.title.setObjectName("rowTitle")
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        self.detail = QLabel("—")
        self.detail.setObjectName("detail")
        self.reset = QLabel("")
        self.reset.setObjectName("reset")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self.title)
        layout.addWidget(self.bar)
        layout.addWidget(self.detail)
        layout.addWidget(self.reset)

    def set_window(self, window: UsageWindow | None, weekly: bool = False) -> None:
        self.setVisible(window is not None)
        if window is None:
            return
        remaining = int(round(window.remaining_percent))
        self.bar.setValue(remaining)
        color = "#66d9a3" if remaining > 30 else "#f6c85f" if remaining >= 10 else "#ff7474"
        self.bar.setStyleSheet(
            "QProgressBar{background:#3c4252;border:0;border-radius:4px;}"
            f"QProgressBar::chunk{{background:{color};border-radius:4px;}}"
        )
        self.detail.setText(f"剩余 {remaining}%")
        self.reset.setText(_format_reset(window.resets_at, weekly))


class UsageBubble(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("usageBubble")
        self.setFixedWidth(224)
        self._snapshot: UsageSnapshot | None = None
        title = QLabel("Codex")
        title.setObjectName("title")
        self.plan = QLabel("")
        self.plan.setObjectName("plan")
        self.five_hour = UsageRow("5h")
        self.weekly = UsageRow("Weekly")
        self.credits = QLabel("")
        self.credits.setObjectName("credits")
        self.status = QLabel("正在读取额度…")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(7)
        layout.addWidget(title)
        layout.addWidget(self.plan)
        layout.addWidget(self.five_hour)
        layout.addWidget(self.weekly)
        layout.addWidget(self.credits)
        layout.addWidget(self.status)
        self.setStyleSheet(
            "#usageBubble{background:rgba(24,28,38,235);border:1px solid rgba(255,255,255,35);"
            "border-radius:16px;color:#f3f5f7;}"
            "QLabel{color:#f3f5f7;font-family:'Segoe UI','Microsoft YaHei UI';font-size:12px;}"
            "#title{font-size:17px;font-weight:700;}#plan{color:#aeb7c8;font-size:10px;}"
            "#rowTitle{font-weight:600;}#detail{font-weight:600;}#reset{color:#aeb7c8;font-size:10px;}"
            "#credits{color:#d4c2ff;font-weight:600;}#status{color:#ffd68a;}"
        )
        timer = QTimer(self)
        timer.setInterval(60_000)
        timer.timeout.connect(self._refresh_text)
        timer.start()

    def set_snapshot(self, snapshot: UsageSnapshot) -> None:
        self._snapshot = snapshot
        self.plan.setText((snapshot.account.plan_type or "").replace("_", " ").title())
        self.five_hour.set_window(snapshot.five_hour)
        self.weekly.set_window(snapshot.weekly, weekly=True)
        self.credits.setText(_format_credits(snapshot))
        self.credits.setVisible(bool(self.credits.text()))
        self.status.clear()
        self._refresh_text()

    def set_error(self, text: str) -> None:
        self.status.setText(text)

    def set_pet_message(self, text: str) -> None:
        self.status.setText(text)

    def _refresh_text(self) -> None:
        if self._snapshot:
            self.five_hour.set_window(self._snapshot.five_hour)
            self.weekly.set_window(self._snapshot.weekly, weekly=True)


def _format_reset(value: datetime | None, weekly: bool) -> str:
    if value is None:
        return "重置时间未知"
    if weekly:
        weekdays = "一二三四五六日"
        return f"周{weekdays[value.weekday()]} {value:%H:%M} 重置"
    seconds = max(0, int((value - datetime.now().astimezone()).total_seconds()))
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    return f"{hours}h {minutes:02d}m 后重置"


def _format_credits(snapshot: UsageSnapshot) -> str:
    credits = snapshot.credits
    if credits:
        if credits.unlimited:
            return "Credits  ∞"
        if credits.balance is not None:
            balance = credits.balance.quantize(Decimal("1")) if credits.balance == credits.balance.to_integral() else credits.balance
            return f"Credits  {balance}"
    if snapshot.reset_credits_available:
        return f"重置券  {snapshot.reset_credits_available}"
    return ""

