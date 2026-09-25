"""انتخاب پوشه مجازی برای انتقال فایل‌های ایندکس‌شده."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from gui.widgets import set_btn_type
from utils.i18n import t

_USER_ROLE = int(Qt.ItemDataRole.UserRole)


class FolderPicker(QDialog):
    """نمایش پوشه‌های یک فضا و امکان انتخاب پوشه مقصد (یا ریشه)."""

    def __init__(self, drives, drive_id: str, parent=None):
        super().__init__(parent)
        self._drives = drives
        self._selected = ""
        self.setWindowTitle(t("fm.move_folder"))
        self.setMinimumWidth(340)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)
        lbl = QLabel(t("fm.move.prompt"))
        lbl.setObjectName("subtitle")
        lay.addWidget(lbl)

        self.list_widget = QListWidget()

        def add_item(text: str, value: str) -> None:
            item = QListWidgetItem(text)
            item.setData(_USER_ROLE, value)
            self.list_widget.addItem(item)

        add_item(t("fm.move.root"), "")
        try:
            for folder in self._drives.folders(drive_id):
                add_item(
                    str(folder.get("name", "؟")),
                    str(folder.get("id", "")),
                )
        except Exception:
            pass
        self.list_widget.setCurrentRow(0)
        lay.addWidget(self.list_widget, 1)

        row = QHBoxLayout()
        row.addStretch(1)
        btn_cancel = QPushButton(t("settings.cancel"))
        btn_cancel.setProperty("btnType", "ghost")
        set_btn_type(btn_cancel, "ghost")
        btn_cancel.clicked.connect(self.reject)
        row.addWidget(btn_cancel)
        btn_ok = QPushButton(t("fm.move"))
        btn_ok.setProperty("btnType", "primary")
        set_btn_type(btn_ok, "primary")
        btn_ok.clicked.connect(self._accept)
        row.addWidget(btn_ok)
        lay.addLayout(row)

    def selected_folder_id(self) -> str:
        return self._selected

    def _accept(self) -> None:
        item = self.list_widget.currentItem()
        if item is not None:
            self._selected = str(item.data(_USER_ROLE) or "")
        self.accept()