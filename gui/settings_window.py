"""پنجره تنظیمات: تلگرام، دانلودها (سرعت/زمان‌بندی)، نمایش، عملیات پس از اتمام، Tray و بروزرسانی."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QTime, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QDoubleSpinBox,
    QTabWidget,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from config.settings import Settings
from config.version import APP_VERSION
from gui.about_dialog import AboutDialog
from gui.widgets import set_btn_type
from utils import security
from utils.i18n import t
from utils.updates import check_latest, is_newer

logger = logging.getLogger(__name__)

_SPEED_PRESETS = [
    ("speed.unlimited", 0),
    ("speed.kb512", 512),
    ("speed.mb1", 1024),
    ("speed.mb2", 2048),
    ("speed.mb5", 5120),
    ("speed.mb10", 10240),
    ("speed.custom", -1),
]

_ACTIONS = [
    ("action.none", "none"),
    ("action.exit", "exit"),
    ("action.shutdown", "shutdown"),
    ("action.restart", "restart"),
    ("action.sleep", "sleep"),
    ("action.hibernate", "hibernate"),
]


class SettingsWindow(QDialog):
    """نمایش و ویرایش تنظیمات برنامه."""

    saved = Signal(object)

    def __init__(
        self,
        settings: Settings,
        phone: str,
        logged_in: bool,
        on_rerun_wizard: Optional[Callable[[], None]] = None,
        on_logout: Optional[Callable[[], None]] = None,
        accounts: Optional[list] = None,
        on_remove_account: Optional[Callable[[str], None]] = None,
        service=None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._settings = settings
        self._service = service
        self._on_rerun_wizard = on_rerun_wizard
        self._on_logout = on_logout
        self._accounts = list(accounts) if accounts else []
        self._on_remove_account = on_remove_account

        self.setWindowTitle(t("settings.title"))
        self.setMinimumWidth(700)
        self._build_ui(phone, logged_in)

    # ------------------------------------------------------------------ ui
    def _build_ui(self, phone: str, logged_in: bool) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(14)

        tabs = QTabWidget()
        tabs.addTab(self._build_telegram_tab(phone, logged_in), t("settings.tab.general"))
        tabs.addTab(self._build_downloads_tab(), t("settings.tab.downloads"))
        tabs.addTab(self._build_appearance_tab(), t("settings.tab.appearance"))
        tabs.addTab(self._build_operations_tab(), t("settings.tab.operations"))
        tabs.addTab(self._build_tray_tab(), t("settings.tab.tray"))
        tabs.addTab(self._build_updates_tab(), t("settings.tab.updates"))
        tabs.addTab(self._build_storage_tab(), t("settings.tab.storage"))
        root.addWidget(tabs)

        self.lbl_status = QLabel()
        self.lbl_status.setObjectName("errorText")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.hide()
        root.addWidget(self.lbl_status)

        footer = QHBoxLayout()
        self.btn_about = QPushButton(t("about.button"))
        self.btn_about.setProperty("btnType", "ghost")
        set_btn_type(self.btn_about, "ghost")
        self.btn_about.clicked.connect(self._open_about)
        footer.addWidget(self.btn_about)
        self.btn_export = QPushButton(t("settings.export"))
        self.btn_export.setProperty("btnType", "ghost")
        set_btn_type(self.btn_export, "ghost")
        self.btn_export.clicked.connect(self._on_export)
        footer.addWidget(self.btn_export)
        self.btn_import = QPushButton(t("settings.import"))
        self.btn_import.setProperty("btnType", "ghost")
        set_btn_type(self.btn_import, "ghost")
        self.btn_import.clicked.connect(self._on_import)
        footer.addWidget(self.btn_import)
        footer.addStretch(1)

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        box.button(QDialogButtonBox.StandardButton.Save).setText(t("settings.save"))
        box.button(QDialogButtonBox.StandardButton.Cancel).setText(t("settings.cancel"))
        box.accepted.connect(self._on_save)
        box.rejected.connect(self.reject)
        footer.addWidget(box)
        root.addLayout(footer)

    def _build_telegram_tab(self, phone: str, logged_in: bool) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(10)

        self.lbl_phone = QLabel()
        self.lbl_phone.setObjectName("muted")
        phone_text = security.mask_text(phone) if phone else "—"
        self.lbl_phone.setText(phone_text)

        session_status = "✓" if logged_in else "✗"
        self.lbl_session = QLabel()
        self.lbl_session.setObjectName("muted")
        self.lbl_session.setText(session_status)

        lay.addLayout(self._kv(t("settings.account.active"), self.lbl_phone))
        lay.addLayout(self._kv(t("settings.session"), self.lbl_session))

        self.cmb_accounts = QComboBox()
        for acc in self._accounts:
            self.cmb_accounts.addItem(
                str(acc.get("phone") or acc.get("key") or "؟"),
                str(acc.get("key") or ""),
            )
        lay.addLayout(self._row(t("settings.accounts"), self.cmb_accounts))

        row_btns = QHBoxLayout()
        self.btn_remove = QPushButton(t("settings.account.remove"))
        self.btn_remove.setProperty("btnType", "danger")
        set_btn_type(self.btn_remove, "danger")
        self.btn_remove.clicked.connect(self._on_remove_account_clicked)
        self.btn_remove.setEnabled(bool(self.cmb_accounts.count()))
        self.btn_wizard = QPushButton(t("settings.account.add"))
        self.btn_wizard.setProperty("btnType", "primary")
        set_btn_type(self.btn_wizard, "primary")
        self.btn_wizard.clicked.connect(self._on_wizard)
        self.btn_logout = QPushButton(t("settings.account.logout"))
        self.btn_logout.setProperty("btnType", "ghost")
        set_btn_type(self.btn_logout, "ghost")
        self.btn_logout.clicked.connect(self._on_logout_clicked)
        self.btn_logout.setEnabled(logged_in)
        row_btns.addWidget(self.btn_wizard)
        row_btns.addWidget(self.btn_remove)
        row_btns.addWidget(self.btn_logout)
        lay.addLayout(row_btns)
        lay.addSpacing(6)

        self.chk_proxy = QCheckBox(t("settings.proxy.enable"))
        self.chk_proxy.setChecked(self._settings.proxy_enabled)
        self.chk_proxy.toggled.connect(self._on_proxy_toggled)
        lay.addWidget(self.chk_proxy)

        self.cmb_proxy_type = QComboBox()
        for lab, val in (("SOCKS5", "socks5"), ("HTTP", "http"), ("MTProto", "mtproto")):
            self.cmb_proxy_type.addItem(lab, val)
        idx = self.cmb_proxy_type.findData(self._settings.proxy_type)
        self.cmb_proxy_type.setCurrentIndex(max(0, idx))
        lay.addLayout(self._row(t("settings.proxy.type"), self.cmb_proxy_type))

        self.txt_proxy_host = QLineEdit(self._settings.proxy_host)
        self.txt_proxy_host.setPlaceholderText("127.0.0.1")
        lay.addLayout(self._row(t("settings.proxy.host"), self.txt_proxy_host))

        self.spin_proxy_port = QSpinBox()
        self.spin_proxy_port.setRange(1, 65535)
        self.spin_proxy_port.setValue(int(self._settings.proxy_port or 1080))
        lay.addLayout(self._row(t("settings.proxy.port"), self.spin_proxy_port))

        self.txt_proxy_user = QLineEdit(self._settings.proxy_username)
        lay.addLayout(self._row(t("settings.proxy.user"), self.txt_proxy_user))

        self.txt_proxy_pass = QLineEdit(self._settings.proxy_password)
        self.txt_proxy_pass.setEchoMode(QLineEdit.EchoMode.Password)
        lay.addLayout(self._row(t("settings.proxy.pass"), self.txt_proxy_pass))

        self.txt_proxy_secret = QLineEdit(self._settings.proxy_secret)
        self.txt_proxy_secret.setPlaceholderText("MTProto")
        lay.addLayout(self._row(t("settings.proxy.secret"), self.txt_proxy_secret))

        self._on_proxy_toggled(self._settings.proxy_enabled)
        lay.addStretch(1)
        return page

    def _build_downloads_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(10)

        self.txt_folder = QLineEdit(self._settings.download_folder)
        btn_browse = QPushButton(t("folder.browse"))
        btn_browse.setProperty("btnType", "ghost")
        set_btn_type(btn_browse, "ghost")
        btn_browse.clicked.connect(self._on_browse)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.txt_folder, 1)
        folder_row.addWidget(btn_browse)
        lay.addLayout(self._row(t("settings.section.folder"), None, folder_row))

        self.cmb_concurrent = QComboBox()
        for i in range(1, 5):
            self.cmb_concurrent.addItem(str(i))
        self.cmb_concurrent.setCurrentIndex(max(0, int(self._settings.concurrent_downloads) - 1))
        lay.addLayout(self._row(t("settings.section.concurrency"), self.cmb_concurrent))

        self.spin_chunk = QSpinBox()
        self.spin_chunk.setRange(64, 16384)
        self.spin_chunk.setSingleStep(256)
        self.spin_chunk.setSuffix(" KB")
        self.spin_chunk.setValue(int(self._settings.download_chunk_kb))
        lay.addLayout(self._row(t("settings.chunk"), self.spin_chunk))

        self.cmb_speed = QComboBox()
        for key, value in _SPEED_PRESETS:
            self.cmb_speed.addItem(t(key), value)
        self._selected_speed = 0
        idx = 0
        for i, (_key, value) in enumerate(_SPEED_PRESETS):
            if value == self._settings.speed_limit_kb:
                idx = i
                break
        else:
            idx = len(_SPEED_PRESETS) - 1
        self.cmb_speed.setCurrentIndex(idx)
        self.cmb_speed.currentIndexChanged.connect(self._on_speed_changed)
        lay.addLayout(self._row(t("settings.speed"), self.cmb_speed))

        self.spin_speed = QSpinBox()
        self.spin_speed.setRange(64, 102400)
        self.spin_speed.setSingleStep(128)
        default_custom = self._settings.speed_limit_kb if self._settings.speed_limit_kb > 0 else 1024
        self.spin_speed.setValue(int(default_custom))
        lay.addLayout(self._row(t("speed.custom"), self.spin_speed))
        self._on_speed_changed(idx)
        lay.addSpacing(4)

        self.chk_auto_resume = QCheckBox(t("settings.resume"))
        self.chk_auto_resume.setChecked(self._settings.auto_resume)
        lay.addWidget(self.chk_auto_resume)
        self.chk_overwrite = QCheckBox(t("settings.overwrite"))
        self.chk_overwrite.setChecked(self._settings.overwrite_existing)
        lay.addWidget(self.chk_overwrite)
        self.chk_skip = QCheckBox(t("settings.skip"))
        self.chk_skip.setChecked(self._settings.skip_existing)
        lay.addWidget(self.chk_skip)
        lay.addSpacing(6)

        self.chk_schedule = QCheckBox(t("settings.schedule.none"))
        self.chk_schedule.setChecked(self._settings.schedule_enabled)
        self.chk_schedule.toggled.connect(self._on_schedule_toggled)
        lay.addWidget(self.chk_schedule)
        row_sched = QHBoxLayout()
        self.time_start = QTimeEdit(self._to_qtime(self._settings.schedule_start))
        self.time_start.setDisplayFormat("HH:mm")
        self.time_stop = QTimeEdit(self._to_qtime(self._settings.schedule_stop))
        self.time_stop.setDisplayFormat("HH:mm")
        row_sched.addWidget(self._make_lab(t("settings.schedule.start")))
        row_sched.addWidget(self.time_start)
        row_sched.addWidget(self._make_lab(t("settings.schedule.stop")))
        row_sched.addWidget(self.time_stop)
        row_sched.addStretch(1)
        lay.addLayout(row_sched)
        self._on_schedule_toggled(self._settings.schedule_enabled)

        lay.addStretch(1)
        return page

    def _build_appearance_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(10)

        self.cmb_theme = QComboBox()
        self.cmb_theme.addItem(t("theme.system"), "system")
        self.cmb_theme.addItem(t("theme.dark"), "dark")
        self.cmb_theme.addItem(t("theme.light"), "light")
        idx = self.cmb_theme.findData(self._settings.theme)
        self.cmb_theme.setCurrentIndex(max(0, idx))
        lay.addLayout(self._row(t("settings.theme"), self.cmb_theme))

        self.cmb_language = QComboBox()
        self.cmb_language.addItem("فارسی", "fa")
        self.cmb_language.addItem("English", "en")
        idx = self.cmb_language.findData(self._settings.language)
        self.cmb_language.setCurrentIndex(max(0, idx))
        lay.addLayout(self._row(t("settings.language"), self.cmb_language))

        self.spin_font = QSpinBox()
        self.spin_font.setRange(10, 20)
        self.spin_font.setValue(int(self._settings.font_size))
        lay.addLayout(self._row(t("settings.font"), self.spin_font))

        self.chk_rtl = QCheckBox(t("settings.rtl"))
        self.chk_rtl.setChecked(self._settings.rtl)
        lay.addWidget(self.chk_rtl)

        self.chk_notify = QCheckBox(t("settings.notify"))
        self.chk_notify.setChecked(self._settings.notify_on_complete)
        lay.addWidget(self.chk_notify)

        self.chk_private = QCheckBox(t("settings.private"))
        self.chk_private.setChecked(getattr(self._settings, "private_mode", False))
        lay.addWidget(self.chk_private)
        from config.features import enabled as _feature_enabled

        if not _feature_enabled("ENABLE_PRIVACY"):
            self.chk_private.setEnabled(False)
            lay.addWidget(self._note(t("settings.feature_off")))

        note = self._note(f"{t('app.title')} — v{APP_VERSION}")
        lay.addWidget(note)
        lay.addStretch(1)
        return page

    def _build_operations_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(10)

        self.cmb_after = QComboBox()
        for key, value in _ACTIONS:
            self.cmb_after.addItem(t(key), value)
        idx = self.cmb_after.findData(self._settings.after_all_done)
        self.cmb_after.setCurrentIndex(max(0, idx))
        lay.addLayout(self._row(t("settings.after"), self.cmb_after))

        self.chk_after_confirm = QCheckBox(t("settings.after.confirm"))
        self.chk_after_confirm.setChecked(self._settings.confirm_before_shutdown)
        lay.addWidget(self.chk_after_confirm)

        self.chk_after_success = QCheckBox(t("settings.after.success"))
        self.chk_after_success.setChecked(self._settings.success_only_action)
        lay.addWidget(self.chk_after_success)

        self.spin_delay = QSpinBox()
        self.spin_delay.setRange(5, 600)
        self.spin_delay.setValue(int(self._settings.power_delay_seconds))
        self.spin_delay.setSuffix(" s")
        lay.addLayout(self._row(t("settings.after.delay"), self.spin_delay))

        lay.addWidget(self._note(t("settings.after.note")))
        lay.addStretch(1)
        return page

    def _build_tray_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(10)

        self.chk_tray_close = QCheckBox(t("settings.close_to_tray"))
        self.chk_tray_close.setChecked(self._settings.close_to_tray)
        lay.addWidget(self.chk_tray_close)

        self.chk_tray_min = QCheckBox(t("settings.min_to_tray"))
        self.chk_tray_min.setChecked(self._settings.minimize_to_tray)
        lay.addWidget(self.chk_tray_min)

        lay.addWidget(self._note(t("settings.tray.note")))
        lay.addStretch(1)
        return page

    def _build_updates_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(10)

        self.chk_autoupdate = QCheckBox(t("settings.check_updates"))
        self.chk_autoupdate.setChecked(self._settings.auto_check_updates)
        lay.addWidget(self.chk_autoupdate)

        self.txt_update_url = QLineEdit(self._settings.update_url)
        self.txt_update_url.setPlaceholderText("https://example.com/update.json")
        lay.addLayout(self._row(t("settings.update_url"), self.txt_update_url))

        self.btn_check_now = QPushButton(t("settings.check_now"))
        self.btn_check_now.setProperty("btnType", "primary")
        set_btn_type(self.btn_check_now, "primary")
        self.btn_check_now.clicked.connect(self._on_check_now)
        lay.addWidget(self.btn_check_now)

        self.lbl_update = QLabel()
        self.lbl_update.setObjectName("muted")
        self.lbl_update.setWordWrap(True)
        lay.addWidget(self.lbl_update)
        lay.addStretch(1)
        return page

    def _build_storage_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setSpacing(10)

        self.lbl_cache = QLabel(t("settings.cache.empty"))
        self.lbl_cache.setObjectName("muted")
        self.lbl_cache.setWordWrap(True)
        lay.addWidget(self.lbl_cache)
        self._refresh_cache_status()

        self.spin_cache_quota = QDoubleSpinBox()
        self.spin_cache_quota.setRange(0.1, 1000.0)
        self.spin_cache_quota.setDecimals(1)
        self.spin_cache_quota.setSingleStep(0.5)
        self.spin_cache_quota.setSuffix(" GB")
        self.spin_cache_quota.setValue(
            max(0.1, float(getattr(self._settings, "cache_quota_gb", 2.0) or 0.1))
        )
        lay.addLayout(self._row(t("settings.cache.quota"), self.spin_cache_quota))

        self.btn_cache_clean = QPushButton(t("settings.cache.clean"))
        self.btn_cache_clean.setProperty("btnType", "primary")
        set_btn_type(self.btn_cache_clean, "primary")
        self.btn_cache_clean.clicked.connect(self._on_cache_clean)
        lay.addWidget(self.btn_cache_clean)

        self.lbl_cache_result = QLabel()
        self.lbl_cache_result.setObjectName("muted")
        self.lbl_cache_result.setWordWrap(True)
        lay.addWidget(self.lbl_cache_result)

        import shutil

        try:
            folder = self._settings.download_folder
            free = shutil.disk_usage(folder).free
            self.lbl_free = QLabel(t("settings.cache.free", free=self._fmt(free)))
        except OSError:
            self.lbl_free = QLabel(t("settings.cache.free", free="—"))
        self.lbl_free.setObjectName("muted")
        lay.addWidget(self.lbl_free)

        lay.addWidget(self._note(t("settings.cache.note")))
        lay.addStretch(1)
        return page

    def _refresh_cache_status(self) -> None:
        try:
            from core.cache_manager import CacheManager
            from utils.format_utils import format_size, to_fa

            manager = CacheManager(
                self._settings.download_folder,
                quota_bytes=int(float(getattr(self._settings, "cache_quota_gb", 2.0) or 0.0) * 1024**3),
            )
            status = manager.status()
            count = int(status.get("count") or 0)
            total = int(status.get("total") or 0)
            if count:
                self.lbl_cache.setText(
                    t("settings.cache.status", count=to_fa(count), total=format_size(total))
                )
            else:
                self.lbl_cache.setText(t("settings.cache.empty"))
        except Exception:
            self.lbl_cache.setText(t("settings.cache.empty"))

    @staticmethod
    def _fmt(size: int) -> str:
        from utils.format_utils import format_size

        return format_size(int(size))

    def _on_cache_clean(self) -> None:
        from core.cache_manager import CacheManager

        quota_gb = float(self.spin_cache_quota.value())
        manager = CacheManager(
            self._settings.download_folder, quota_bytes=int(quota_gb * 1024**3)
        )
        status = manager.status()
        count = int(status.get("count") or 0)
        if count == 0:
            self.lbl_cache_result.setText(t("settings.cache.clean_none"))
            return
        if self._service is not None:
            result = self._service.cache_cleanup(force_quota_gb=quota_gb)
        else:
            result = manager.cleanup(
                quota_bytes=int(quota_gb * 1024**3),
                is_active=lambda _p: False,
            )
        deleted = int(result.get("deleted") or 0)
        freed = int(result.get("freed") or 0)
        if deleted:
            self.lbl_cache_result.setText(
                t("settings.cache.clean_done", count=self._fmt_str(deleted), freed=self._fmt(freed))
            )
        else:
            self.lbl_cache_result.setText(t("settings.cache.clean_busy"))

    @staticmethod
    def _fmt_str(value: int) -> str:
        from utils.format_utils import to_fa

        return to_fa(value)

    # ------------------------------------------------------------------ helpers
    def _on_speed_changed(self, _index: int) -> None:
        value = int(self.cmb_speed.currentData() or 0)
        self.spin_speed.setVisible(value == -1)

    def _on_schedule_toggled(self, enabled: bool) -> None:
        self.time_start.setEnabled(enabled)
        self.time_stop.setEnabled(enabled)

    def _make_lab(self, text: str) -> QLabel:
        lab = QLabel(text)
        lab.setObjectName("muted")
        return lab

    @staticmethod
    def _to_qtime(value: str) -> QTime:
        parts = str(value).split(":")
        try:
            return QTime(int(parts[0]), int(parts[1]), 0, 0)
        except (ValueError, IndexError):
            return QTime(9, 0, 0, 0)

    def _on_proxy_toggled(self, enabled: bool) -> None:
        for widget in (
            self.cmb_proxy_type,
            self.txt_proxy_host,
            self.spin_proxy_port,
            self.txt_proxy_user,
            self.txt_proxy_pass,
            self.txt_proxy_secret,
        ):
            widget.setEnabled(enabled)

    def _note(self, text: str) -> QLabel:
        lab = QLabel(text)
        lab.setObjectName("muted")
        lab.setWordWrap(True)
        return lab

    def _on_browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, t("folder.browse"), self.txt_folder.text())
        if folder:
            self.txt_folder.setText(folder)

    def _on_wizard(self) -> None:
        if self._on_rerun_wizard:
            self._on_rerun_wizard()

    def _on_remove_account_clicked(self) -> None:
        key = str(self.cmb_accounts.currentData() or "")
        if not key or self._on_remove_account is None:
            return
        ans = QMessageBox.question(
            self,
            t("settings.account.remove"),
            t("settings.account.remove.confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans == QMessageBox.StandardButton.Yes:
            self._on_remove_account(key)
            self.cmb_accounts.removeItem(self.cmb_accounts.currentIndex())
            self.btn_remove.setEnabled(bool(self.cmb_accounts.count()))

    def _on_logout_clicked(self) -> None:
        if self._on_logout:
            self._on_logout()
            self.lbl_session.setText("✗")
            self.btn_logout.setEnabled(False)

    def _on_check_now(self) -> None:
        url = self.txt_update_url.text().strip()
        if not url:
            self.lbl_update.setText(t("settings.update_url") + f" ({t('settings.empty')})")
            return
        self.lbl_update.setText("...")
        ok, info = check_latest(url)
        if not ok:
            self.lbl_update.setText(t("update.err", error=info.get("error", "")))
            return
        version = str(info.get("version", ""))
        if is_newer(APP_VERSION, version):
            self.lbl_update.setText(t("update.found", version=version))
        else:
            self.lbl_update.setText(t("update.none"))

    def _open_about(self) -> None:
        AboutDialog.run(self)

    def _export_payload(self) -> dict:
        data = self._settings.to_dict()
        data.pop("proxy_password", None)
        data.pop("proxy_secret", None)
        return data

    def _on_export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, t("settings.export"), "telegram-downloader-settings.json", "*.json")
        if not path:
            return
        try:
            payload = self._export_payload()
            Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            self._toast_status(t("settings.exported", path=path), good=True)
        except OSError as exc:
            self._toast_status(str(exc), good=False)

    def _on_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, t("settings.import"), "", "*.json")
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            imported = Settings.from_dict(data)
        except (OSError, ValueError) as exc:
            self._toast_status(t("settings.import_err", error=str(exc)), good=False)
            return
        self._settings.download_folder = imported.download_folder
        self._settings.concurrent_downloads = imported.concurrent_downloads
        self._settings.download_chunk_kb = imported.download_chunk_kb
        self._settings.theme = imported.theme
        self._settings.language = imported.language
        self._settings.speed_limit_kb = imported.speed_limit_kb
        self._settings.after_all_done = imported.after_all_done
        self.saved.emit(self._settings)
        self._toast_status(t("settings.imported"), good=True)
        self.accept()

    def _toast_status(self, message: str, good: bool) -> None:
        self.lbl_status.setText(message)
        self.lbl_status.setProperty("state", "good" if good else "bad")
        self.lbl_status.style().unpolish(self.lbl_status)
        self.lbl_status.style().polish(self.lbl_status)
        self.lbl_status.show()

    # ------------------------------------------------------------------ save
    def _on_save(self) -> None:
        folder = self.txt_folder.text().strip()
        if not folder:
            self._toast_status(t("settings.folder_empty"), good=False)
            return
        s = self._settings
        s.download_folder = folder
        s.concurrent_downloads = int(self.cmb_concurrent.currentText())
        s.download_chunk_kb = int(self.spin_chunk.value())
        selected_speed = int(self.cmb_speed.currentData() or 0)
        s.speed_limit_kb = int(self.spin_speed.value()) if selected_speed == -1 else selected_speed
        s.auto_resume = self.chk_auto_resume.isChecked()
        s.overwrite_existing = self.chk_overwrite.isChecked()
        s.skip_existing = self.chk_skip.isChecked()

        s.schedule_enabled = self.chk_schedule.isChecked()
        s.schedule_start = self.time_start.time().toString("HH:mm")
        s.schedule_stop = self.time_stop.time().toString("HH:mm")

        s.theme = str(self.cmb_theme.currentData() or "dark")
        s.language = str(self.cmb_language.currentData() or "fa")
        s.font_size = int(self.spin_font.value())
        s.rtl = self.chk_rtl.isChecked()
        s.notify_on_complete = self.chk_notify.isChecked()
        from config.features import enabled as _feature_enabled

        s.private_mode = self.chk_private.isChecked() and _feature_enabled("ENABLE_PRIVACY")

        s.after_all_done = str(self.cmb_after.currentData() or "none")
        s.confirm_before_shutdown = self.chk_after_confirm.isChecked()
        s.success_only_action = self.chk_after_success.isChecked()
        s.power_delay_seconds = int(self.spin_delay.value())

        s.close_to_tray = self.chk_tray_close.isChecked()
        s.minimize_to_tray = self.chk_tray_min.isChecked()

        s.auto_check_updates = self.chk_autoupdate.isChecked()
        s.update_url = self.txt_update_url.text().strip()

        s.cache_quota_gb = float(self.spin_cache_quota.value())

        s.proxy_enabled = self.chk_proxy.isChecked() and bool(self.txt_proxy_host.text().strip())
        s.proxy_type = str(self.cmb_proxy_type.currentData() or "socks5")
        s.proxy_host = self.txt_proxy_host.text().strip()
        s.proxy_port = int(self.spin_proxy_port.value())
        s.proxy_username = self.txt_proxy_user.text().strip()
        s.proxy_password = self.txt_proxy_pass.text()
        s.proxy_secret = self.txt_proxy_secret.text().strip()

        self.saved.emit(s)
        self.accept()

    @staticmethod
    def _row(label_text: str, widget: QWidget | None, custom_layout=None) -> QHBoxLayout:
        row = QHBoxLayout()
        if label_text:
            lab = QLabel(label_text)
            lab.setObjectName("muted")
            lab.setMinimumWidth(190)
            row.addWidget(lab)
        if custom_layout is not None:
            row.addLayout(custom_layout)
        elif widget is not None:
            row.addWidget(widget, 1)
        return row

    @staticmethod
    def _kv(key: str, value_widget: QWidget) -> QHBoxLayout:
        return SettingsWindow._row(key, value_widget)