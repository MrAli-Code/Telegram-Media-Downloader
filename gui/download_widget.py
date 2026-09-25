"""کارت دانلود: نمایش پیشرفت، وضعیت و کنترل هر فایل به صورت جداگانه."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, SignalInstance
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QProgressBar,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.models import STATUS_COMPLETED, STATUS_ERROR
from config.features import enabled as feature_enabled
from gui.components import StatusBadge
from gui.widgets import set_btn_type
from utils.format_utils import (
    format_duration,
    format_eta,
    format_percent,
    format_size,
    format_speed,
    to_fa,
)
from utils.i18n import t

KIND_TEXT = {
    "video": "fm.kind.video",
    "video_note": "fm.kind.video_note",
    "audio": "fm.kind.audio",
    "voice": "fm.kind.voice",
    "photo": "fm.kind.photo",
    "document": "fm.kind.document",
}


class DownloadCard(QFrame):
    """نمایش یک آیتم صف با کنترل‌های توقف/ادامه/لغو/حذف/باز کردن پوشه/تلاش مجدد."""

    pauseClicked = Signal(str)
    resumeClicked = Signal(str)
    cancelClicked = Signal(str)
    removeClicked = Signal(str)
    openFolderClicked = Signal(str)
    retryClicked = Signal(str)
    moveToFrontClicked = Signal(str)
    priorityClicked = Signal(str, int)
    streamClicked = Signal(str)

    def __init__(self, snapshot: dict, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("card")
        self._item_id = str(snapshot.get("id", ""))
        self._build_ui()
        self.set_data(snapshot)

    # ------------------------------------------------------------------ ui
    def _build_ui(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(10)
        self.lbl_index = QLabel()
        self.lbl_index.setObjectName("muted")
        self.lbl_name = QLabel()
        self.lbl_name.setObjectName("nameText")
        self.lbl_kind = QLabel()
        self.lbl_kind.setObjectName("muted")
        self.lbl_badge = StatusBadge("", "pending")
        top.addWidget(self.lbl_index)
        top.addWidget(self.lbl_name, 1)
        top.addWidget(self.lbl_kind)
        top.addWidget(self.lbl_badge)
        lay.addLayout(top)

        info = QHBoxLayout()
        self.lbl_meta = QLabel()
        self.lbl_meta.setObjectName("muted")
        self.lbl_size = QLabel()
        self.lbl_size.setObjectName("muted")
        info.addWidget(self.lbl_meta)
        info.addStretch(1)
        info.addWidget(self.lbl_size)
        lay.addLayout(info)

        bar_row = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 1000)
        self.progress.setFixedHeight(10)
        self.lbl_percent = QLabel()
        self.lbl_percent.setObjectName("muted")
        self.lbl_percent.setMinimumWidth(52)
        self.lbl_percent.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        bar_row.addWidget(self.progress, 1)
        bar_row.addWidget(self.lbl_percent)
        lay.addLayout(bar_row)

        self.lbl_speed = QLabel()
        self.lbl_speed.setObjectName("muted")
        lay.addWidget(self.lbl_speed)

        self.lbl_error = QLabel()
        self.lbl_error.setObjectName("errorText")
        self.lbl_error.setWordWrap(True)
        self.lbl_error.hide()
        lay.addWidget(self.lbl_error)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.btn_pause = self._make_button("", "primary", self.pauseClicked)
        self.btn_resume = self._make_button("", "success", self.resumeClicked)
        self.btn_cancel = self._make_button("", "danger", self.cancelClicked)
        self.btn_retry = self._make_button("", "ghost", self.retryClicked)
        self.btn_open = self._make_button("", "ghost", self.openFolderClicked)
        self.btn_remove = self._make_button("", "ghost", self.removeClicked)
        self._stream_enabled = feature_enabled("ENABLE_STREAMING")
        self.btn_stream: QPushButton | None = None
        if self._stream_enabled:
            self.btn_stream = self._make_button("", "ghost", self.streamClicked)
        widgets = [self.btn_pause, self.btn_resume, self.btn_cancel, self.btn_retry, self.btn_open, self.btn_remove]
        if self.btn_stream is not None:
            widgets.insert(-2, self.btn_stream)
        for widget in widgets:
            actions.addWidget(widget)
        self.btn_menu = QToolButton()
        self.btn_menu.setText("⋮")
        self.btn_menu.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_menu.setObjectName("cardMenu")
        self.btn_menu.setCursor(Qt.CursorShape.PointingHandCursor)
        self._build_menu()
        actions.addWidget(self.btn_menu)
        lay.addLayout(actions)
        self._relabel()

    def _build_menu(self) -> None:
        self.menu_root = QMenu(self)
        self.action_move_top = QAction(t("queue.move_top"), self.menu_root)
        self.action_move_top.triggered.connect(lambda: self.moveToFrontClicked.emit(self._item_id))
        self.menu_root.addAction(self.action_move_top)

        if self._stream_enabled:
            self.action_stream = QAction(t("stream.live"), self.menu_root)
            self.action_stream.triggered.connect(self._emit_stream)
            self.menu_root.addAction(self.action_stream)

        priority_menu = self.menu_root.addMenu(t("queue.priority"))
        self.priority_menu = priority_menu
        self._priority_actions: dict[int, QAction] = {}
        for value, key in ((0, "priority.low"), (1, "priority.normal"), (2, "priority.high")):
            act = QAction(t(key), priority_menu)
            act.setCheckable(True)
            act.triggered.connect(lambda _=False, v=value: self.priorityClicked.emit(self._item_id, v))
            priority_menu.addAction(act)
            self._priority_actions[value] = act

        self.menu_root.addSeparator()
        action_remove = QAction(t("remove"), self.menu_root)
        action_remove.triggered.connect(lambda: self.removeClicked.emit(self._item_id))
        self.menu_root.addAction(action_remove)
        self.btn_menu.setMenu(self.menu_root)

    def _emit_stream(self) -> None:
        part = str((self._last_snap or {}).get("part_path", ""))
        if part:
            self.streamClicked.emit(part)

    def _relabel(self) -> None:
        self.btn_pause.setText(t("pause"))
        self.btn_resume.setText(t("resume"))
        self.btn_cancel.setText(t("cancel"))
        self.btn_retry.setText(t("retry.again"))
        self.btn_open.setText(t("open_folder"))
        self.btn_remove.setText(t("remove"))
        if self.btn_stream is not None:
            self.btn_stream.setText(t("stream.live"))

    def retranslate(self) -> None:
        """بروزرسانی برچسب‌های کارت هنگام تغییر زبان."""
        self._relabel()
        self.action_move_top.setText(t("queue.move_top"))
        if getattr(self, "_stream_enabled", False):
            self.action_stream.setText(t("stream.live"))
        for value, key in ((0, "priority.low"), (1, "priority.normal"), (2, "priority.high")):
            act = self._priority_actions.get(value)
            if act is not None:
                act.setText(t(key))
        self.priority_menu.setTitle(t("queue.priority"))
        if getattr(self, "_last_snap", None) is not None:
            self.set_data(self._last_snap)

    def _make_button(self, text: str, kind: str, signal: SignalInstance) -> QPushButton:
        btn = QPushButton(text)
        btn.setProperty("btnType", kind)
        set_btn_type(btn, kind)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda _=False, s=signal: s.emit(self._item_id))
        return btn

    # ------------------------------------------------------------------ data
    def set_data(self, snap: dict) -> None:
        self._last_snap = snap
        status = str(snap.get("status", "pending"))

        self.lbl_index.setText(to_fa(f"{int(snap.get('order', 0))}."))

        name = str(snap.get("display_name") or snap.get("file_name") or t("download.unknown_name"))
        self.lbl_name.setText(name)
        self.lbl_name.setToolTip(name)

        kind_key = KIND_TEXT.get(str(snap.get("kind", "")))
        self.lbl_kind.setText(t(kind_key) if kind_key else "")
        self.lbl_badge.set_text(str(snap.get("status_label", status)))
        self.lbl_badge.set_status(status)

        meta = str(snap.get("message_info", ""))
        self.lbl_meta.setText(meta if meta else str(snap.get("link", "")))
        self.lbl_size.setText(format_size(int(snap.get("media_size", 0) or 0)))

        downloaded = int(snap.get("downloaded", 0) or 0)
        size = int(snap.get("media_size", 0) or 0)
        percent = 0
        if size > 0:
            percent = max(0, min(100, int(downloaded * 100 / size)))
        self.progress.setValue(int(percent * 10))
        self.progress.setProperty("paused", status == "paused")
        self.progress.style().unpolish(self.progress)
        self.progress.style().polish(self.progress)

        pct: int | None = None
        if status in ("downloading", "paused") and size > 0:
            pct = percent
        elif status == STATUS_COMPLETED:
            pct = 100
        self.lbl_percent.setText(format_percent(pct))

        speed = float(snap.get("speed", 0) or 0)
        eta = float(snap.get("eta", 0) or 0)
        elapsed = float(snap.get("elapsed", 0) or 0)
        parts = []
        if status in ("downloading", "paused") and size > 0:
            parts.append(t("widget.received", down=format_size(downloaded), total=format_size(size)))
        if speed > 0:
            parts.append(t("widget.speed", speed=format_speed(speed)))
        if eta > 0:
            parts.append(t("widget.remaining", eta=format_eta(eta)))
        if status == "downloading" and elapsed > 0:
            parts.append(t("widget.elapsed", elapsed=format_duration(elapsed)))
        self.lbl_speed.setText(" · ".join(parts))

        error = str(snap.get("error", ""))
        if error and status in (STATUS_ERROR, STATUS_COMPLETED):
            self.lbl_error.setText(error)
            self.lbl_error.show()
        else:
            self.lbl_error.hide()

        self._update_actions(status, snap)

    def _update_actions(self, status: str, snap: dict) -> None:
        finished = snap.get("is_finished", False)
        self.btn_pause.setVisible(bool(snap.get("can_pause", False)))
        self.btn_resume.setVisible(bool(snap.get("can_resume", False)))
        self.btn_cancel.setVisible(bool(snap.get("can_cancel", False)))
        self.btn_retry.setVisible(status == STATUS_ERROR)
        self.btn_open.setVisible(status == STATUS_COMPLETED)
        self.btn_remove.setVisible(finished)
        if self.btn_stream is not None:
            part = str(snap.get("part_path", ""))
            self.btn_stream.setVisible(status in ("downloading", "paused") and bool(part))
        if getattr(self, "_stream_enabled", False):
            self.action_stream.setEnabled(status in ("downloading", "paused") and bool(snap.get("part_path")))
        self.action_move_top.setEnabled(status == "pending")
        priority = int(snap.get("priority", 1) or 1)
        for value, act in self._priority_actions.items():
            act.setChecked(value == priority)

    @property
    def item_id(self) -> str:
        return self._item_id
