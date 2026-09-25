"""نقطه ورود برنامه «دانلودر تلگرام» (Personal / Public)."""

from __future__ import annotations

import logging
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from config import api_credentials
from config.edition import current as current_edition
from config.settings import SettingsStore
from gui import theme as theme_mod
from gui.app_icon import load_app_icon
from gui.main_window import MainWindow
from gui.setup_wizard import SetupWizard
from services.download_service import DownloadService
from services.logging_service import setup_logging
from utils.i18n import set_language as set_i18n_language
from utils.i18n import t
from utils.updates import check_latest, is_newer

logger = logging.getLogger(__name__)


def _apply_app_theme(app: QApplication, settings) -> None:
    family = theme_mod.pick_font(app)
    app.setStyleSheet(theme_mod.build_qss(settings.theme, family, settings.font_size))
    theme_mod.set_font(app, family, settings.font_size)
    direction = Qt.LayoutDirection.RightToLeft if settings.rtl else Qt.LayoutDirection.LeftToRight
    app.setLayoutDirection(direction)


def _auto_check_update(window: MainWindow, settings) -> None:
    url = (settings.update_url or "").strip()
    if not url or not settings.auto_check_updates:
        return
    try:
        exists, info = check_latest(url)
        if exists and is_newer(api_credentials.APP_VERSION, str(info.get("version", ""))):
            window._notify_os("بروزرسانی", f"{info.get('version')}")
    except Exception as exc:  # pragma: no cover
        logger.info("بررسی خودکار بروزرسانی ناموفق بود: %s", exc)


def _setup_windows_integrations(window: MainWindow, service, args: list[str]) -> None:
    if sys.platform != "win32":
        return
    try:
        from utils.integrations import (
            apply_protocol_entries,
            current_exe,
            parse_protocol_url,
            protocol_args,
            protocol_entries,
            register_send_to,
        )

        exe = current_exe()
        try:
            apply_protocol_entries(protocol_entries(exe))
            register_send_to(exe)
        except Exception as exc:  # pragma: no cover
            logger.info("ثبت یکپارچه‌سازی ویندوز ناموفق بود: %s", exc)

        links = [parse_protocol_url(a) for a in protocol_args(args)]
        links = [link for link in links if link]
        for link in links:
            if service.add_link(link):
                window._notify_os(t("app.title"), str(link))
    except Exception as exc:  # pragma: no cover
        logger.info("پردازش آرگومان‌های پروتکل ناموفق بود: %s", exc)


def main() -> int:
    setup_logging()
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)

    edition = current_edition()
    app.setApplicationName(edition.exe_name)
    app.setApplicationVersion(edition.app_version)
    app.setApplicationDisplayName(edition.display_name)
    app.setOrganizationName("TelegramDownloader")

    settings_store = SettingsStore()
    settings = settings_store.load()
    set_i18n_language(settings.language)
    _apply_app_theme(app, settings)

    icon = load_app_icon()
    app.setWindowIcon(icon)

    from config.settings import CredentialStore

    cred_store = CredentialStore()
    service = DownloadService(settings, settings_store, cred_store)

    window = MainWindow(service, settings)
    window.set_app_icon(icon)
    window.set_tray_icon(icon)
    window.show()

    service.start()

    wizard_already_shown = False

    def show_wizard_if_needed() -> None:
        nonlocal wizard_already_shown
        if wizard_already_shown:
            return
        wizard_already_shown = True
        SetupWizard.run(service, window)

    needs_setup = not service.list_accounts()
    if needs_setup:
        QTimer.singleShot(400, show_wizard_if_needed)
    else:
        def on_auth(phone_: str) -> None:
            if not phone_ and not wizard_already_shown:
                QTimer.singleShot(400, show_wizard_if_needed)

        service.auth_changed.connect(on_auth)

    QTimer.singleShot(3000, lambda: _auto_check_update(window, settings))
    QTimer.singleShot(500, lambda: _setup_windows_integrations(window, service, list(sys.argv[1:])))
    app.aboutToQuit.connect(service.stop)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())