"""داشبورد: وضعیت دانلود، ایندکس، فضاها، حافظه و فایل‌های اخیر."""

from __future__ import annotations

import shutil
from datetime import datetime

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.components import KpiCard
from utils.format_utils import format_size, to_fa
from utils.i18n import t

# آیکون هر کارت آماری (یکدست و قابل تشخیص سریع)
STAT_ICONS = {
    "conn": "\U0001f517",
    "active": "⬇",
    "queued": "\U0001f4e6",
    "completed": "✅",
    "failed": "⚠",
    "total_dl": "\U0001f4be",
    "files": "\U0001f5c4",
    "index_size": "\U0001f5c2",
    "drives": "\U0001f5a5",
    "favorites": "⭐",
    "trash": "\U0001f5d1",
    "storage": "\U0001f4be",
    "cache": "⚡",
}


class DashboardWidget(QWidget):
    """نمایش خلاصه وضعیت برنامه؛ از ایندکس محلی و صف دانلود خوانده می‌شود."""

    def __init__(self, service, parent: QWidget | None = None):
        super().__init__(parent)
        self._service = service
        self._stat_labels: dict[str, QLabel] = {}
        self._build_ui()
        self._timer = QTimer(self)
        self._timer.setInterval(5000)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        self.refresh()

    # ------------------------------------------------------------------ ui
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        self.lbl_title = QLabel(t("dash.home"))
        self.lbl_title.setObjectName("title")
        root.addWidget(self.lbl_title)

        self._grid = QGridLayout()
        self._grid.setSpacing(10)
        self._stat_cards: dict[str, QLabel] = {}
        self._stat_cards_widgets: dict[str, KpiCard] = {}
        root.addLayout(self._grid)

        self.btn_retry_failed = QPushButton(t("dash.retry_failed"))
        self.btn_retry_failed.setObjectName("ghost")
        self.btn_retry_failed.clicked.connect(self._on_retry_failed)
        root.addWidget(self.btn_retry_failed)

        self.lbl_recent_label = QLabel(t("dash.recent"))
        self.lbl_recent_label.setObjectName("section")
        root.addWidget(self.lbl_recent_label)

        self.lbl_recent = QLabel()
        self.lbl_recent.setObjectName("muted")
        self.lbl_recent.setWordWrap(True)
        root.addWidget(self.lbl_recent, 1)

    def _stat(self, key: str, label: str) -> QLabel:
        if key in self._stat_cards:
            return self._stat_cards[key]
        card = KpiCard(STAT_ICONS.get(key, "\U0001f4ca"), label)
        self._stat_cards[key] = card.lbl_value
        self._stat_cards_widgets[key] = card
        self._stat_labels[key] = card.lbl_label
        col = len(self._stat_cards) - 1
        self._grid.addWidget(card, col // 4, col % 4)
        return card.lbl_value

    def _on_retry_failed(self) -> None:
        try:
            count = self._service.retry_failed()
        except Exception:
            count = 0
        self.btn_retry_failed.setText(t("dash.retry_all.run"))
        self.btn_retry_failed.setEnabled(count > 0)
        self.refresh()

    # ------------------------------------------------------------------ data
    def refresh(self) -> None:
        service = self._service
        try:
            stats = service.stats()
            queue_active, queue_pending = service.queue_stats()
        except Exception:
            stats, queue_active, queue_pending = {}, 0, 0
        try:
            queue_errors = service.queue_error_count()
        except Exception:
            queue_errors = 0
        self.btn_retry_failed.setText(
            t("dash.retry_all.ready", count=to_fa(queue_errors))
        )
        self.btn_retry_failed.setVisible(queue_errors > 0)
        self.btn_retry_failed.setEnabled(True)
        try:
            totals = service.index.totals()
            drives = service.index.list_drives()
            favorites = len(service.drives.favorites(None))
            trash = len(service.drives.trash(None))
            recent = service.drives.recent(None, limit=8)
        except Exception as exc:  # pragma: no cover
            totals, drives, favorites, trash, recent = {}, [], 0, 0, []
            self.lbl_recent.setText(t("dash.error", error=str(exc)))

        conn = getattr(service, "connected", False)
        self._stat("conn", t("dash.telegram_label")).setText(
            t("conn.online") if conn else t("conn.offline")
        )
        self._stat("active", t("dash.active")).setText(to_fa(queue_active))
        self._stat("queued", t("dash.queued")).setText(to_fa(queue_pending))
        self._stat("completed", t("dash.completed")).setText(
            to_fa(int(stats.get("completed_count") or 0))
        )
        self._stat("failed", t("dash.failed")).setText(
            to_fa(int(stats.get("failed_count") or 0))
        )
        self._stat("total_dl", t("dash.total")).setText(
            format_size(int(stats.get("size_total") or 0))
        )
        self._stat("files", t("dash.files")).setText(
            to_fa(int(totals.get("files_count") or 0))
        )
        self._stat("index_size", t("dash.index_size")).setText(
            format_size(int(totals.get("total_size") or 0))
        )
        self._stat("drives", t("dash.drives")).setText(to_fa(len(drives)))
        self._stat("favorites", t("dash.favorites")).setText(to_fa(favorites))
        self._stat("trash", t("dash.trash")).setText(to_fa(trash))

        try:
            free = shutil.disk_usage(service._settings.download_folder).free
            self._stat("storage", t("dash.storage")).setText(format_size(free))
        except OSError:
            self._stat("storage", t("dash.storage")).setText("—")

        try:
            cache = service.cache_status()
            cache_total = int(cache.get("total") or 0)
            self._stat("cache", t("dash.cache")).setText(
                f"{format_size(cache_total)}" if cache.get("count") else "—"
            )
        except Exception:
            self._stat("cache", t("dash.cache")).setText("—")

        lines = []
        private = bool(getattr(service._settings, "private_mode", False))
        for rec in recent:
            name = str(rec.get("file_name") or "؟")
            if private:
                from utils.security import mask_text

                name = mask_text(name, show=1)
            ts = float(rec.get("message_date") or 0)
            date = to_fa(datetime.fromtimestamp(ts).strftime("%Y/%m/%d")) if ts else "—"
            lines.append(f"• {name} — {date}")
        self.lbl_recent.setText("\n".join(lines) if lines else "—")

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.refresh()

    def retranslate(self) -> None:
        """بروزرسانی برچسب‌های داشبورد هنگام تغییر زبان."""
        self.lbl_title.setText(t("dash.home"))
        self.lbl_recent_label.setText(t("dash.recent"))
        for key, label in (
            ("conn", t("dash.telegram_label")),
            ("active", t("dash.active")),
            ("queued", t("dash.queued")),
            ("completed", t("dash.completed")),
            ("failed", t("dash.failed")),
            ("total_dl", t("dash.total")),
            ("files", t("dash.files")),
            ("index_size", t("dash.index_size")),
            ("drives", t("dash.drives")),
            ("favorites", t("dash.favorites")),
            ("trash", t("dash.trash")),
            ("cache", t("dash.cache")),
            ("storage", t("dash.storage")),
        ):
            card = self._stat_cards_widgets.get(key)
            if card is not None:
                card.set_label(label)
        self.refresh()