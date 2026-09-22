from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


def make_app_icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#9b87f5"))
    painter.setPen(QColor("#393342"))
    painter.drawEllipse(8, 8, 48, 48)
    painter.setBrush(QColor("#f4f0ff"))
    painter.drawEllipse(21, 27, 5, 7)
    painter.drawEllipse(38, 27, 5, 7)
    painter.end()
    return QIcon(pixmap)


class TrayIcon(QObject):
    def __init__(self, menu_factory: Callable[[], QMenu], toggle_window: Callable[[], None]) -> None:
        super().__init__()
        self._menu_factory = menu_factory
        self._toggle_window = toggle_window
        self.icon = QSystemTrayIcon(make_app_icon())
        self.icon.setToolTip("Codex Usage Pet")
        self.icon.activated.connect(self._activated)
        self.icon.show()

    def refresh_menu(self) -> None:
        self.icon.setContextMenu(self._menu_factory())

    def hide(self) -> None:
        self.icon.hide()

    def _activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_window()

