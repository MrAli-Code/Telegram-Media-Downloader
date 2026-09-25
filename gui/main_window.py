"""پنجره اصلی برنامه با رابط کاربری فارسی RTL؛ داشبورد، صف، Tray و عملیات پس از اتمام."""

from __future__ import annotations

import logging
import os

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QDragEnterEvent, QDropEvent, QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from config.settings import Settings
from config.version import APP_VERSION
from gui.about_dialog import AboutDialog
from gui.components import EmptyState
from gui.download_widget import DownloadCard
from gui.duplicate_dialog import DuplicateDialog
from gui.history_window import HistoryWindow
from gui.settings_window import SettingsWindow
from gui.widgets import Toast, set_btn_type
from utils.format_utils import format_size, format_speed, to_fa
from utils.i18n import set_language as set_i18n_language
from utils.i18n import t
from config.features import enabled as feature_enabled

logger = logging.getLogger(__name__)

ACTION_ITEMS = [
    ("action.none", "none"),
    ("action.exit", "exit"),
    ("action.shutdown", "shutdown"),
    ("action.restart", "restart"),
    ("action.sleep", "sleep"),
    ("action.hibernate", "hibernate"),
]

NAV_ITEMS = [
    ("گ.1", "nav.dashboard", "dashboard"),
    ("گ.2", "nav.downloads", "downloads"),
    ("گ.3", "nav.files", "files", "ENABLE_FILE_MANAGER"),
    ("گ.4", "nav.drives", "drives", "ENABLE_MULTI_DRIVE"),
]


class MainWindow(QMainWindow):
    """پنجره اصلی: افزودن لینک، صف دانلود، کارت‌های پیشرفت، داشبورد و Tray."""

    def __init__(self, service, settings: Settings, parent: QWidget | None = None):
        super().__init__(parent)
        self._service = service
        self._settings = settings
        self._cards: dict[str, DownloadCard] = {}
        self._tray: QSystemTrayIcon | None = None
        self._last_clipboard = ""
        self._force_quit = False

        self.setWindowTitle(t("app.title"))
        self.resize(980, 720)
        self.setAcceptDrops(True)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        self._lay = QVBoxLayout(root)
        self._lay.setContentsMargins(18, 14, 18, 10)
        self._lay.setSpacing(10)

        self._build_header()
        self._build_add_row()
        self._ensure_incomplete_banner()
        self._build_clipboard_hint()
        self._build_download_bar()
        self._build_navigation()
        self._build_statusbar()
        self._build_footer()

        self._toast = Toast(self)
        self._stream_server = None
        if feature_enabled("ENABLE_STREAMING"):
            from core.stream_server import StreamRangeServer

            self._stream_server = StreamRangeServer()
        self._connect_service()

        self._clipboard_timer = QTimer(self)
        self._clipboard_timer.setInterval(1200)
        self._clipboard_timer.timeout.connect(self._poll_clipboard)
        self._clipboard_timer.start()

        self._dash_timer = QTimer(self)
        self._dash_timer.setInterval(1000)
        self._dash_timer.timeout.connect(self._refresh_dashboard)
        self._dash_timer.start()

        self._install_shortcuts()

        QTimer.singleShot(1200, self._startup_checks)

    def _install_shortcuts(self) -> None:
        """میانبرهای سراسری: جستجو، افزودن مستقیم و غیره."""
        from PySide6.QtGui import QKeySequence, QShortcut

        search = QShortcut(QKeySequence("Ctrl+F"), self)
        search.activated.connect(self._on_shortcut_search)
        paste_queue = QShortcut(QKeySequence("Ctrl+Shift+V"), self)
        paste_queue.activated.connect(self._on_paste_to_queue)
        add_now = QShortcut(QKeySequence("Ctrl+Enter"), self)
        add_now.activated.connect(self._on_add_current)

    def _startup_checks(self) -> None:
        incomplete = self._service.index.find_incomplete_local()
        self._on_index_changed()
        if incomplete:
            self._on_toast(t("meta.resume"), t("meta.incomplete", count=to_fa(len(incomplete))))

    def _on_shortcut_search(self) -> None:
        from gui.search_dialog import SearchEverywhereDialog

        SearchEverywhereDialog.run(self._service, self)

    def _on_paste_to_queue(self) -> None:
        from PySide6.QtGui import QGuiApplication

        text = QGuiApplication.clipboard().text().strip()
        if not text:
            return
        if self._service.add_link(text):
            self._on_toast(t("add.queued"), "")

    def _on_add_current(self) -> None:
        self._on_add()

    # ------------------------------------------------------------------ build
    def _build_header(self) -> None:
        header = QHBoxLayout()
        left = QVBoxLayout()
        self.lbl_title = QLabel(t("app.title"))
        self.lbl_title.setObjectName("title")
        self.lbl_subtitle = QLabel(t("app.subtitle"))
        self.lbl_subtitle.setObjectName("subtitle")
        left.addWidget(self.lbl_title)
        left.addWidget(self.lbl_subtitle)
        header.addLayout(left)
        header.addStretch(1)

        self.lbl_version = QLabel(f"v{APP_VERSION}")
        self.lbl_version.setObjectName("muted")
        header.addWidget(self.lbl_version)

        self.lbl_account = QLabel()
        self.lbl_account.setObjectName("muted")

        self.cmb_account = QComboBox()
        self.cmb_account.setFixedWidth(190)
        self.cmb_account.currentIndexChanged.connect(self._on_account_combo_changed)
        self.cmb_account.setCursor(Qt.CursorShape.PointingHandCursor)
        header.addWidget(self.cmb_account)
        header.addWidget(self.lbl_account)

        self.btn_history = QPushButton(t("history.button"))
        self.btn_history.setProperty("btnType", "ghost")
        set_btn_type(self.btn_history, "ghost")
        self.btn_history.clicked.connect(self._open_history)
        header.addWidget(self.btn_history)

        self.btn_about = QPushButton(t("about.button"))
        self.btn_about.setProperty("btnType", "ghost")
        set_btn_type(self.btn_about, "ghost")
        self.btn_about.clicked.connect(self._open_about)
        header.addWidget(self.btn_about)

        self.btn_manage = QPushButton(t("settings.button"))
        self.btn_manage.setProperty("btnType", "ghost")
        set_btn_type(self.btn_manage, "ghost")
        self.btn_manage.clicked.connect(self._open_settings)
        header.addWidget(self.btn_manage)
        self._lay.addLayout(header)

    def _build_add_row(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(8)
        self.edt_link = QLineEdit()
        self.edt_link.setPlaceholderText(t("add.placeholder"))
        self.edt_link.returnPressed.connect(self._on_add)
        row.addWidget(self.edt_link, 1)

        self.btn_paste = QPushButton(t("add.paste"))
        self.btn_paste.setProperty("btnType", "ghost")
        set_btn_type(self.btn_paste, "ghost")
        self.btn_paste.clicked.connect(self._on_paste)
        row.addWidget(self.btn_paste)

        self.btn_clear = QPushButton(t("add.clear"))
        self.btn_clear.setProperty("btnType", "ghost")
        set_btn_type(self.btn_clear, "ghost")
        self.btn_clear.clicked.connect(self._on_clear)
        row.addWidget(self.btn_clear)

        self.btn_add = QPushButton(t("add.queue"))
        self.btn_add.setProperty("btnType", "primary")
        set_btn_type(self.btn_add, "primary")
        self.btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add.clicked.connect(self._on_add)
        row.addWidget(self.btn_add)
        self._lay.addLayout(row)

    def _ensure_incomplete_banner(self) -> None:
        """نوار اطلاع‌رسانی دانلودهای ناقص در راه‌اندازی."""
        self._incomplete_count = 0
        self._incomplete_banner = QWidget()
        self._incomplete_banner.setProperty("class", "incomplete-banner")
        bar = QHBoxLayout(self._incomplete_banner)
        bar.setContentsMargins(12, 8, 12, 8)
        bar.setSpacing(10)

        self.lbl_incomplete = QLabel()
        self.lbl_incomplete.setWordWrap(True)
        bar.addWidget(self.lbl_incomplete, 1)

        self.btn_incomplete_continue = QPushButton(t("incomplete.continue"))
        set_btn_type(self.btn_incomplete_continue, "ghost")
        self.btn_incomplete_continue.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_incomplete_continue.clicked.connect(self._on_incomplete_continue)
        bar.addWidget(self.btn_incomplete_continue)

        self.btn_incomplete_view = QPushButton(t("incomplete.view"))
        set_btn_type(self.btn_incomplete_view, "ghost")
        self.btn_incomplete_view.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_incomplete_view.clicked.connect(self._on_incomplete_view)
        bar.addWidget(self.btn_incomplete_view)

        self.btn_incomplete_close = QPushButton(t("incomplete.close"))
        set_btn_type(self.btn_incomplete_close, "ghost")
        self.btn_incomplete_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_incomplete_close.clicked.connect(lambda: self._incomplete_banner.hide())
        bar.addWidget(self.btn_incomplete_close)

        self._incomplete_banner.hide()
        self._lay.insertWidget(2, self._incomplete_banner)

    def _on_incomplete_restored(self, count: int) -> None:
        self._incomplete_count = count
        if count <= 0:
            self._incomplete_banner.hide()
            return
        self.lbl_incomplete.setText(t("incomplete.banner", count=to_fa(count)))
        self._incomplete_banner.show()

    def _on_incomplete_continue(self) -> None:
        self._service.resume_all_items()
        self._incomplete_banner.hide()

    def _on_incomplete_view(self) -> None:
        for index, nav_id in getattr(self, "_nav_map", {}).items():
            if nav_id == "downloads":
                self._switch_page(index)
                break

    def _build_clipboard_hint(self) -> None:
        hint = QHBoxLayout()
        self.lbl_clip_hint = QLabel(t("clipboard.found"))
        self.lbl_clip_hint.setObjectName("muted")
        hint.addWidget(self.lbl_clip_hint)
        hint.addStretch(1)
        self.btn_clip_paste = QPushButton(t("clipboard.paste"))
        self.btn_clip_paste.setProperty("btnType", "success")
        set_btn_type(self.btn_clip_paste, "success")
        self.btn_clip_paste.clicked.connect(self._on_paste)
        hint.addWidget(self.btn_clip_paste)
        hint_widget = QWidget()
        hint_widget.setLayout(hint)
        self._clip_hint_widget = hint_widget
        self._clip_hint_widget.hide()
        self._lay.addWidget(hint_widget)

    def _build_download_bar(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(8)
        self.lbl_folder_label = QLabel(t("folder.label"))
        self.lbl_folder_label.setObjectName("muted")
        self.lbl_folder = QLabel()
        self.lbl_folder.setObjectName("pathLabel")
        self.lbl_folder.setToolTip(self._settings.download_folder)
        self.lbl_folder.setText(self._short_path(self._settings.download_folder))
        row.addWidget(self.lbl_folder_label)
        row.addWidget(self.lbl_folder, 1)

        self.btn_browse = QPushButton(t("folder.browse"))
        self.btn_browse.setProperty("btnType", "ghost")
        set_btn_type(self.btn_browse, "ghost")
        self.btn_browse.clicked.connect(self._on_browse_folder)
        row.addWidget(self.btn_browse)

        self.lbl_concurrent = QLabel(t("concurrent.label"))
        self.lbl_concurrent.setObjectName("muted")
        self.cmb_concurrent = QComboBox()
        for i in range(1, 5):
            self.cmb_concurrent.addItem(str(i))
        self.cmb_concurrent.setCurrentIndex(max(0, int(self._settings.concurrent_downloads) - 1))
        self.cmb_concurrent.setFixedWidth(60)
        self.cmb_concurrent.currentIndexChanged.connect(self._on_concurrency_changed)
        row.addWidget(self.lbl_concurrent)
        row.addWidget(self.cmb_concurrent)

        self.lbl_after = QLabel(t("after.title"))
        self.lbl_after.setObjectName("muted")
        self.cmb_after = QComboBox()
        for key, value in ACTION_ITEMS:
            self.cmb_after.addItem(t(key), value)
        idx = self.cmb_after.findData(self._settings.after_all_done)
        self.cmb_after.setCurrentIndex(max(0, idx))
        self.cmb_after.setFixedWidth(170)
        self.cmb_after.currentIndexChanged.connect(self._on_after_changed)
        row.addWidget(self.lbl_after)
        row.addWidget(self.cmb_after)
        self._lay.addLayout(row)

    @staticmethod
    def _short_path(path: str, limit: int = 46) -> str:
        if len(path) <= limit:
            return path
        return "…" + path[-(limit - 1) :]

    def _on_after_changed(self, _index: int) -> None:
        self._settings.after_all_done = str(self.cmb_after.currentData() or "none")
        self._service.apply_settings(self._settings)

    def _on_browse_folder(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        folder = QFileDialog.getExistingDirectory(self, t("folder.label"), self._settings.download_folder)
        if folder:
            self._settings.download_folder = folder
            self.lbl_folder.setText(self._short_path(folder))
            self.lbl_folder.setToolTip(folder)
            self._service.apply_settings(self._settings)

    def _on_concurrency_changed(self, _index: int) -> None:
        self._settings.concurrent_downloads = int(self.cmb_concurrent.currentText())
        self._service.apply_settings(self._settings)

    def _build_queue_area(self) -> None:
        """صفحه دانلود (صفحه ۰): صف آیتم‌ها و کارت‌ها."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._queue_container = QWidget()
        self._queue_layout = QVBoxLayout(self._queue_container)
        self._queue_layout.setContentsMargins(2, 2, 2, 2)
        self._queue_layout.setSpacing(10)
        self._queue_layout.addStretch(1)

        self._empty_state = EmptyState(
            "\U0001f4e6",
            t("empty.queue_title", default=""),
            t("empty.queue_hint", default=""),
            t("add.queue", default=""),
        )
        self._empty_state.btn_action.clicked.connect(lambda: self.edt_link.setFocus())
        self.lbl_empty = self._empty_state.lbl_title
        self._queue_layout.insertWidget(0, self._empty_state)

        scroll.setWidget(self._queue_container)
        self._download_page = scroll

    def _build_navigation(self) -> None:
        """سایدبار ناوبری و صفحه‌های داشبورد/فایل منیجر/فضاها."""
        from PySide6.QtWidgets import QButtonGroup, QStackedWidget

        from gui.dashboard_widget import DashboardWidget
        from gui.drive_manager_page import DriveManagerPage
        from gui.file_manager_page import FileManagerPage

        self._build_queue_area()
        sidebar = QWidget()
        sidebar.setFixedWidth(180)
        side_lay = QVBoxLayout(sidebar)
        side_lay.setContentsMargins(0, 4, 10, 4)
        side_lay.setSpacing(4)

        self._stack = QStackedWidget()
        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        self._nav_map: dict[int, str] = {}
        self._nav_buttons: list[tuple[QPushButton, str]] = []

        def add_page(page: QWidget, nav_id: str, label_key: str) -> None:
            index = self._stack.addWidget(page)
            self._nav_map[index] = nav_id
            btn = QPushButton(t(label_key))
            btn.setProperty("nav", "true")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, i=index: self._switch_page(i))
            self._nav_group.addButton(btn)
            side_lay.insertWidget(side_lay.count(), btn)
            self._nav_buttons.append((btn, label_key))
            if nav_id == "dashboard":
                self._dashboard_page = page
            if nav_id == "files":
                self._files_page = page
            if nav_id == "drives":
                self._drives_page = page

        add_page(DashboardWidget(self._service), "dashboard", "nav.dashboard")
        add_page(self._download_page, "downloads", "nav.downloads")
        if feature_enabled("ENABLE_FILE_MANAGER"):
            files_page = FileManagerPage(self._service, self._settings)
            files_page.toastRequested.connect(self._on_page_toast)
            add_page(files_page, "files", "nav.files")
        if feature_enabled("ENABLE_MULTI_DRIVE"):
            drives_page = DriveManagerPage(self._service)
            drives_page.toastRequested.connect(self._on_page_toast)
            add_page(drives_page, "drives", "nav.drives")

        side_lay.addStretch(1)
        row = QHBoxLayout()
        row.addWidget(sidebar)
        row.addWidget(self._stack, 1)
        self._lay.addLayout(row, 1)
        self._switch_page(0)

    def _switch_page(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        buttons = list(self._nav_group.buttons())
        if index < len(buttons):
            button = buttons[index]
            button.setChecked(True)
        page = self._stack.currentWidget()
        refresh = getattr(page, "refresh", None)
        if callable(refresh):
            refresh()

    def _build_statusbar(self) -> None:
        bar = QHBoxLayout()
        self.lbl_stats = QLabel()
        self.lbl_stats.setObjectName("muted")
        self.lbl_stats.setText("—")
        bar.addWidget(self.lbl_stats)

        self.lbl_speed = QLabel()
        self.lbl_speed.setObjectName("muted")
        self.lbl_speed.setText("")
        bar.addWidget(self.lbl_speed)

        self.lbl_size = QLabel()
        self.lbl_size.setObjectName("muted")
        self.lbl_size.setText("")
        bar.addWidget(self.lbl_size)

        bar.addStretch(1)

        self.btn_pause_all = QPushButton(t("pause_all"))
        self.btn_pause_all.setProperty("btnType", "ghost")
        set_btn_type(self.btn_pause_all, "ghost")
        self.btn_pause_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pause_all.clicked.connect(self._service.pause_all_items)
        self.btn_pause_all.setEnabled(False)
        bar.addWidget(self.btn_pause_all)

        self.btn_resume_all = QPushButton(t("resume_all"))
        self.btn_resume_all.setProperty("btnType", "ghost")
        set_btn_type(self.btn_resume_all, "ghost")
        self.btn_resume_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_resume_all.clicked.connect(self._service.resume_all_items)
        self.btn_resume_all.setEnabled(False)
        bar.addWidget(self.btn_resume_all)

        self.lbl_countdown = QLabel()
        self.lbl_countdown.setObjectName("warn")
        self.lbl_countdown.setStyleSheet("color: #f3b743; font-weight: 600;")
        self.lbl_countdown.hide()
        bar.addWidget(self.lbl_countdown)

        self.btn_cancel_countdown = QPushButton(t("after.done.cancel"))
        self.btn_cancel_countdown.setProperty("btnType", "ghost")
        set_btn_type(self.btn_cancel_countdown, "ghost")
        self.btn_cancel_countdown.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel_countdown.clicked.connect(self._service.cancel_after_action)
        self.btn_cancel_countdown.hide()
        bar.addWidget(self.btn_cancel_countdown)

        self.lbl_conn = QLabel()
        self.lbl_conn.setObjectName("muted")
        bar.addWidget(self.lbl_conn)
        self._lay.addLayout(bar)

    def _build_footer(self) -> None:
        """فوتر برند: نام توسعه‌دهنده و وب‌سایت در همه صفحات (بند ۹)."""
        from gui.components import DeveloperFooter

        self._footer = DeveloperFooter(self)
        self._footer.setToolTip(t("branding.site_tooltip"))
        self._lay.addWidget(self._footer)

    # ------------------------------------------------------------------ service wiring
    def _connect_service(self) -> None:
        s = self._service
        s.item_added.connect(self._on_item_added)
        s.item_updated.connect(self._on_item_updated)
        s.item_removed.connect(self._on_item_removed)
        s.auth_changed.connect(self._on_auth_changed)
        s.login_event.connect(self._on_login_event)
        s.toast.connect(self._on_toast)
        s.connection_changed.connect(self._on_connection_changed)
        s.accounts_changed.connect(self._on_accounts_changed)
        s.stats_changed.connect(self._on_stats_changed)
        s.after_done_countdown.connect(self._on_after_countdown)
        s.confirm_required.connect(self._on_confirm_required)
        s.after_done_finished.connect(self._on_after_finished)
        s.request_exit.connect(self._quit_app)
        # --- فایل منیجر / فضاها
        s.index_changed.connect(self._on_index_changed)
        s.sync_progress.connect(self._on_sync_progress)
        s.sync_finished.connect(self._on_sync_finished)
        s.duplicates_found.connect(self._on_duplicates)
        s.incomplete_restored.connect(self._on_incomplete_restored)

    def _on_index_changed(self) -> None:
        for page in (getattr(self, "_files_page", None), getattr(self, "_drives_page", None)):
            if page is not None:
                page._reload()
        dashboard = getattr(self, "_dashboard_page", None)
        if dashboard is not None:
            dashboard.refresh()

    def _on_duplicates(self, groups: object, file_id: str = "") -> None:
        try:
            group_list = list(groups)
        except TypeError:
            group_list = list(groups or []) if groups else []
        if not group_list:
            return
        if not feature_enabled("ENABLE_DEDUPE"):
            count = sum((g.get("n") or 0) - 1 for g in group_list if isinstance(g, dict))
            self._on_toast(t("duplicates.title"), t("duplicates.text", count=to_fa(count)))
            return
        choice = DuplicateDialog.run(self, group_list)
        if choice:
            message = self._service.apply_duplicate_choice(str(file_id), choice)
            if message:
                self._on_toast(t("duplicates.title"), message)

    def _on_sync_progress(self, drive_id: str, stats: dict) -> None:
        page = getattr(self, "_drives_page", None)
        if page is not None:
            page.on_sync_progress(drive_id, stats)

    def _on_sync_finished(self, drive_id: str, status: str, stats: dict) -> None:
        page = getattr(self, "_drives_page", None)
        if page is not None:
            page.on_sync_finished(drive_id, status, stats)
        self._refresh_dashboard()
        if status == "ok":
            self._on_toast(t("dm.status.ok"), "")

    # ------------------------------------------------------------------ slots
    def _on_item_added(self, snap: dict) -> None:
        card = DownloadCard(snap)
        card.pauseClicked.connect(self._service.pause_item)
        card.resumeClicked.connect(self._service.resume_item)
        card.cancelClicked.connect(self._on_cancel)
        card.removeClicked.connect(self._on_remove)
        card.retryClicked.connect(self._service.retry_item)
        card.openFolderClicked.connect(self._on_open_folder)
        card.moveToFrontClicked.connect(self._service.move_to_front)
        card.priorityClicked.connect(self._service.set_priority)
        card.streamClicked.connect(self._on_stream_item)
        self._cards[card.item_id] = card
        self._queue_layout.insertWidget(self._queue_layout.count() - 1, card)
        self._empty_state.hide()
        self._refresh_dashboard()

    def _on_item_updated(self, snap: dict) -> None:
        card = self._cards.get(str(snap.get("id", "")))
        if card is not None:
            card.set_data(snap)
        if snap.get("status") == "completed":
            self._notify_completed(snap)
        self._refresh_dashboard()

    def _on_item_removed(self, item_id: str) -> None:
        card = self._cards.pop(item_id, None)
        if card is not None:
            card.deleteLater()
        if not self._cards:
            self._empty_state.show()
        self._refresh_dashboard()

    def _on_auth_changed(self, phone: str) -> None:
        if phone:
            self.lbl_account.setText(t("account.label", phone=phone))
            self.lbl_account.setToolTip("✓")
        else:
            self.lbl_account.setText(t("account.not_logged"))
        self._refresh_dashboard()

    def _on_accounts_changed(self, accounts) -> None:
        active = self._service.active_account()
        items = list(accounts) if isinstance(accounts, list) else []
        self.cmb_account.blockSignals(True)
        self.cmb_account.clear()
        for account in items:
            label = str(account.get("phone") or account.get("key") or "؟")
            self.cmb_account.addItem(label, str(account.get("key") or ""))
        self.cmb_account.addItem("＋ " + t("account.add"), "")
        if active:
            idx = self.cmb_account.findData(active)
        else:
            idx = self.cmb_account.count() - 1
        self.cmb_account.setCurrentIndex(max(0, idx))
        self.cmb_account.blockSignals(False)

    def _on_account_combo_changed(self, index: int) -> None:
        key = self.cmb_account.itemData(index)
        if key:
            if key != self._service.active_account():
                self._service.set_active_account(str(key))
        else:
            self._open_add_account()
            self._refresh_account_selection()

    def _open_add_account(self) -> None:
        from gui.setup_wizard import SetupWizard

        SetupWizard.run(self._service, self)

    def _refresh_account_selection(self) -> None:
        active = self._service.active_account()
        idx = self.cmb_account.findData(active)
        self.cmb_account.blockSignals(True)
        self.cmb_account.setCurrentIndex(max(0, idx))
        self.cmb_account.blockSignals(False)

    def _on_login_event(self, kind: str, payload) -> None:
        if kind == "authorized":
            self._on_toast(t("login.ok"), "")

    def _on_connection_changed(self, connected: bool) -> None:
        self.lbl_conn.setText(t("conn.online") if connected else t("conn.offline"))
        self.lbl_conn.setProperty("conn", "ok" if connected else "bad")
        self.lbl_conn.style().unpolish(self.lbl_conn)
        self.lbl_conn.style().polish(self.lbl_conn)

    def _on_toast(self, title: str, message: str) -> None:
        text = f"{title}: {message}" if message else title
        self._toast.show_toast(text)
        self._notify_os(title, message)

    def _on_page_toast(self, message: str) -> None:
        """پیام‌های تک‌آرگومانی صفحه‌ها (فایل/فضا) به‌صورت Toast نمایش داده می‌شوند."""
        self._toast.show_toast(message)

    def _on_stats_changed(self, _stats: dict) -> None:
        self._update_queue_action_buttons()
        self._refresh_dashboard()

    def _update_queue_action_buttons(self) -> None:
        can_pause, can_resume = self._service.queue_action_states()
        self.btn_pause_all.setEnabled(can_pause)
        self.btn_resume_all.setEnabled(can_resume)

    def _on_after_countdown(self, seconds: int) -> None:
        if seconds < 0:
            self.lbl_countdown.hide()
            self.btn_cancel_countdown.hide()
            return
        action = self._settings.after_all_done
        self.lbl_countdown.setText(
            t("after.done.message", nl=" ", action=t(f"action.{action}"), seconds=to_fa(seconds))
        )
        self.lbl_countdown.show()
        self.btn_cancel_countdown.show()

    def _on_confirm_required(self, payload: dict) -> None:
        title = str(payload.get("title", t("power.confirm.title")))
        text = str(payload.get("text", ""))
        ans = QMessageBox.question(
            self,
            title,
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        self._service.confirm_result(ans == QMessageBox.StandardButton.Yes)

    def _on_after_finished(self, action: str, ok: bool, message: str) -> None:
        if not ok:
            self._toast.show_toast(t("power.error.body", action=t(f"action.{action}"), error=message))

    # ------------------------------------------------------------------ actions
    def _on_add(self) -> None:
        text = self.edt_link.text().strip()
        if not text:
            self.edt_link.setFocus()
            return
        if not self._service.add_link(text):
            return
        self.edt_link.clear()
        self.edt_link.setFocus()

    def _on_paste(self) -> None:
        from PySide6.QtGui import QGuiApplication

        clipboard = QGuiApplication.clipboard()
        text = clipboard.text().strip()
        if text:
            self.edt_link.setText(text)
            self.edt_link.selectAll()
            self.edt_link.setFocus()

    def _on_clear(self) -> None:
        self.edt_link.clear()
        self.edt_link.setFocus()

    def _on_cancel(self, item_id: str) -> None:
        self._service.cancel_item(item_id)

    def _on_remove(self, item_id: str) -> None:
        self._service.remove_item(item_id)

    def _on_open_folder(self, item_id: str) -> None:
        status, final_path, dest_dir = self._service.resolve_item_path(item_id)
        target = final_path if status == "completed" and final_path else dest_dir or ""
        if target:
            QDesktopServices.openUrl(QUrl.fromLocalFile(target))

    def _on_stream_item(self, part_path: str) -> None:
        if not part_path or not os.path.exists(part_path):
            self._on_toast(t("stream.needs_part"), "")
            return
        from gui.preview_dialog import PreviewDialog, guess_media_kind

        server = self._stream_server
        url = server.url_for(part_path)
        box = PreviewDialog(None, kind=guess_media_kind(part_path), stream_url=url, parent=self)
        box.show()
        box.exec()

    def _open_history(self) -> None:
        HistoryWindow.run(self._service, self)

    def _open_about(self) -> None:
        AboutDialog.run(self)

    def _open_settings(self) -> None:
        dialog = SettingsWindow(
            self._settings,
            self._settings_phone(),
            logged_in=bool(self._settings_phone()),
            on_rerun_wizard=self._rerun_wizard,
            on_logout=self._service.logout,
            accounts=self._service.list_accounts(),
            on_remove_account=self._remove_account,
            service=self._service,
            parent=self,
        )
        dialog.saved.connect(self._on_settings_saved)
        dialog.exec()

    def _settings_phone(self) -> str:
        return getattr(self._service, "_phone", "") or ""

    def _rerun_wizard(self) -> None:
        from gui.setup_wizard import SetupWizard

        if SetupWizard.run(self._service, self):
            self._on_auth_changed(self._settings_phone())

    def _remove_account(self, key: str) -> None:
        self._service.remove_account(key)

    def _on_settings_saved(self, settings: Settings) -> None:
        self._set_settings(settings)
        self._service.apply_settings(settings)

    def _set_settings(self, settings: Settings) -> None:
        from typing import cast

        from PySide6.QtCore import Qt as _Qt

        from PySide6.QtWidgets import QApplication

        raw_app = QApplication.instance()
        if raw_app is None:
            return
        app = cast(QApplication, raw_app)
        from gui import theme as theme_mod

        family = theme_mod.pick_font(app)
        app.setStyleSheet(theme_mod.build_qss(settings.theme, family, settings.font_size))
        theme_mod.set_font(app, family, settings.font_size)
        self._settings = settings
        self.cmb_concurrent.setCurrentIndex(max(0, int(settings.concurrent_downloads) - 1))
        self.lbl_folder.setText(self._short_path(settings.download_folder))
        self.lbl_folder.setToolTip(settings.download_folder)
        idx = self.cmb_after.findData(settings.after_all_done)
        self.cmb_after.setCurrentIndex(max(0, idx))
        set_i18n_language(settings.language)
        app.setLayoutDirection(
            _Qt.LayoutDirection.RightToLeft if settings.rtl else _Qt.LayoutDirection.LeftToRight
        )
        self._retranslate()

    def _retranslate(self) -> None:
        """بروزرسانی برچسب‌های قابل مشاهده پس از تغییر زبان/چیدمان."""
        self.setWindowTitle(t("app.title"))
        self.lbl_title.setText(t("app.title"))
        self.lbl_subtitle.setText(t("app.subtitle"))
        self.btn_history.setText(t("history.button"))
        self.btn_about.setText(t("about.button"))
        self.btn_manage.setText(t("settings.button"))
        self.edt_link.setPlaceholderText(t("add.placeholder"))
        self.btn_paste.setText(t("add.paste"))
        self.btn_clear.setText(t("add.clear"))
        self.btn_add.setText(t("add.queue"))
        self.lbl_clip_hint.setText(t("clipboard.found"))
        self.btn_clip_paste.setText(t("clipboard.paste"))
        self.lbl_folder_label.setText(t("folder.label"))
        self.btn_browse.setText(t("folder.browse"))
        self.lbl_concurrent.setText(t("concurrent.label"))
        self.lbl_after.setText(t("after.title"))
        self.btn_pause_all.setText(t("pause_all"))
        self.btn_resume_all.setText(t("resume_all"))
        self.btn_cancel_countdown.setText(t("after.done.cancel"))
        self._empty_state.set_texts(
            t("empty.queue_title", default=""),
            t("empty.queue_hint", default=""),
        )
        btn_continue = getattr(self, "btn_incomplete_continue", None)
        if btn_continue is not None:
            btn_continue.setText(t("incomplete.continue"))
            getattr(self, "btn_incomplete_view").setText(t("incomplete.view"))
            getattr(self, "btn_incomplete_close").setText(t("incomplete.close"))
            if self._incomplete_banner.isVisible():
                self.lbl_incomplete.setText(t("incomplete.banner", count=to_fa(self._incomplete_count)))
        for btn, label_key in self._nav_buttons:
            btn.setText(t(label_key))
        current = self.cmb_after.currentData()
        self.cmb_after.blockSignals(True)
        self.cmb_after.clear()
        for key, value in ACTION_ITEMS:
            self.cmb_after.addItem(t(key), value)
        idx = self.cmb_after.findData(current)
        self.cmb_after.setCurrentIndex(max(0, idx))
        self.cmb_after.blockSignals(False)
        phone = self._settings_phone()
        if phone:
            self.lbl_account.setText(t("account.label", phone=phone))
        for page in (
            getattr(self, "_dashboard_page", None),
            getattr(self, "_files_page", None),
            getattr(self, "_drives_page", None),
        ):
            if page is not None and hasattr(page, "retranslate"):
                page.retranslate()
        for card in self._cards.values():
            if hasattr(card, "retranslate"):
                card.retranslate()

    # ------------------------------------------------------------------ clipboard
    def _poll_clipboard(self) -> None:
        from PySide6.QtGui import QGuiApplication

        clipboard = QGuiApplication.clipboard()
        text = (clipboard.text() or "").strip()
        if text == self._last_clipboard:
            return
        self._last_clipboard = text
        from utils.link_utils import is_valid_message_link

        valid = len(text) <= 500 and is_valid_message_link(text)
        self._clip_hint_widget.setVisible(bool(valid))

    # ------------------------------------------------------------------ dashboard
    def _refresh_dashboard(self) -> None:
        stats = self._service.stats()
        active = int(stats.get("active") or 0)
        pending = int(stats.get("pending") or 0)
        completed = int(stats.get("completed_count") or 0)
        failed = int(stats.get("failed_count") or 0)
        speed = float(stats.get("speed") or 0.0)
        size_total = int(stats.get("size_total") or 0)

        self.lbl_stats.setText(
            f"{t('dash.active')}: {to_fa(active)} · {t('dash.queued')}: {to_fa(pending)} · "
            f"{t('dash.completed')}: {to_fa(completed)} · {t('dash.failed')}: {to_fa(failed)}"
        )
        self.lbl_speed.setText(f"{t('dash.speed')}: {format_speed(speed)}" if speed > 0 else "")
        self.lbl_size.setText(f"{t('dash.total')}: {format_size(size_total)}")

    # ------------------------------------------------------------------ notifications
    def _notify_completed(self, snap: dict) -> None:
        if self._settings.notify_on_complete:
            name = str(snap.get("file_name", ""))
            if self._settings.private_mode:
                from utils.security import mask_text

                name = mask_text(name, show=1)
            self._notify_os(t("download.finished", name=name), "")

    def _notify_os(self, title: str, message: str) -> None:
        if self._tray is not None and self._tray.isVisible():
            self._tray.showMessage(title, message or title, QSystemTrayIcon.MessageIcon.Information, 4000)

    # ------------------------------------------------------------------ icon / tray
    def set_app_icon(self, icon: QIcon) -> None:
        self.setWindowIcon(icon)

    def set_tray_icon(self, icon: QIcon) -> None:
        import sys

        if sys.platform != "win32":
            return
        from PySide6.QtWidgets import QMenu

        tray = QSystemTrayIcon(icon, self)
        tray.setToolTip(t("app.title"))
        menu = QMenu(self)
        menu.addAction(t("tray.show"), self.show_and_raise)
        menu.addAction(t("tray.pause_all"), self._service.pause_all_items)
        menu.addAction(t("tray.resume_all"), self._service.resume_all_items)
        menu.addAction(t("tray.open_folder"), self._open_download_folder)
        menu.addAction(t("tray.settings"), self._open_settings)
        menu.addSeparator()
        menu.addAction(t("tray.quit"), self._quit_from_tray)
        tray.setContextMenu(menu)
        tray.activated.connect(self._on_tray_activated)
        tray.show()
        self._tray = tray

    def _open_download_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(self._settings.download_folder))

    def _on_tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show_and_raise()

    def show_and_raise(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _quit_from_tray(self) -> None:
        if self._confirm_exit_if_running():
            self._quit_app()

    def show_notification(self, title: str, message: str) -> None:
        self._on_toast(title, message)

    # ------------------------------------------------------------------ close / minimize behavior
    def changeEvent(self, event) -> None:  # noqa: N802
        if (
            event.type() == event.Type.WindowStateChange
            and self.isMinimized()
            and self._settings.minimize_to_tray
            and self._tray is not None
            and self._service.queue_stats()[0] > 0
        ):
            QTimer.singleShot(0, self._hide_to_tray)
        super().changeEvent(event)

    def _hide_to_tray(self) -> None:
        if self._tray is not None and self.isVisible():
            self.hide()
            self._tray.showMessage(
                t("app.title"),
                t("tray.hidden"),
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._force_quit:
            event.accept()
            return
        if self._settings.close_to_tray and self._tray is not None:
            event.ignore()
            self._hide_to_tray()
            return
        if self._tray is not None:
            event.ignore()
            self._ask_close_to_tray()
            return
        if not self._confirm_exit_if_running():
            event.ignore()
            return
        event.accept()

    def _ask_close_to_tray(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(t("dialog.close.tray.title"))
        dialog.setMinimumWidth(420)
        lay = QVBoxLayout(dialog)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(14)
        lbl = QLabel(t("dialog.close.tray.text"))
        lbl.setWordWrap(True)
        lay.addWidget(lbl)
        chk = QCheckBox(t("dialog.close.tray.always"))
        chk.setChecked(self._settings.close_to_tray)
        lay.addWidget(chk)
        box = QDialogButtonBox()
        btn_tray = box.addButton(t("dialog.close.tray.to_tray"), QDialogButtonBox.ButtonRole.AcceptRole)
        btn_tray.setProperty("btnType", "primary")
        set_btn_type(btn_tray, "primary")
        btn_quit = box.addButton(t("dialog.close.tray.quit"), QDialogButtonBox.ButtonRole.RejectRole)
        btn_quit.setProperty("btnType", "ghost")
        set_btn_type(btn_quit, "ghost")
        lay.addWidget(box)

        def on_tray() -> None:
            self._settings.close_to_tray = chk.isChecked()
            self._service.apply_settings(self._settings)
            dialog.accept()
            self._hide_to_tray()

        def on_quit() -> None:
            self._settings.close_to_tray = chk.isChecked()
            self._service.apply_settings(self._settings)
            dialog.reject()
            if self._confirm_exit_if_running():
                self._force_quit = True
                self.close()

        btn_tray.clicked.connect(on_tray)
        btn_quit.clicked.connect(on_quit)
        dialog.exec()

    def _confirm_exit_if_running(self) -> bool:
        active = self._service.queue_stats()[0]
        if active > 0:
            ans = QMessageBox.question(
                self,
                t("app.close_confirm.title"),
                t("app.close_confirm.text"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            return ans == QMessageBox.StandardButton.Yes
        return True

    def _quit_app(self) -> None:
        self._force_quit = True
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.quit()

    # ------------------------------------------------------------------ drag & drop
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        from utils.link_utils import is_valid_message_link

        text = event.mimeData().text()
        for line in text.splitlines():
            line = line.strip()
            if line and is_valid_message_link(line):
                self._service.add_link(line)
        event.acceptProposedAction()