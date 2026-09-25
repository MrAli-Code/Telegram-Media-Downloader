"""صفحه «فضاهای من» (Drive Manager): افزودن/حذف فضاهای تلگرام و همگام‌سازی."""

from __future__ import annotations

import logging
import time
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gui.theme import apply_badge_props
from gui.widgets import set_btn_type
from utils.format_utils import format_size, to_fa
from utils.i18n import t

logger = logging.getLogger(__name__)

SOURCE_LABELS = {
    "saved": "dm.type.saved",
    "channel": "dm.type.channel",
    "group": "dm.type.group",
}

STATUS_LABELS = {
    "idle": "dm.status.idle",
    "syncing": "dm.status.syncing",
    "ok": "dm.status.ok",
    "error": "dm.status.error",
    "throttled": "dm.status.throttled",
    "not_logged": "dm.status.not_logged",
}


class DriveManagerPage(QWidget):
    """مدیریت فضاهای تلگرام؛ هر فضا یک کانال/گروه/Saved Messages است."""

    toastRequested = Signal(str)

    def __init__(self, service, parent: QWidget | None = None):
        super().__init__(parent)
        self._service = service
        self._drives = service.drives
        self._index = service.index
        self._cards: dict[str, "DriveCard"] = {}
        self._syncing: set[str] = set()
        self._build_ui()
        self._reload()
        self._auto_timer = QTimer(self)
        self._auto_timer.setInterval(30_000)
        self._auto_timer.timeout.connect(self._auto_sync_tick)
        self._auto_timer.start()

    # ------------------------------------------------------------------ ui
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        head = QHBoxLayout()
        title = QLabel(t("dm.title"))
        title.setObjectName("title")
        head.addWidget(title)
        head.addStretch(1)
        self.btn_export = QPushButton(t("dm.export"))
        self.btn_export.setProperty("btnType", "ghost")
        set_btn_type(self.btn_export, "ghost")
        self.btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_export.clicked.connect(self._export_index)
        head.addWidget(self.btn_export)
        self.btn_add = QPushButton("＋ " + t("dm.add"))
        self.btn_add.setProperty("btnType", "primary")
        set_btn_type(self.btn_add, "primary")
        self.btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add.clicked.connect(self._add_drive)
        head.addWidget(self.btn_add)
        root.addLayout(head)

        sync_row = QHBoxLayout()
        self.chk_auto = QCheckBox(t("sync.auto"))
        self.chk_auto.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_auto.toggled.connect(self._on_auto_sync_toggled)
        sync_row.addWidget(self.chk_auto)
        self.lbl_interval = QLabel(t("sync.interval"))
        sync_row.addWidget(self.lbl_interval)
        self.cmb_interval = QComboBox()
        for minutes, key in (
            (5, "sync.interval.5"),
            (15, "sync.interval.15"),
            (30, "sync.interval.30"),
            (60, "sync.interval.60"),
            (0, "sync.interval.manual"),
        ):
            self.cmb_interval.addItem(t(key), minutes)
        self.cmb_interval.currentIndexChanged.connect(self._on_interval_changed)
        sync_row.addWidget(self.cmb_interval)
        sync_row.addStretch(1)
        root.addLayout(sync_row)
        self._reflect_settings()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._container = QWidget()
        self._lay = QVBoxLayout(self._container)
        self._lay.setContentsMargins(2, 2, 2, 2)
        self._lay.setSpacing(12)
        self._lay.addStretch(1)
        self.lbl_empty = QLabel(t("dm.empty"))
        self.lbl_empty.setObjectName("subtitle")
        self.lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lay.insertWidget(0, self.lbl_empty)
        scroll.setWidget(self._container)
        root.addWidget(scroll, 1)

    def _reload(self, *_args) -> None:
        try:
            drives = self._drives.drives_with_stats()
        except Exception as exc:
            logger.exception("بارگذاری فضاها ناموفق بود")
            self.toastRequested.emit(t("dm.generic_error", error=str(exc)))
            drives = []
        existing = set(self._cards)
        new_ids = {str(d.get("id", "")) for d in drives}
        for drive_id in existing - new_ids:
            card = self._cards.pop(drive_id)
            card.deleteLater()
        found = bool(drives)
        self.lbl_empty.setVisible(not found)
        for drive in drives:
            drive_id = str(drive.get("id", ""))
            card = self._cards.get(drive_id)
            if card is None:
                card = DriveCard(drive, self)
                card.syncClicked.connect(self._on_sync)
                card.fullSyncClicked.connect(self._on_full_sync)
                card.cancelClicked.connect(self._on_cancel_sync)
                card.removeClicked.connect(self._on_remove)
                card.openClicked.connect(self._on_open_drive)
                self._lay.insertWidget(self._lay.count() - 1, card)
                self._cards[drive_id] = card
            card.set_drive(drive)

    # ------------------------------------------------------------------ actions
    def _add_drive(self) -> None:
        dialog = DriveEditDialog(self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        payload = dialog.payload()
        payload["account"] = self._service.active_account()
        if not payload["account"]:
            self.toastRequested.emit(t("dm.status.not_logged"))
            return
        self._drives.add_drive(payload)
        self.toastRequested.emit(t("dm.add.toast"))
        self._reload()

    def _on_sync(self, drive_id: str) -> None:
        if self._service.start_sync(drive_id, full=False):
            self._syncing.add(drive_id)
            self._set_card(drive_id, "syncing")
        else:
            self.toastRequested.emit(t("dm.sync.fail"))

    def _on_full_sync(self, drive_id: str) -> None:
        if self._service.start_sync(drive_id, full=True):
            self._syncing.add(drive_id)
            self._set_card(drive_id, "syncing")
        else:
            self.toastRequested.emit(t("dm.sync.fail"))

    def _on_cancel_sync(self, drive_id: str) -> None:
        self._service.request_sync_cancel()
        self._syncing.discard(drive_id)
        self._set_card(drive_id, "idle")

    def _on_remove(self, drive_id: str) -> None:
        drive = self._drives.get(drive_id) or {}
        ans = QMessageBox.question(
            self,
            t("dm.remove.confirm.title"),
            t("dm.remove.confirm.text", name=str(drive.get("name") or "؟")),
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        self._drives.remove(drive_id)
        self.toastRequested.emit(t("dm.removed"))
        self._reload()

    def _on_open_drive(self, drive_id: str) -> None:
        drive = self._drives.get(drive_id) or {}
        username = str(drive.get("username") or "").strip()
        if username:
            QDesktopServices.openUrl(QUrl(f"https://t.me/{username}"))
            return
        drive_name = str(drive.get("name") or "؟")
        source = str(drive.get("username") or "") or (
            "Saved Messages" if str(drive.get("source_type", "")).lower() in ("saved", "account") else ""
        )
        self.toastRequested.emit(t("dm.open.no_link", name=drive_name, source=source))

    def _auto_sync_tick(self) -> None:
        if not self._service.connected:
            return
        settings = getattr(self._service, "settings", None)
        if settings is not None and not settings.auto_sync_enabled:
            return
        minutes = int(settings.auto_sync_minutes) if settings is not None else 15
        if minutes <= 0:
            return
        now = time.time()
        try:
            drives = self._drives.drives_with_stats()
        except Exception:
            return
        for drive in drives:
            drive_id = str(drive.get("id", ""))
            if drive_id in self._syncing:
                continue
            if not drive.get("auto_sync_enabled"):
                continue
            updated = float(drive.get("updated_at") or 0)
            if updated and now - updated < minutes * 60:
                continue
            self._reload()
            self._on_sync(drive_id)
            return

    def _reflect_settings(self) -> None:
        settings = getattr(self._service, "settings", None)
        if settings is None:
            self.chk_auto.setVisible(False)
            return
        self.chk_auto.setChecked(bool(settings.auto_sync_enabled))
        minutes = int(settings.auto_sync_minutes or 0)
        idx = self.cmb_interval.findData(minutes)
        self.cmb_interval.setCurrentIndex(max(0, idx))

    def _on_auto_sync_toggled(self, checked: bool) -> None:
        settings = getattr(self._service, "settings", None)
        if settings is None:
            return
        settings.auto_sync_enabled = checked
        self._service.apply_settings(settings)

    def _on_interval_changed(self, _index: int) -> None:
        settings = getattr(self._service, "settings", None)
        if settings is None:
            return
        settings.auto_sync_minutes = int(self.cmb_interval.currentData() or 0)
        self._service.apply_settings(settings)

    def _export_index(self) -> None:
        path, _filter = QFileDialog.getSaveFileName(
            self, t("dm.export"), "index-export.json", "JSON (*.json);;CSV (*.csv)"
        )
        if not path:
            return
        try:
            count = self._index.export(path)
            self.toastRequested.emit(t("metadata.exported", path=path, count=to_fa(count)))
        except Exception as exc:
            self.toastRequested.emit(t("dm.generic_error", error=str(exc)))

    def _set_card(self, drive_id: str, status: str, extra: str = "") -> None:
        card = self._cards.get(drive_id)
        if card is not None:
            card.set_status(status, extra)

    # ------------------------------------------------------------------ progress hooks
    def on_sync_progress(self, drive_id: str, stats: dict) -> None:
        text = t("dm.sync.progress", added=to_fa(int(stats.get("added") or 0)), updated=to_fa(int(stats.get("updated") or 0)))
        self._set_card(drive_id, "syncing", text)

    def on_sync_finished(self, drive_id: str, status: str, _stats: dict) -> None:
        self._syncing.discard(drive_id)
        self._set_card(drive_id, status if status in STATUS_LABELS else "ok")

    # ------------------------------------------------------------------ refresh
    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._reload()

    def retranslate(self) -> None:
        """بروزرسانی برچسب‌های صفحه فضاها هنگام تغییر زبان."""
        self.btn_export.setText(t("dm.export"))
        self.btn_add.setText("＋ " + t("dm.add"))
        self.chk_auto.setText(t("sync.auto"))
        self.lbl_interval.setText(t("sync.interval"))
        current = self.cmb_interval.currentData()
        self.cmb_interval.blockSignals(True)
        self.cmb_interval.clear()
        for minutes, key in (
            (5, "sync.interval.5"),
            (15, "sync.interval.15"),
            (30, "sync.interval.30"),
            (60, "sync.interval.60"),
            (0, "sync.interval.manual"),
        ):
            self.cmb_interval.addItem(t(key), minutes)
        idx = self.cmb_interval.findData(current)
        self.cmb_interval.setCurrentIndex(max(0, idx))
        self.cmb_interval.blockSignals(False)
        for card in self._cards.values():
            card.retranslate()
        self._reload()


def _parse_username(link: str) -> str:
    link = (link or "").strip()
    if not link:
        return ""
    for prefix in ("https://t.me/", "http://t.me/", "t.me/"):
        if link.startswith(prefix):
            return link[len(prefix):].split("/")[0].strip()
    return link.split("/")[0].strip()


class DriveEditDialog(QDialog):
    """فرم افزودن یک فضای تلگرام جدید."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("dm.add.title"))
        self.setMinimumWidth(440)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(10)

        lay.addWidget(QLabel(t("dm.add.name")))
        self.edt_name = QLineEdit()
        self.edt_name.setPlaceholderText(t("dm.add.name.ph"))
        lay.addWidget(self.edt_name)

        lay.addWidget(QLabel(t("dm.add.username")))
        self.edt_link = QLineEdit()
        self.edt_link.setPlaceholderText(t("dm.add.username.ph"))
        lay.addWidget(self.edt_link)

        lay.addWidget(QLabel(t("dm.add.type")))
        self.cmb_type = QComboBox()
        self.cmb_type.addItem(t("dm.type.saved"), "saved")
        self.cmb_type.addItem(t("dm.type.channel"), "channel")
        self.cmb_type.addItem(t("dm.type.group"), "group")
        lay.addWidget(self.cmb_type)

        hint = QLabel(t("dm.add.hint"))
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        self.lbl_form_error = QLabel(t("dm.add.empty_error"))
        self.lbl_form_error.setObjectName("warn")
        self.lbl_form_error.hide()
        lay.addWidget(self.lbl_form_error)

        row = QHBoxLayout()
        row.addStretch(1)
        btn_cancel = QPushButton(t("settings.cancel"))
        btn_cancel.setProperty("btnType", "ghost")
        set_btn_type(btn_cancel, "ghost")
        btn_cancel.clicked.connect(self.reject)
        row.addWidget(btn_cancel)
        btn_ok = QPushButton(t("dm.add"))
        btn_ok.setProperty("btnType", "primary")
        set_btn_type(btn_ok, "primary")
        btn_ok.clicked.connect(self._accept)
        row.addWidget(btn_ok)
        lay.addLayout(row)

    def payload(self) -> dict:
        from core.drive_manager import default_drive_payload

        source = str(self.cmb_type.currentData() or "channel")
        return default_drive_payload(
            name=self.edt_name.text().strip() or t("dm.add.unnamed"),
            source_type=source,
            account="",
        ) | {"username": _parse_username(self.edt_link.text())}

    def _accept(self) -> None:
        if not self.edt_name.text().strip() and not self.edt_link.text().strip():
            self.lbl_form_error.show()
            self.edt_name.setFocus()
            return
        self.accept()


class DriveCard(QFrame):
    """کارت نمایش یک فضا: نام، آمار، وضعیت همگام‌سازی و کنترل‌ها."""

    syncClicked = Signal(str)
    fullSyncClicked = Signal(str)
    cancelClicked = Signal(str)
    removeClicked = Signal(str)
    openClicked = Signal(str)

    def __init__(self, drive: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self._drive_id = str(drive.get("id", ""))
        self._last_drive: dict = drive
        self._build_ui()
        self.set_drive(drive)

    def _build_ui(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)

        top = QHBoxLayout()
        self.lbl_name = QLabel()
        self.lbl_name.setObjectName("nameText")
        self.lbl_type = QLabel()
        self.lbl_type.setObjectName("muted")
        self.lbl_badge = QLabel()
        self.lbl_badge.setObjectName("badge")
        top.addWidget(self.lbl_name)
        top.addWidget(self.lbl_type, 1)
        top.addWidget(self.lbl_badge)
        lay.addLayout(top)

        info = QHBoxLayout()
        self.lbl_files = QLabel()
        self.lbl_files.setObjectName("muted")
        self.lbl_size = QLabel()
        self.lbl_size.setObjectName("muted")
        self.lbl_sync = QLabel()
        self.lbl_sync.setObjectName("muted")
        info.addWidget(self.lbl_files)
        info.addWidget(self.lbl_size)
        info.addStretch(1)
        info.addWidget(self.lbl_sync)
        lay.addLayout(info)

        row = QHBoxLayout()
        row.addStretch(1)
        self.btn_sync = self._make_button(t("dm.sync"), "ghost", self.syncClicked)
        self.btn_full = self._make_button(t("dm.sync.full"), "ghost", self.fullSyncClicked)
        self.btn_cancel = self._make_button(t("dm.sync.cancel"), "ghost", self.cancelClicked)
        self.btn_open = self._make_button(t("dm.open"), "ghost", self.openClicked)
        self.btn_remove = self._make_button(t("dm.remove"), "danger", self.removeClicked)
        for b in (self.btn_sync, self.btn_full, self.btn_cancel, self.btn_open, self.btn_remove):
            row.addWidget(b)
        lay.addLayout(row)

    def _make_button(self, text: str, kind: str, signal) -> QPushButton:
        btn = QPushButton(text)
        btn.setProperty("btnType", kind)
        set_btn_type(btn, kind)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda _=False, s=signal: s.emit(self._drive_id))
        return btn

    def set_drive(self, drive: dict) -> None:
        self._last_drive = drive
        self._drive_id = str(drive.get("id", ""))
        self.lbl_name.setText(str(drive.get("name") or "؟"))
        source = str(drive.get("source_type") or "channel").lower()
        self.lbl_type.setText(t(SOURCE_LABELS.get(source, source)))
        files = int(drive.get("files_count") or 0)
        size = int(drive.get("total_size") or 0)
        self.lbl_files.setText(f"{t('dm.files')}: {to_fa(files)}")
        self.lbl_size.setText(f"{t('dm.size')}: {format_size(size)}")

        updated = float(drive.get("updated_at") or 0) or float(drive.get("cursor") or 0)
        last_sync = to_fa(datetime.fromtimestamp(updated).strftime("%Y/%m/%d - %H:%M")) if updated else t("dm.never")
        self.lbl_sync.setText(f"{t('dm.last_sync')}: {last_sync}")

        status = str(drive.get("status") or "idle")
        self.set_status(status)

    def set_status(self, status: str, extra: str = "") -> None:
        label_key = STATUS_LABELS.get(status, STATUS_LABELS["idle"])
        text = t(label_key)
        if extra:
            text = extra
        self.lbl_badge.setText(text)
        apply_badge_props(self.lbl_badge, status if status != "syncing" else "downloading")
        syncing = status == "syncing"
        self.btn_sync.setVisible(not syncing)
        self.btn_full.setVisible(not syncing)
        self.btn_open.setVisible(not syncing)
        self.btn_cancel.setVisible(syncing)

    def retranslate(self) -> None:
        """بروزرسانی برچسب‌های کارت هنگام تغییر زبان."""
        self.btn_sync.setText(t("dm.sync"))
        self.btn_full.setText(t("dm.sync.full"))
        self.btn_cancel.setText(t("dm.sync.cancel"))
        self.btn_open.setText(t("dm.open"))
        self.btn_remove.setText(t("dm.remove"))
        if getattr(self, "_last_drive", None) is not None:
            self.set_drive(self._last_drive)