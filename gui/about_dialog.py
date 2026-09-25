"""دیالوگ درباره برنامه: Developer، نسخه و وب‌سایت (با دکمه باز کردن مرورگر)."""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from config.branding import DEV_NAME, DEV_TITLE, DEV_WEBSITE, DEV_WEBSITE_SHORT
from config.edition import DISPLAY_NAME, current
from config.version import APP_VERSION
from gui.widgets import set_btn_type
from utils.i18n import t

EDITION_LABELS = {"personal": "Personal", "public": "Public"}


class AboutDialog(QDialog):
    """اطلاعات توسعه‌دهنده و لینک وب‌سایت (ذیل قوانین Telegram)."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(t("about.title"))
        self.setMinimumWidth(560)
        self.setModal(True)

        info = current()
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 22)
        root.setSpacing(14)

        title = QLabel(DISPLAY_NAME)
        title.setObjectName("title")
        root.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)

        edition = EDITION_LABELS.get(info.edition, info.edition)
        version = QLabel(t("about.edition", edition=edition, version=APP_VERSION))
        version.setObjectName("subtitle")
        root.addWidget(version, alignment=Qt.AlignmentFlag.AlignCenter)

        desc = QLabel(t("about.description"))
        desc.setObjectName("muted")
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignJustify)
        root.addWidget(desc)

        root.addWidget(self._separator())

        dev_title = QLabel(f"<b>{t('about.developer')}</b>")
        dev_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(dev_title)

        name = QLabel(DEV_NAME)
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setStyleSheet("font-size: 15pt; font-weight: 700;")
        root.addWidget(name)

        role = QLabel(DEV_TITLE)
        role.setObjectName("subtitle")
        role.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(role)

        website_row = QHBoxLayout()
        lab_site = QLabel(
            f"{t('about.website')} <a style='color:#7aa8e6;' href='{DEV_WEBSITE}'>{DEV_WEBSITE_SHORT}</a>"
        )
        lab_site.setObjectName("muted")
        lab_site.setTextFormat(Qt.TextFormat.RichText)
        lab_site.setOpenExternalLinks(True)
        website_row.addWidget(lab_site, 1)
        btn_site = QPushButton(t("about.website_btn"))
        btn_site.setProperty("btnType", "primary")
        set_btn_type(btn_site, "primary")
        btn_site.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_site.clicked.connect(self._open_site)
        website_row.addWidget(btn_site)
        root.addLayout(website_row)

        footnote = QLabel(DEV_WEBSITE)
        footnote.setObjectName("muted")
        footnote.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footnote.setStyleSheet("color: #6b7990;")
        root.addWidget(footnote)

        close_btn = QPushButton(t("dialog.close"))
        close_btn.setProperty("btnType", "ghost")
        set_btn_type(close_btn, "ghost")
        close_btn.clicked.connect(self.accept)
        root.addWidget(close_btn)

    @staticmethod
    def _separator() -> QLabel:
        line = QLabel()
        line.setFixedHeight(1)
        line.setStyleSheet("background: #303a4a;")
        return line

    def _open_site(self) -> None:
        QDesktopServices.openUrl(QUrl(DEV_WEBSITE))

    @staticmethod
    def run(parent: QWidget | None = None) -> None:
        dialog = AboutDialog(parent)
        dialog.exec()