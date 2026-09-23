from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from codex_usage_pet.services.paths import resource_path


def make_app_icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    sheet = QPixmap(str(resource_path("assets/rita/rita_sprite_sheet.png")))
    if sheet.isNull():
        return QIcon(pixmap)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    painter.drawPixmap(
        QRectF(1, 1, 62, 62),
        sheet,
        QRectF(0, 0, sheet.width() / 3, sheet.height() / 2),
    )
    painter.end()
    return QIcon(pixmap)


class TrayIcon(QObject):
    def __init__(self, menu_factory: Callable[[], QMenu], toggle_window: Callable[[], None]) -> None:
        super().__init__()
        self._menu_factory = menu_factory
        self._toggle_window = toggle_window
        self._menu: QMenu | None = None
        self.icon = QSystemTrayIcon(make_app_icon(), self)
        self.icon.setToolTip("Codex Usage Pet")
        self.icon.activated.connect(self._activated)
        self.icon.show()

    def refresh_menu(self) -> None:
        old_menu = self._menu
        self._menu = self._menu_factory()
        self.icon.setContextMenu(self._menu)
        if old_menu is not None:
            old_menu.deleteLater()

    def hide(self) -> None:
        # QSystemTrayIcon does not own its context menu.  Detaching it before
        # Qt tears down the Windows notification-area object avoids a dangling
        # native menu during fast smoke-test shutdowns.
        self.icon.setContextMenu(None)
        self.icon.hide()

    def _activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_window()

