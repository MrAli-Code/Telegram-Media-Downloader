"""پنجره تاریخچه دانلودها: جستجو، باز کردن فایل/پوشه، حذف و پاک کردن."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from gui.widgets import Toast, set_btn_type
from utils.format_utils import format_size
from utils.i18n import t


class _Model(QStandardItemModel):
    def __init__(self, service):
        super().__init__(0, 7)
        self.setHorizontalHeaderLabels(
            [
                t("history.col.file"),
                t("history.col.date"),
                t("history.col.size"),
                t("history.col.status"),
                t("history.col.source"),
                t("history.col.path"),
                t("history.col.uid"),
            ]
        )
        self._service = service

    def refresh(self, rows: list[dict]) -> None:
        self.removeRows(0, self.rowCount())
        for row in rows:
            file_item = QStandardItem(str(row.get("filename") or ""))
            date_item = QStandardItem(self._format_date(str(row.get("date") or "")))
            size_item = QStandardItem(format_size(int(row.get("size") or 0)))
            status_item = QStandardItem(self._status_text(str(row.get("status") or "")))
            source_item = QStandardItem(str(row.get("source") or ""))
            path_item = QStandardItem(str(row.get("save_path") or ""))
            for it in (size_item,):
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            status_item.setData(str(row.get("status") or ""), Qt.ItemDataRole.UserRole)
            uid_item = QStandardItem(str(row.get("uid") or ""))
            uid_item.setData(str(row.get("uid") or ""), Qt.ItemDataRole.UserRole)
            self.appendRow(
                [file_item, date_item, size_item, status_item, source_item, path_item, uid_item]
            )

    @staticmethod
    def _format_date(value: str) -> str:
        try:
            dt = datetime.fromisoformat(value)
            return dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return value

    @staticmethod
    def _status_text(status: str) -> str:
        return {
            "completed": t("status.completed"),
            "error": t("status.error"),
            "cancelled": t("status.cancelled"),
        }.get(status, status)


class HistoryWindow(QDialog):
    """نمایش تاریخچه با فیلتر جستجو و اقدامات روی هر ردیف."""

    OPEN_FILE = "file"
    OPEN_FOLDER = "folder"

    def __init__(self, service, parent: QWidget | None = None):
        super().__init__(parent)
        self._service = service
        self._rows: list[dict] = []
        self.setWindowTitle(t("history.title"))
        self.resize(920, 560)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        top = QHBoxLayout()
        self.edt_search = QLineEdit()
        self.edt_search.setPlaceholderText(t("history.search"))
        self.edt_search.textChanged.connect(self._on_search)
        top.addWidget(self.edt_search, 1)

        self.btn_open_file = QPushButton(t("history.open_file"))
        self.btn_open_file.setProperty("btnType", "ghost")
        set_btn_type(self.btn_open_file, "ghost")
        self.btn_open_file.clicked.connect(lambda: self._open_selected(self.OPEN_FILE))
        top.addWidget(self.btn_open_file)

        self.btn_open_folder = QPushButton(t("history.open_folder"))
        self.btn_open_folder.setProperty("btnType", "ghost")
        set_btn_type(self.btn_open_folder, "ghost")
        self.btn_open_folder.clicked.connect(lambda: self._open_selected(self.OPEN_FOLDER))
        top.addWidget(self.btn_open_folder)

        self.btn_delete = QPushButton(t("history.delete"))
        self.btn_delete.setProperty("btnType", "danger")
        set_btn_type(self.btn_delete, "danger")
        self.btn_delete.clicked.connect(self._delete_selected)
        top.addWidget(self.btn_delete)

        self.btn_clear = QPushButton(t("history.clear"))
        self.btn_clear.setProperty("btnType", "ghost")
        set_btn_type(self.btn_clear, "ghost")
        self.btn_clear.clicked.connect(self._clear_all)
        top.addWidget(self.btn_clear)

        self.btn_close = QPushButton(t("dialog.close"))
        self.btn_close.setProperty("btnType", "primary")
        set_btn_type(self.btn_close, "primary")
        self.btn_close.clicked.connect(self.accept)
        top.addWidget(self.btn_close)
        root.addLayout(top)

        for btn in (self.btn_open_file, self.btn_open_folder, self.btn_delete):
            btn.setEnabled(False)

        self.model = _Model(service)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnHidden(6, True)
        self.table.selectionModel().selectionChanged.connect(self._update_buttons)
        self.table.doubleClicked.connect(lambda _idx: self._open_selected(self.OPEN_FILE))
        root.addWidget(self.table, 1)

        self.lbl_empty = QLabel(t("history.empty"))
        self.lbl_empty.setObjectName("subtitle")
        self.lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.lbl_empty)

        self._toast = Toast(self)
        self._refresh()

    def _refresh(self) -> None:
        query = self.edt_search.text().strip()
        rows = self._service.history_search(query) if query else self._service.history()
        self._rows = rows
        self.model.refresh(rows)
        have = bool(rows)
        self.table.setVisible(have)
        self.lbl_empty.setVisible(not have)
        self.lbl_empty.setText(t("history.no_match") if query and not have else t("history.empty"))
        self._update_buttons()

    def _update_buttons(self) -> None:
        has_selection = bool(self._selected_uid())
        self.btn_open_file.setEnabled(has_selection)
        self.btn_open_folder.setEnabled(has_selection)
        self.btn_delete.setEnabled(has_selection)

    def _on_search(self, _text: str) -> None:
        self._refresh()

    def _selected_uid(self) -> str | None:
        index = self.table.currentIndex()
        if not index.isValid():
            return None
        return str(self.model.index(index.row(), 6).data(Qt.ItemDataRole.UserRole) or "")

    def _select_row(self) -> dict | None:
        uid = self._selected_uid()
        if not uid:
            return None
        for row in self._rows:
            if str(row.get("uid") or "") == uid:
                return row
        return None

    def _open_selected(self, mode: str) -> None:
        row = self._select_row()
        if not row:
            return
        path = str(row.get("save_path") or "")
        if not path:
            return
        if mode == self.OPEN_FOLDER:
            from pathlib import Path

            path = str(Path(path).parent)
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _delete_selected(self) -> None:
        uid = self._selected_uid()
        if not uid:
            return
        self._service.history_remove(uid)
        self._toast.show_toast(t("history.deleted"))
        self._refresh()

    def _clear_all(self) -> None:
        self._service.history_clear()
        self._toast.show_toast(t("history.cleared"))
        self._refresh()

    @staticmethod
    def run(service, parent: QWidget | None = None) -> None:
        dialog = HistoryWindow(service, parent)
        dialog.exec()