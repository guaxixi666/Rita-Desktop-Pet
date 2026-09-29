from __future__ import annotations

import argparse
import logging
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from codex_usage_pet.services.logger import configure_logging
from codex_usage_pet.services.desktop_shortcut import DesktopShortcutManager
from codex_usage_pet.services.settings import SettingsStore
from codex_usage_pet.services.startup import StartupManager
from codex_usage_pet.services.usage_service import UsageService
from codex_usage_pet.skins.manager import SkinManager
from codex_usage_pet.ui.pet_window import PetWindow
from codex_usage_pet.ui.tray import TrayIcon, make_app_icon


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rita Desktop Pet")
    parser.add_argument("--smoke-test", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--animation-test", metavar="ACTION_ID", help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    log_path = configure_logging()
    logger = logging.getLogger(__name__)
    logger.info("Rita Desktop Pet starting; log=%s", log_path)
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Rita Desktop Pet")
    app.setApplicationVersion("0.1.0-beta")
    app.setQuitOnLastWindowClosed(False)

    store = SettingsStore()
    settings = store.load()
    startup = StartupManager()
    shortcuts = DesktopShortcutManager()
    skin_manager = SkinManager(settings, store)
    app.setWindowIcon(make_app_icon(skin_manager.current))
    window = PetWindow(settings, store, startup, skin_manager, shortcuts)
    service = UsageService(settings.refresh_interval)
    tray = TrayIcon(window.build_menu, window.toggle_visible, window.current_skin)

    service.usage_updated.connect(window.set_snapshot)
    service.read_failed.connect(window.set_error)
    window.refresh_requested.connect(service.refresh_now)
    window.interval_changed.connect(service.set_interval)
    window.menu_changed.connect(tray.refresh_menu)
    window.skin_changed.connect(tray.set_skin)

    stopping = False

    def shutdown() -> None:
        nonlocal stopping
        if stopping:
            return
        stopping = True
        window.save_settings()
        service.stop()
        tray.hide()
        logger.info("Rita Desktop Pet stopped")
        app.quit()

    window.quit_requested.connect(shutdown)
    app.aboutToQuit.connect(service.stop)
    tray.refresh_menu()
    window.show()
    if args.animation_test:
        QTimer.singleShot(100, lambda: window.pet.play_action(args.animation_test))
    service.start()
    if args.smoke_test:
        # Leave enough time for a real App Server handshake and first quota
        # read; a shorter timer only proved that Qt could open and close.
        QTimer.singleShot(7000, shutdown)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

