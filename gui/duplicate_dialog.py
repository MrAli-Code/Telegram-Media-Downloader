"""دیالوگ مدیریت فایل‌های تکراری: نگه‌داشتن، جایگزینی یا تغییر نام پس از دانلود."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from gui.widgets import set_btn_type
from utils.format_utils import to_fa
from utils.i18n import t


class DuplicateDialog(QDialog):
    """الزامات انتخاب کاربر برای فایل جدید دانلودشده که نسخه هم‌هش دارد."""

    def __init__(self, groups: list[dict] | None, parent: QWidget | None = None):
        super().__init__(parent)
        groups = groups or []
        self._count = 0
        for group in groups:
            try:
                self._count += int(group.get("n", 0)) - 1
            except (TypeError, ValueError):
                pass
        self._choice = "keep"
        self.setWindowTitle(t("duplicates.title"))
        self.setMinimumWidth(560)
        self.setModal(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        title = QLabel(t("duplicates.dialog_title"))
        title.setObjectName("title")
        root.addWidget(title)

        if self._count > 0:
            count_lab = QLabel(t("duplicates.text", count=to_fa(self._count)))
            count_lab.setObjectName("muted")
            root.addWidget(count_lab)

        self._list = QListWidget()
        self._list.setMinimumHeight(120)
        for group in groups:
            names = (group.get("names") or "").split("\n")
            for name in names[:100]:
                if name:
                    self._list.addItem(name)
        if self._list.count():
            root.addWidget(QLabel(t("duplicates.old_copies")))
            root.addWidget(self._list, 1)

        self._keep = QRadioButton(t("duplicates.keep"), self)
        self._replace = QRadioButton(t("duplicates.replace"), self)
        self._rename = QRadioButton(t("duplicates.rename"), self)
        self._keep.setChecked(True)
        group = QButtonGroup(self)
        group.addButton(self._keep)
        group.addButton(self._replace)
        group.addButton(self._rename)
        root.addWidget(self._keep)
        root.addWidget(self._replace)
        root.addWidget(self._rename)
        self._keep.toggled.connect(lambda on: on and setattr(self, "_choice", "keep"))
        self._replace.toggled.connect(lambda on: on and setattr(self, "_choice", "replace"))
        self._rename.toggled.connect(lambda on: on and setattr(self, "_choice", "rename"))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        set_btn_type(ok_btn, "primary")
        ok_btn.setText(t("dialog.ok"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(t("dialog.cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def choice(self) -> str:
        """keep | replace | rename"""
        return self._choice

    @staticmethod
    def run(parent: QWidget | None = None, groups: list[dict] | None = None) -> str:
        """اجرای مدال؛ خروجی «keep/replace/rename» یا خالی در صورت انصراف."""
        dialog = DuplicateDialog(groups, parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.choice()
        return ""