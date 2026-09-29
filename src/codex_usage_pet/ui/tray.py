from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from codex_usage_pet.pet.animator import PetActivity
from codex_usage_pet.skins.loader import SkinRepository
from codex_usage_pet.skins.models import SkinPack


def make_app_icon(skin: SkinPack | None = None) -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    if skin is None:
        repository = SkinRepository()
        repository.scan()
        skin = repository.default()
    asset = skin.asset_for(PetActivity.IDLE)
    sheet = QPixmap(str(asset.path))
    if sheet.isNull():
        return QIcon(pixmap)
    if asset.cell is None:
        source = QRectF(0, 0, sheet.width(), sheet.height())
    else:
        columns, rows = asset.grid
        cell_width = sheet.width() / columns
        cell_height = sheet.height() / rows
        source = QRectF(
            asset.cell[0] * cell_width,
            asset.cell[1] * cell_height,
            cell_width,
            cell_height,
        )
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    painter.drawPixmap(
        QRectF(1, 1, 62, 62),
        sheet,
        source,
    )
    painter.end()
    return QIcon(pixmap)


class TrayIcon(QObject):
    def __init__(
        self,
        menu_factory: Callable[[], QMenu],
        toggle_window: Callable[[], None],
        skin: SkinPack | None = None,
    ) -> None:
        super().__init__()
        self._menu_factory = menu_factory
        self._toggle_window = toggle_window
        self._menu: QMenu | None = None
        self.icon = QSystemTrayIcon(make_app_icon(skin), self)
        self.icon.setToolTip("Rita Desktop Pet")
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

    def set_skin(self, skin: SkinPack) -> None:
        self.icon.setIcon(make_app_icon(skin))

    def _activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle_window()

