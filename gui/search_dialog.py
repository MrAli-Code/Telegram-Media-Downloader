"""جستجوی سراسری: ایندکس، تاریخچه و صف دانلود در یک دیالوگ."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.widgets import set_btn_type
from utils.format_utils import format_size, to_fa
from utils.i18n import t

SECTION_RE = "section"


class SearchEverywhereDialog(QDialog):
    """جستجوی همزمان در فایل‌های ایندکس‌شده، تاریخچه دانلود و صف."""

    def __init__(self, service, parent: QWidget | None = None):
        super().__init__(parent)
        self._service = service
        self._results: dict[str, list[dict]] = {"files": [], "history": [], "queue": []}
        self.setWindowTitle(t("search.title"))
        self.resize(620, 520)
        self.setModal(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        self.edt_query = QLineEdit()
        self.edt_query.setPlaceholderText(t("search.placeholder"))
        root.addWidget(self.edt_query)

        self.lbl_count = QLabel(t("search.empty"))
        self.lbl_count.setObjectName("muted")
        root.addWidget(self.lbl_count)

        self.lst = QListWidget()
        self.lst.itemActivated.connect(self._on_activate)
        self.lst.itemDoubleClicked.connect(self._on_activate)
        root.addWidget(self.lst, 1)

        hint = QLabel(t("search.hint"))
        hint.setObjectName("muted")
        root.addWidget(hint)

        footer = QHBoxLayout()
        footer.addStretch(1)
        btn_close = QPushButton(t("dialog.close"))
        set_btn_type(btn_close, "ghost")
        btn_close.clicked.connect(self.reject)
        footer.addWidget(btn_close)
        root.addLayout(footer)

        self._timer = QTimer(self)
        self._timer.setInterval(180)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._run_search)
        self.edt_query.textChanged.connect(lambda _text: self._timer.start())
        self.edt_query.textChanged.connect(self._clear_results)

    def _clear_results(self, _text: str) -> None:
        self.lst.clear()
        self.lbl_count.setText(t("search.empty"))

    def _run_search(self) -> None:
        q = self.edt_query.text().strip()
        if len(q) < 2:
            return
        self._results = self._service.search_everywhere(q)
        self._rebuild()

    def _rebuild(self) -> None:
        self.lst.clear()
        total = 0
        for section, label_key, meta in (
            ("files", "search.section.files", "file"),
            ("queue", "search.section.queue", "queue"),
            ("history", "search.section.history", "history"),
        ):
            rows = self._results.get(section, [])
            if not rows:
                continue
            head = QListWidgetItem(t(label_key))
            head.setData(Qt.ItemDataRole.UserRole, SECTION_RE)
            head.setFlags(Qt.ItemFlag.NoItemFlags)
            self.lst.addItem(head)
            for row in rows:
                total += 1
                self.lst.addItem(self._make_item(section, row))
        if total == 0:
            self.lbl_count.setText(t("search.no_results"))
        else:
            self.lbl_count.setText(t("search.results", count=to_fa(total)))

    def _make_item(self, section: str, row: dict) -> QListWidgetItem:
        text: str
        if section == "files":
            name = str(row.get("file_name") or "؟")
            drive = str(row.get("drive_name") or "")
            size = format_size(int(row.get("file_size") or 0))
            text = f"{name}  ·  {drive}  ·  {size}"
        elif section == "queue":
            text = str(row.get("display_name") or row.get("file_name") or row.get("link") or "؟")
        else:
            text = (
                f"{row.get('name', '؟')}  ·  {row.get('status_label', row.get('status', ''))}  ·  "
                f"{row.get('created_text', row.get('created_at', ''))}"
            )
        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, section)
        item.setData(Qt.ItemDataRole.UserRole + 1, row)
        return item

    def _on_activate(self, item: QListWidgetItem) -> None:
        section = item.data(Qt.ItemDataRole.UserRole)
        if section != "files":
            return
        row = item.data(Qt.ItemDataRole.UserRole + 1)
        path = str(row.get("local_path") or "")
        if path and os.path.exists(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        else:
            QMessageBox.information(self, t("search.title"), t("search.not_downloaded"))

    @staticmethod
    def run(service, parent: QWidget | None = None) -> None:
        dialog = SearchEverywhereDialog(service, parent)
        dialog.exec()