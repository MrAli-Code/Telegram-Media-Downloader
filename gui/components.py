"""سیستم طراحی داخلی: کامپوننت‌های مشترک UI (در همه صفحات بدون تکرار)."""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QBrush, QColor, QDesktopServices
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from config.branding import DEV_NAME, DEV_TITLE, DEV_WEBSITE, DEV_WEBSITE_SHORT
from gui.widgets import set_btn_type
from utils.i18n import t

# وضعیت‌های متحد رنگ برنامه (مطابق Design Tokens تم)
STATUS_TONES = {
    "pending": "pending",
    "resolving": "pending",
    "downloading": "downloading",
    "paused": "paused",
    "completed": "completed",
    "error": "error",
    "cancelled": "cancelled",
}


def open_site(url: str = DEV_WEBSITE) -> None:
    """باز کردن وب‌سایت توسعه‌دهنده در مرورگر پیش‌فرض Windows."""
    QDesktopServices.openUrl(QUrl(url))


def site_link(text: str = "alikhanmohammadi.ir") -> QLabel:
    """برچسب پیوندی وب‌سایت؛ قابل کلیک با مرورگر پیش‌فرض."""
    lab = QLabel(f'<a href="{DEV_WEBSITE}" style="color:#7aa8e6;">{text}</a>')
    lab.setTextFormat(Qt.TextFormat.RichText)
    lab.setOpenExternalLinks(True)
    lab.setCursor(Qt.CursorShape.PointingHandCursor)
    return lab


def status_color(status: str, theme: str = "dark") -> QColor:
    """رنگ یکدست هر وضعیت از تم جاری (برای جدول‌ها و متن‌ها)."""
    from gui.theme import palette

    p = palette(theme)
    mapping = {
        "completed": p.success,
        "error": p.danger,
        "paused": p.warn,
        "downloading": p.accent,
        "cancelled": p.muted,
        "pending": p.badge_info,
    }
    return QColor(mapping.get(STATUS_TONES.get(status, status), p.muted))


def status_foreground(status: str, theme: str = "dark") -> QBrush:
    """قلم‌مو برای رنگ متن سلول‌های جدول بر اساس وضعیت."""
    return QBrush(status_color(status, theme))


class SectionHeader(QWidget):
    """سربرگ بخش: عنوان H3 + توضیح کوتاه (Visual Hierarchy)."""

    def __init__(self, title: str, subtitle: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self.lbl_title = QLabel(title)
        self.lbl_title.setObjectName("section")
        lay.addWidget(self.lbl_title)
        self.lbl_subtitle = QLabel(subtitle)
        self.lbl_subtitle.setObjectName("subtitle")
        self.lbl_subtitle.setVisible(bool(subtitle))
        lay.addWidget(self.lbl_subtitle)

    def set_texts(self, title: str, subtitle: str = "") -> None:
        self.lbl_title.setText(title)
        if self.lbl_subtitle is not None:
            self.lbl_subtitle.setText(subtitle)
            self.lbl_subtitle.setVisible(bool(subtitle))


class KpiCard(QFrame):
    """کارت KPI داشبورد: آیکون + عنوان + مقدار + زیرنویس/وضعیت."""

    def __init__(
        self,
        icon: str,
        label: str,
        value: str = "—",
        subtitle: str = "",
        tone: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("statCard")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(3)
        head = QHBoxLayout()
        self.lbl_icon = QLabel(icon)
        self.lbl_icon.setObjectName("kpiIcon")
        head.addWidget(self.lbl_icon, 0)
        head.addStretch(1)
        lay.addLayout(head)
        self.lbl_label = QLabel(label)
        self.lbl_label.setObjectName("muted")
        lay.addWidget(self.lbl_label)
        self.lbl_value = QLabel(value)
        self.lbl_value.setObjectName("statValue")
        lay.addWidget(self.lbl_value)
        self.lbl_subtitle = QLabel(subtitle)
        self.lbl_subtitle.setObjectName("kpiSub")
        self.lbl_subtitle.setVisible(bool(subtitle))
        lay.addWidget(self.lbl_subtitle)

    def set_value(self, value: str, subtitle: str = "") -> None:
        self.lbl_value.setText(value)
        if subtitle:
            self.lbl_subtitle.setText(subtitle)
            self.lbl_subtitle.setVisible(True)

    def set_label(self, label: str) -> None:
        self.lbl_label.setText(label)


class StatusBadge(QLabel):
    """نشان وضعیت رنگی یکپارچه (Success/Warning/Danger/Info/Idle)."""

    def __init__(self, text: str, status: str = "pending", parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setObjectName("badge")
        self._status = "pending"
        self._refresh_props()
        self.set_status(status)

    def set_status(self, status: str) -> None:
        self._status = STATUS_TONES.get(status, "pending")
        self._refresh_props()

    def set_text(self, text: str) -> None:
        self.setText(text)

    def _refresh_props(self) -> None:
        for key in ("pending", "downloading", "paused", "completed", "error", "cancelled"):
            self.setProperty(key, key == self._status)
        self.style().unpolish(self)
        self.style().polish(self)


class ProgressCard(QFrame):
    """کارت پیشرفت دانلود: نام + بازه + نوار + سرعت/زمان مانده + توضیح."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)
        self.lbl_title = QLabel("")
        self.lbl_title.setObjectName("nameText")
        lay.addWidget(self.lbl_title)
        self.lbl_range = QLabel("")
        self.lbl_range.setObjectName("muted")
        lay.addWidget(self.lbl_range)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        lay.addWidget(self.progress)
        self.lbl_meta = QLabel("")
        self.lbl_meta.setObjectName("muted")
        lay.addWidget(self.lbl_meta)

    def set_data(self, title: str, done: float, total: float, meta: str, paused: bool = False) -> None:
        self.lbl_title.setText(title)
        self.lbl_range.setText(self._fmt_range(done, total))
        percent = int((done / total) * 1000) if total > 0 else 0
        self.progress.setValue(percent)
        self.progress.setProperty("paused", "true" if paused else "false")
        self.progress.style().unpolish(self.progress)
        self.progress.style().polish(self.progress)
        self.lbl_meta.setText(meta)

    @staticmethod
    def _fmt_range(done: float, total: float) -> str:
        from utils.format_utils import format_size

        return f"{format_size(done)} / {format_size(total)}"


class EmptyState(QWidget):
    """وضعیت خالی حرفه‌ای: آیکون + عنوان + توضیح + یک اقدام اصلی."""

    def __init__(
        self,
        icon: str,
        title: str,
        hint: str = "",
        button_text: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("emptyState")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.lbl_icon = QLabel(icon)
        self.lbl_icon.setObjectName("emptyIcon")
        self.lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.lbl_icon)
        self.lbl_title = QLabel(title)
        self.lbl_title.setObjectName("emptyTitle")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.lbl_title)
        self.lbl_hint = QLabel(hint)
        self.lbl_hint.setObjectName("muted")
        self.lbl_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_hint.setWordWrap(True)
        self.lbl_hint.setVisible(bool(hint))
        lay.addWidget(self.lbl_hint)
        self.btn_action = QPushButton(button_text)
        self.btn_action.setObjectName("emptyAction")
        self.btn_action.setProperty("btnType", "primary")
        set_btn_type(self.btn_action, "primary")
        self.btn_action.setVisible(bool(button_text))
        lay.addWidget(self.btn_action, alignment=Qt.AlignmentFlag.AlignCenter)

    def set_texts(self, title: str, hint: str = "") -> None:
        self.lbl_title.setText(title)
        if hint:
            self.lbl_hint.setText(hint)
            self.lbl_hint.setVisible(True)


class AppButton(QPushButton):
    """دکمه شرکت: آیکون + برچسب فارسی (هیچ دکمه بدون Label نیست)."""

    def __init__(self, text: str, icon: str = "", kind: str = "ghost", parent: QWidget | None = None):
        super().__init__(f"{icon} {text}" if icon else text, parent)
        self.setProperty("btnType", kind)
        set_btn_type(self, kind)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._base_text = text
        self._base_icon = icon

    def set_labels(self, text: str, icon: str | None = None) -> None:
        self._base_text = text
        if icon is not None:
            self._base_icon = icon
        self.setText(f"{self._base_icon} {self._base_text}" if self._base_icon else self._base_text)


def storage_progress(used: float, total: float) -> QFrame:
    """کارت کوچک فضای ذخیره‌سازی برای داشبورد (Progress/Donut ساده)."""
    card = QFrame()
    card.setObjectName("card")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(14, 12, 14, 12)
    lay.setSpacing(6)
    head = QHBoxLayout()
    lab = QLabel(t("dash.storage"))
    lab.setObjectName("section")
    head.addWidget(lab)
    head.addStretch(1)
    lay.addLayout(head)
    bar = QProgressBar()
    bar.setRange(0, 1000)
    percent = int((used / total) * 1000) if total > 0 else 0
    bar.setValue(min(1000, percent))
    lay.addWidget(bar)
    note = QLabel()
    note.setObjectName("muted")
    from utils.format_utils import format_size

    note.setText(f"{format_size(used)} / {format_size(total)}")
    lay.addWidget(note)
    return card


class DeveloperFooter(QWidget):
    """فوتر برند: نام توسعه‌دهنده + عنوان شغلی + وب‌سایت قابل کلیک (بند ۹)."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("brandFooter")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 0)
        lay.setSpacing(1)

        row = QHBoxLayout()
        row.setSpacing(6)
        self.lbl_name = QLabel(DEV_NAME)
        self.lbl_name.setObjectName("brandName")
        row.addWidget(self.lbl_name)
        self.lbl_site = site_link(DEV_WEBSITE_SHORT)
        self.lbl_site.setObjectName("brandSite")
        self.lbl_site.setToolTip(t("branding.site_tooltip"))
        row.addWidget(self.lbl_site)
        row.addStretch(1)
        lay.addLayout(row)

        self.lbl_title = QLabel(DEV_TITLE)
        self.lbl_title.setObjectName("brandTitle")
        lay.addWidget(self.lbl_title)


__all__ = [
    "DEV_NAME",
    "DEV_TITLE",
    "DEV_WEBSITE",
    "DEV_WEBSITE_SHORT",
    "STATUS_TONES",
    "AppButton",
    "DeveloperFooter",
    "EmptyState",
    "KpiCard",
    "ProgressCard",
    "SectionHeader",
    "StatusBadge",
    "open_site",
    "site_link",
    "status_color",
    "status_foreground",
    "storage_progress",
]