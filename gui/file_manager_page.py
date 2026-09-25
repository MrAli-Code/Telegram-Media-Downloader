"""صفحه مدیریت فایل‌های Telegram: اکسپلورر، جستجو، پوشه‌ها، دلخواه و زباله.

داده‌ها مستقیماً از ایندکس محلی (SQLite) خوانده می‌شود تا در حالت آفلاین هم
اعمال مدیریت فایل در دسترس باشند؛ فقط دانلود/باز کردن به اتصال نیاز دارد.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.index_store import DL_DOWNLOADED, DL_REMOTE
from gui.components import status_foreground
from gui.widgets import set_btn_type
from utils.format_utils import format_size, to_fa
from utils.i18n import t

logger = logging.getLogger(__name__)

PAGE_SIZE = 500

KIND_LABELS = {
    "video": "fm.kind.video",
    "video_note": "fm.kind.video_note",
    "audio": "fm.kind.audio",
    "voice": "fm.kind.voice",
    "photo": "fm.kind.photo",
    "document": "fm.kind.document",
    "archive": "fm.kind.archive",
    "sticker": "fm.kind.sticker",
}

STATUS_LABELS = {
    "remote": "fm.status.remote",
    "queued": "fm.status.queued",
    "downloading": "fm.status.downloading",
    "partial": "fm.status.partial",
    "downloaded": "fm.status.downloaded",
    "error": "fm.status.error",
    "skipped": "fm.status.skipped",
}

FILTERS = [
    ("all", "fm.filter.all"),
    ("downloaded", "fm.filter.downloaded"),
    ("pending", "fm.filter.pending"),
    ("favorite", "fm.filter.favorite"),
    ("trash", "fm.filter.trash"),
]

SORT_KEYS = [
    ("name", "fm.sort.name"),
    ("size", "fm.sort.size"),
    ("date", "fm.sort.date"),
    ("type", "fm.sort.type"),
]


class FileManagerPage(QWidget):
    """نمایش و مدیریت فایل‌های ایندکس‌شده با انتخاب چندگانه."""

    toastRequested = Signal(str)

    def __init__(self, service, settings=None, parent: QWidget | None = None):
        super().__init__(parent)
        self._service = service
        self._settings = settings or getattr(service, "_settings", None)
        self._drives = service.drives
        self._index = service.index
        self._page = 1
        self._rows: dict[int, str] = {}  # row -> file_id
        self._build_ui()
        self._apply_view()
        self._reload()

    # ------------------------------------------------------------------ ui
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        head = QHBoxLayout()
        title = QLabel(t("fm.title"))
        title.setObjectName("title")
        head.addWidget(title)
        head.addStretch(1)
        root.addLayout(head)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.edt_search = QLineEdit()
        self.edt_search.setPlaceholderText(t("fm.search"))
        self.edt_search.setClearButtonEnabled(True)
        self.edt_search.textChanged.connect(self._on_search)
        toolbar.addWidget(self.edt_search, 1)

        self.cmb_filter = QComboBox()
        for key, label in FILTERS:
            self.cmb_filter.addItem(t(label), key)
        self.cmb_filter.currentIndexChanged.connect(self._reload)
        toolbar.addWidget(self.cmb_filter)

        self.cmb_drive = QComboBox()
        self.cmb_drive.currentIndexChanged.connect(self._reload)
        toolbar.addWidget(self.cmb_drive)

        self.cmb_folder = QComboBox()
        self.cmb_folder.currentIndexChanged.connect(self._reload)
        toolbar.addWidget(self.cmb_folder)

        self.cmb_sort = QComboBox()
        for key, label in SORT_KEYS:
            self.cmb_sort.addItem(t(label), key)
        self.cmb_sort.setCurrentIndex(0)
        self.cmb_sort.currentIndexChanged.connect(self._reload)
        toolbar.addWidget(self.cmb_sort)

        self.btn_sort_dir = QPushButton()
        self.btn_sort_dir.setFixedWidth(40)
        self.btn_sort_dir.clicked.connect(self._toggle_sort_dir)
        self.btn_sort_dir.setEnabled(False)
        toolbar.addWidget(self.btn_sort_dir)

        self.btn_refresh = QPushButton(t("fm.refresh"))
        self.btn_refresh.setProperty("btnType", "ghost")
        set_btn_type(self.btn_refresh, "ghost")
        self.btn_refresh.clicked.connect(self._reload)
        toolbar.addWidget(self.btn_refresh)

        self.btn_view = QPushButton()
        self.btn_view.setProperty("btnType", "ghost")
        set_btn_type(self.btn_view, "ghost")
        self.btn_view.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_view.clicked.connect(self._toggle_view)
        toolbar.addWidget(self.btn_view)
        root.addLayout(toolbar)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.btn_download = QPushButton(t("fm.download_selected"))
        self.btn_download.setProperty("btnType", "primary")
        set_btn_type(self.btn_download, "primary")
        self.btn_download.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_download.clicked.connect(self._download_selected)
        actions.addWidget(self.btn_download)

        from config.features import enabled as feature_enabled

        if feature_enabled("ENABLE_PREVIEW"):
            self.btn_preview = QPushButton(t("fm.preview"))
            self.btn_preview.setProperty("btnType", "ghost")
            set_btn_type(self.btn_preview, "ghost")
            self.btn_preview.clicked.connect(self._preview_selected)
            actions.addWidget(self.btn_preview)
        else:
            self.btn_preview = None

        self.btn_fav = QPushButton(t("fm.favorite"))
        self.btn_fav.setProperty("btnType", "ghost")
        set_btn_type(self.btn_fav, "ghost")
        self.btn_fav.clicked.connect(self._toggle_favorite)
        actions.addWidget(self.btn_fav)

        self.btn_move = QPushButton(t("fm.move_folder"))
        self.btn_move.setProperty("btnType", "ghost")
        set_btn_type(self.btn_move, "ghost")
        self.btn_move.clicked.connect(self._move_selected)
        actions.addWidget(self.btn_move)

        self.btn_trash = QPushButton(t("fm.trash"))
        self.btn_trash.setProperty("btnType", "ghost")
        set_btn_type(self.btn_trash, "ghost")
        self.btn_trash.clicked.connect(self._trash_selected)
        actions.addWidget(self.btn_trash)

        self.btn_restore = QPushButton(t("fm.restore"))
        self.btn_restore.setProperty("btnType", "ghost")
        set_btn_type(self.btn_restore, "ghost")
        self.btn_restore.clicked.connect(self._restore_selected)
        actions.addWidget(self.btn_restore)

        self.btn_new_folder = QPushButton(t("fm.new_folder"))
        self.btn_new_folder.setProperty("btnType", "ghost")
        set_btn_type(self.btn_new_folder, "ghost")
        self.btn_new_folder.clicked.connect(self._create_folder)
        actions.addWidget(self.btn_new_folder)

        self.btn_verify = QPushButton(t("fm.verify"))
        self.btn_verify.setProperty("btnType", "ghost")
        set_btn_type(self.btn_verify, "ghost")
        self.btn_verify.clicked.connect(self._verify_selected)
        actions.addWidget(self.btn_verify)

        actions.addStretch(1)
        self.lbl_selected = QLabel()
        self.lbl_selected.setObjectName("muted")
        actions.addWidget(self.lbl_selected)
        root.addLayout(actions)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            [t("fm.col.name"), t("fm.col.kind"), t("fm.col.size"), t("fm.col.date"), t("fm.col.status")]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._update_selection_label)
        self.table.cellDoubleClicked.connect(self._on_double_click)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        root.addWidget(self.table, 1)

        page_actions = QHBoxLayout()
        self.btn_prev = QPushButton(t("fm.prev"))
        self.btn_prev.setProperty("btnType", "ghost")
        set_btn_type(self.btn_prev, "ghost")
        self.btn_prev.clicked.connect(self._prev_page)
        self.btn_next = QPushButton(t("fm.next"))
        self.btn_next.setProperty("btnType", "ghost")
        set_btn_type(self.btn_next, "ghost")
        self.btn_next.clicked.connect(self._next_page)
        self.lbl_page = QLabel()
        self.lbl_page.setObjectName("muted")
        page_actions.addWidget(self.btn_prev)
        page_actions.addWidget(self.lbl_page)
        page_actions.addWidget(self.btn_next)
        page_actions.addStretch(1)
        self.lbl_total = QLabel()
        self.lbl_total.setObjectName("muted")
        page_actions.addWidget(self.lbl_total)
        root.addLayout(page_actions)

    # ------------------------------------------------------------------ data
    @property
    def _current_filter(self) -> str:
        return str(self.cmb_filter.currentData() or "all")

    def _selected_drive_id(self) -> str:
        return str(self.cmb_drive.currentData() or "")

    def _query(self, limit: int, offset: int) -> tuple[list[dict], int]:
        query = self.edt_search.text().strip()
        drive_id = self._selected_drive_id()
        folder_id = self._selected_folder_id()
        current = self._current_filter
        if current == "trash" or current == "favorite":
            if query:
                rows = self._index.search(
                    query,
                    drive_id=drive_id,
                    include_trash=current == "trash",
                    limit=10000,
                )
                rows = [r for r in rows if (int(r.get("trashed") or 0) == 1)] if current == "trash" else [
                    r for r in rows if int(r.get("favorite") or 0) == 1 and not int(r.get("trashed") or 0)
                ]
                return rows[offset : offset + limit], len(rows)
            if current == "trash":
                rows = self._drives.trash(drive_id or None)
            else:
                rows = self._drives.favorites(drive_id or None)
            return rows[offset : offset + limit], len(rows)

        statuses = {"downloaded": [DL_DOWNLOADED], "pending": [DL_REMOTE]}.get(current)
        if query:
            rows = self._index.search(
                query,
                drive_id=drive_id,
                folder_id=folder_id or None,
                include_trash=False,
                limit=10**6,
                offset=0,
            )
            if statuses:
                rows = [r for r in rows if r.get("download_status") in statuses]
            sort_key = {"size": "size", "name": "name", "date": "date"}.get(
                str(self.cmb_sort.currentData() or "name"), "name"
            )
            rows.sort(key=lambda r: self._sort_value(r, sort_key), reverse=not self._ascending())
            return rows[offset : offset + limit], len(rows)

        sort_key = str(self.cmb_sort.currentData() or "name")
        sort_map = {"name": "name", "size": "size", "date": "date", "type": "type"}
        rows = self._index.list_files(
            drive_id=drive_id or None,
            folder_id=folder_id or None,
            statuses=statuses,
            include_trash=False,
            sort=sort_map.get(sort_key, "name"),
            ascending=self._ascending(),
            limit=limit,
            offset=offset,
        )
        total = self._index.count_files(
            drive_id=drive_id or None,
            folder_id=folder_id or None,
            statuses=statuses,
            include_trash=False,
        )
        return rows, total

    @staticmethod
    def _sort_value(row: dict, key: str):
        if key == "size":
            return int(row.get("file_size") or 0)
        if key == "date":
            return float(row.get("message_date") or 0)
        if key == "type":
            return str(row.get("media_type") or row.get("file_ext") or "")
        return str(row.get("file_name") or "").lower()

    def _ascending(self) -> bool:
        return self.btn_sort_dir.text() != "↓"

    def _selected_folder_id(self) -> str:
        data = self.cmb_folder.currentData()
        if data is None:
            return ""
        return str(data)

    def _reload(self, *_args) -> None:
        self._page = 1
        self._refresh_combo_data()
        self._load_rows()

    def _refresh_combo_data(self) -> None:
        try:
            drives = self._index.list_drives()
        except Exception:
            drives = []
        self.cmb_drive.blockSignals(True)
        current = str(self.cmb_drive.currentData() or "")
        self.cmb_drive.clear()
        self.cmb_drive.addItem(t("fm.all_drives"), "")
        drive_names: dict[str, str] = {"": ""}
        for drive in drives:
            drive_names[str(drive.get("id", ""))] = str(drive.get("name") or "؟")
            self.cmb_drive.addItem(str(drive.get("name") or "؟"), str(drive.get("id", "")))
        idx = self.cmb_drive.findData(current)
        self.cmb_drive.setCurrentIndex(max(0, idx))
        self.cmb_drive.blockSignals(False)

        self.cmb_folder.blockSignals(True)
        self.cmb_folder.clear()
        self.cmb_folder.addItem(t("fm.folder.all"), None)
        try:
            folders = self._index.list_folders(drive_id=self._selected_drive_id() or None)
        except Exception:
            folders = []
        for folder in folders:
            prefix = drive_names.get(str(folder.get("drive_id", "")), "")
            label = f"{prefix} / {folder.get('name', '؟')}" if prefix else str(folder.get("name", "؟"))
            self.cmb_folder.addItem(label, str(folder.get("id", "")))
        self.cmb_folder.blockSignals(False)

        if not self.btn_sort_dir.isEnabled():
            self.btn_sort_dir.setEnabled(True)
            self.btn_sort_dir.setText("↓" if str(self.cmb_sort.currentData() or "") == "date" else "→")

    def _toggle_sort_dir(self) -> None:
        self.btn_sort_dir.setText("↓" if self.btn_sort_dir.text() == "↑" else "↑")
        self._reload()

    def _compact(self) -> bool:
        return bool(getattr(self._settings, "fm_compact", False))

    def _private(self) -> bool:
        return bool(getattr(self._settings, "private_mode", False))

    def _theme(self) -> str:
        """نام تم جاری برای رنگ‌های یکدست جدول."""
        return str(getattr(self._settings, "theme", "dark") or "dark")

    def _toggle_view(self) -> None:
        if self._settings is not None:
            self._settings.fm_compact = not self._compact()
        self._apply_view()
        self._reload()

    def _apply_view(self) -> None:
        compact = self._compact()
        self.btn_view.setText(t("fm.view_full") if compact else t("fm.view"))
        height = 26 if compact else 46
        for i in range(self.table.rowCount()):
            self.table.setRowHeight(i, height)
        self.table.verticalHeader().setDefaultSectionSize(height)
        self.table.setColumnHidden(1, compact)
        self.table.setColumnHidden(3, compact)

    def _display_name(self, rec: dict) -> str:
        name = str(rec.get("file_name") or rec.get("file_id") or "نامشخص")
        if self._private():
            from utils.security import mask_text

            return mask_text(name, show=1)
        return name

    def _load_rows(self) -> None:
        offset = (self._page - 1) * PAGE_SIZE
        try:
            rows, total = self._query(PAGE_SIZE, offset)
        except Exception as exc:
            logger.exception("بارگذاری فایل‌ها ناموفق بود")
            self.toastRequested.emit(t("fm.load_error", error=str(exc)))
            rows, total = [], 0
        self._rows = {}
        self.table.setRowCount(0)
        self.table.setRowCount(len(rows))
        for row, rec in enumerate(rows):
            self._rows[row] = str(rec.get("id", ""))
            self._fill_row(row, rec)
        pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        self.lbl_page.setText(f"{t('fm.page', page=to_fa(self._page))} / {to_fa(pages)}")
        self.btn_prev.setEnabled(self._page > 1)
        self.btn_next.setEnabled(self._page < pages)
        self.lbl_total.setText(t("fm.count", count=to_fa(total)))
        self._apply_view()
        self._update_selection_label()

    def _fill_row(self, row: int, rec: dict) -> None:
        name = self._display_name(rec)
        kind_key = KIND_LABELS.get(str(rec.get("media_type", "")) or "", "—")
        kind = t(kind_key) if kind_key != "—" else str(rec.get("media_type", "")) or "—"
        size = format_size(int(rec.get("file_size") or 0))
        ts = float(rec.get("message_date") or 0)
        date_text = to_fa(datetime.fromtimestamp(ts).strftime("%Y/%m/%d")) if ts else "—"
        status_key = str(rec.get("download_status") or DL_REMOTE)
        status_text = t(STATUS_LABELS.get(status_key, status_key))
        if int(rec.get("favorite") or 0):
            status_text += " · ★"
        if int(rec.get("archived") or 0):
            status_text += f" · {t('fm.badge.archived')}"
        if int(rec.get("hidden") or 0):
            status_text += f" · {t('fm.badge.hidden')}"

        name_item = QTableWidgetItem(name)
        name_item.setData(Qt.ItemDataRole.UserRole, str(rec.get("id", "")))
        kind_item = QTableWidgetItem(kind)
        size_item = QTableWidgetItem(size)
        size_item.setData(Qt.ItemDataRole.UserRole, int(rec.get("file_size") or 0))
        date_item = QTableWidgetItem(date_text)
        date_item.setData(Qt.ItemDataRole.UserRole, float(ts))
        status_item = QTableWidgetItem(status_text)
        status_item.setData(Qt.ItemDataRole.UserRole, status_key)
        status_item.setForeground(status_foreground(status_key, self._theme()))

        for col, item in enumerate((name_item, kind_item, size_item, date_item, status_item)):
            self.table.setItem(row, col, item)

    # ------------------------------------------------------------------ selection
    def _selected_ids(self) -> list[str]:
        ids = []
        for index in self.table.selectionModel().selectedRows():
            row = index.row()
            row_id = self._rows.get(row)
            if row_id:
                ids.append(row_id)
        return ids

    def _update_selection_label(self) -> None:
        count = len(self._selected_ids())
        self.lbl_selected.setText(t("fm.selected", count=to_fa(count)) if count else "")
        self.btn_download.setEnabled(count > 0)
        self.btn_move.setEnabled(count > 0)
        self.btn_fav.setEnabled(count > 0)
        self.btn_trash.setEnabled(count > 0)
        self.btn_restore.setEnabled(count > 0)
        self.btn_verify.setEnabled(count > 0)
        if self.btn_preview is not None:
            self.btn_preview.setEnabled(count > 0)

    # ------------------------------------------------------------------ actions
    def _download_selected(self) -> None:
        ids = self._selected_ids()
        if not ids:
            return
        links = []
        for file_id in ids:
            rec = self._index.get_file(file_id)
            link = self._drives.link_for_file(rec) if rec else ""
            if link:
                links.append(link)
        added = self._service.add_indexed_files(links) if links else 0
        if added > 0:
            self.toastRequested.emit(t("fm.toast.queued", count=to_fa(added)))
        else:
            self.toastRequested.emit(t("fm.toast.none"))

    def _toggle_favorite(self) -> None:
        ids = self._selected_ids()
        if not ids:
            return
        any_fav = any(int((self._index.get_file(i) or {}).get("favorite") or 0) == 1 for i in ids)
        self._drives.mark(ids, favorite=0 if any_fav else 1)
        self._emit_index_changed(t("fm.toast.fav"))

    def _trash_selected(self) -> None:
        ids = self._selected_ids()
        if not ids:
            return
        self._drives.mark(ids, trashed=1)
        self._emit_index_changed(t("fm.toast.trashed", count=to_fa(len(ids))))

    def _restore_selected(self) -> None:
        ids = self._selected_ids()
        if not ids:
            return
        self._drives.mark(ids, trashed=0)
        self._emit_index_changed(t("fm.toast.restored", count=to_fa(len(ids))))

    def _delete_records(self, ids: list[str]) -> None:
        self._drives.delete_records(ids)
        self._emit_index_changed(t("fm.toast.deleted", count=to_fa(len(ids))))

    def _emit_index_changed(self, toast: str) -> None:
        self.toastRequested.emit(toast)
        self._reload()

    def _move_selected(self) -> None:
        ids = self._selected_ids()
        if not ids:
            return
        from gui.folder_picker import FolderPicker

        drive_id = self._selected_drive_id()
        if not drive_id:
            rec = self._index.get_file(ids[0])
            drive_id = str((rec or {}).get("drive_id", ""))
        dialog = FolderPicker(self._drives, drive_id, self)
        if dialog.exec() == dialog.DialogCode.Accepted:
            folder_id = dialog.selected_folder_id()
            moved = self._drives.move_to_folder(ids, folder_id)
            self.toastRequested.emit(t("fm.move.done", count=to_fa(moved)))
            self._reload()

    def _create_folder(self) -> None:
        drive_id = self._selected_drive_id()
        if not drive_id:
            drives = self._index.list_drives()
            if drives:
                drive_id = str(drives[0].get("id", ""))
            else:
                self.toastRequested.emit(t("fm.need_drive"))
                return
        name, ok = QInputDialog.getText(self, t("fm.folder.new"), t("fm.folder.new"))
        name = name.strip() if ok else ""
        if not name:
            return
        self._drives.create_folder(drive_id, name)
        self._emit_index_changed(t("fm.folder.created"))

    def _verify_selected(self) -> None:
        ids = self._selected_ids()
        if not ids:
            return
        missing = 0
        verified = 0
        for file_id in ids:
            rec = self._index.get_file(file_id)
            path = (rec or {}).get("local_path") or ""
            if path and os.path.exists(path):
                result = self._drives.verify_file(file_id)
                status = (result or {}).get("ok")
                if status:
                    verified += 1
                else:
                    self.toastRequested.emit(t("toast.ver.needed"))
            else:
                missing += 1
        if missing:
            self.toastRequested.emit(t("fm.verify.local_missing", count=to_fa(missing)))
        elif verified:
            self.toastRequested.emit(t("fm.verify.ok"))

    def _rename_selected(self) -> None:
        ids = self._selected_ids()
        if len(ids) != 1:
            self.toastRequested.emit(t("fm.no_selection"))
            return
        rec = self._index.get_file(ids[0])
        old_name = str((rec or {}).get("file_name") or "")
        new_name, ok = QInputDialog.getText(
            self, t("fm.rename.title"), t("fm.rename.prompt"), text=old_name
        )
        new_name = new_name.strip() if ok else ""
        if not new_name or new_name == old_name:
            return
        path = (rec or {}).get("local_path") or ""
        if path and os.path.exists(path):
            new_path = os.path.join(os.path.dirname(path), new_name)
            try:
                os.rename(path, new_path)
            except OSError as exc:
                self.toastRequested.emit(t("fm.rename.error", error=str(exc)))
                return
            self._index.mark_download(ids[0], DL_DOWNLOADED, local_path=new_path)
        self._drives.rename_file(ids[0], new_name)
        self._emit_index_changed(t("fm.rename.done"))

    def _open_selected(self) -> None:
        ids = self._selected_ids()
        if not ids:
            return
        rec = self._index.get_file(ids[0])
        if not rec:
            return
        path = str(rec.get("local_path") or "")
        if path and os.path.exists(path):
            QDesktopServices.openUrl(_local_url(path))
            return
        self._download_selected()

    def _preview_selected(self) -> None:
        ids = self._selected_ids()
        if not ids:
            return
        from gui.preview_dialog import PreviewDialog

        rec = self._index.get_file(ids[0]) or {}
        path = str(rec.get("local_path") or "")
        if path and os.path.exists(path):
            box = PreviewDialog(path, kind="auto", parent=self)
            box.exec()
            return
        self.toastRequested.emit(t("fm.preview.need_download"))

    def _on_double_click(self, row: int, _column: int) -> None:
        file_id = self._rows.get(row)
        if not file_id:
            return
        self.table.clearSelection()
        self.table.selectRow(row)
        self._open_selected()

    def _on_search(self, _text: str) -> None:
        self._page = 1
        self._load_rows()

    # ------------------------------------------------------------------ pagination
    def _prev_page(self) -> None:
        if self._page > 1:
            self._page -= 1
            self._load_rows()

    def _next_page(self) -> None:
        self._page += 1
        self._load_rows()

    # ------------------------------------------------------------------ context menu
    def _show_context_menu(self, pos) -> None:
        menu = QMenu(self)
        current = self._current_filter
        action_download = QAction(t("fm.download_selected"), menu)
        action_download.triggered.connect(self._download_selected)
        menu.addAction(action_download)

        action_open = QAction(t("fm.open"), menu)
        action_open.triggered.connect(self._open_selected)
        menu.addAction(action_open)

        from config.features import enabled as feature_enabled

        if feature_enabled("ENABLE_PREVIEW"):
            action_preview = QAction(t("fm.preview"), menu)
            action_preview.triggered.connect(self._preview_selected)
            menu.addAction(action_preview)

        action_fav = QAction(t("fm.unfavorite" if self._selection_has_favorite() else "fm.favorite"), menu)
        action_fav.triggered.connect(self._toggle_favorite)
        menu.addAction(action_fav)

        action_move = QAction(t("fm.move_folder"), menu)
        action_move.triggered.connect(self._move_selected)
        menu.addAction(action_move)

        action_ver = QAction(t("fm.verify"), menu)
        action_ver.triggered.connect(self._verify_selected)
        menu.addAction(action_ver)

        action_rename = QAction(t("fm.rename.title"), menu)
        action_rename.triggered.connect(self._rename_selected)
        menu.addAction(action_rename)

        menu.addSeparator()
        if current == "trash":
            action_restore = QAction(t("fm.restore"), menu)
            action_restore.triggered.connect(self._restore_selected)
            menu.addAction(action_restore)
            action_delete = QAction(t("fm.delete"), menu)
            action_delete.triggered.connect(self._delete_selected_confirm)
            menu.addAction(action_delete)
        else:
            action_trash = QAction(t("fm.trash"), menu)
            action_trash.triggered.connect(self._trash_selected)
            menu.addAction(action_trash)

        action_copy = QAction(t("fm.copy_link"), menu)
        action_copy.triggered.connect(self._copy_link)
        menu.addAction(action_copy)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _selection_has_favorite(self) -> bool:
        ids = self._selected_ids()
        return any(int((self._index.get_file(i) or {}).get("favorite") or 0) == 1 for i in ids)

    def _delete_selected_confirm(self) -> None:
        ids = self._selected_ids()
        if not ids:
            return
        ans = QMessageBox.question(
            self,
            t("fm.delete"),
            t("fm.toast.deleted", count=to_fa(len(ids))),
        )
        if ans == QMessageBox.StandardButton.Yes:
            self._delete_records(ids)

    def _copy_link(self) -> None:
        from PySide6.QtGui import QGuiApplication

        ids = self._selected_ids()
        if not ids:
            return
        links = []
        for file_id in ids:
            rec = self._index.get_file(file_id)
            link = self._drives.link_for_file(rec) if rec else ""
            if link:
                links.append(link)
        if links:
            QGuiApplication.clipboard().setText("\n".join(links))
            self.toastRequested.emit(t("fm.links_copied"))

    # ------------------------------------------------------------------ refresh
    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._reload()

    def retranslate(self) -> None:
        """بروزرسانی برچسب‌های این صفحه هنگام تغییر زبان."""
        self.btn_download.setText(t("fm.download_selected"))
        self.btn_fav.setText(t("fm.favorite"))
        self.btn_move.setText(t("fm.move_folder"))
        self.btn_trash.setText(t("fm.trash"))
        self.btn_restore.setText(t("fm.restore"))
        self.btn_new_folder.setText(t("fm.new_folder"))
        self.btn_verify.setText(t("fm.verify"))
        if self.btn_preview is not None:
            self.btn_preview.setText(t("fm.preview"))
        self.btn_refresh.setText(t("fm.refresh"))
        self.btn_prev.setText(t("fm.prev"))
        self.btn_next.setText(t("fm.next"))
        self.edt_search.setPlaceholderText(t("fm.search"))
        self.table.setHorizontalHeaderLabels(
            [t("fm.col.name"), t("fm.col.kind"), t("fm.col.size"), t("fm.col.date"), t("fm.col.status")]
        )
        current_filter = self.cmb_filter.currentData()
        self.cmb_filter.blockSignals(True)
        self.cmb_filter.clear()
        for key, label in FILTERS:
            self.cmb_filter.addItem(t(label), key)
        idx = self.cmb_filter.findData(current_filter)
        self.cmb_filter.setCurrentIndex(max(0, idx))
        self.cmb_filter.blockSignals(False)
        current_sort = self.cmb_sort.currentData()
        self.cmb_sort.blockSignals(True)
        self.cmb_sort.clear()
        for key, label in SORT_KEYS:
            self.cmb_sort.addItem(t(label), key)
        idx = self.cmb_sort.findData(current_sort)
        self.cmb_sort.setCurrentIndex(max(0, idx))
        self.cmb_sort.blockSignals(False)
        self._refresh_combo_data()
        self._load_rows()


def _local_url(path: str) -> QUrl:
    return QUrl.fromLocalFile(path)