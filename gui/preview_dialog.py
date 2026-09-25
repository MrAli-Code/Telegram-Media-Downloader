"""پیش‌نمایش داخلی فایل‌ها: تصویر، متن، PDF، ZIP و پخش صدا/ویدیو (با پشتیبانی از پخش جریانی)."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from gui.widgets import set_btn_type
from utils.i18n import t

_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".ico"}
_VIDEO_EXT = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".3gp"}
_AUDIO_EXT = {".mp3", ".m4a", ".aac", ".ogg", ".oga", ".wav", ".flac", ".opus", ".wma"}
_TEXT_EXT = {".txt", ".md", ".json", ".log", ".srt", ".vtt", ".csv", ".py", ".ini", ".xml", ".html", ".fa", ".en"}
_MAX_TEXT = 8 * 1024 * 1024
_ZOOM_STEP = 1.15


def guess_media_kind(name: str) -> str:
    """تشخیص نوع پیش‌نمایش بر اساس پسوند فایل."""
    ext = Path(name).suffix.lower()
    if ext in _IMAGE_EXT:
        return "image"
    if ext in _VIDEO_EXT:
        return "video"
    if ext in _AUDIO_EXT:
        return "audio"
    if ext == ".pdf":
        return "pdf"
    if ext == ".zip":
        return "zip"
    if ext in _TEXT_EXT:
        return "text"
    return "other"


def _temp_player(page: QWidget) -> tuple[object, QWidget | None]:
    """ساخت QMediaPlayer + ویجت ویدیو با مقاوم در برابر نبود بک‌اند."""
    try:
        from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
        from PySide6.QtMultimediaWidgets import QVideoWidget
    except Exception:  # pragma: no cover
        return SimpleNamespace(play=lambda *a, **k: None, stop=lambda *a, **k: None), None
    player = QMediaPlayer(page)
    video = QVideoWidget()
    player.setVideoOutput(video)
    output = QAudioOutput()
    player.setAudioOutput(output)
    player._audio_output = output  # type: ignore[attr-defined]
    return player, video


class PreviewDialog(QDialog):
    """دیالوگ پیش‌نمایش محتوا؛ برای فایل‌های صوتی/ویدیویی امکان پخش جریانی (URL سرور Range) وجود دارد."""

    def __init__(self, path: Path | None = None, kind: str = "auto", stream_url: str = "", parent=None):
        super().__init__(parent)
        self._path = Path(path) if path is not None else None
        self._kind = kind if kind != "auto" else guess_media_kind(str(self._path) if self._path else "")
        self._stream_url = stream_url
        self.setWindowTitle(t("preview.title"))
        self.resize(900, 620)
        self._player = None
        self._video_widget: QWidget | None = None
        self._is_video = self._kind in ("video", "audio")

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 10)
        if self._is_video:
            self._build_media(root)
        else:
            root.addWidget(self._build_static(), 1)

        bar = QHBoxLayout()
        bar.addStretch(1)
        if self._kind == "image":
            for txt, delta in (("−", -1), ("+", 1)):
                btn = QToolButton()
                btn.setText(txt)
                btn.clicked.connect(
                    lambda _checked=False, d=delta: self._zoom(self._zoom_step if d > 0 else 1 / self._zoom_step)
                )
                bar.addWidget(btn)
            btn_fit = QPushButton(t("preview.fit"))
            btn_fit.clicked.connect(self._zoom_fit)
            bar.addWidget(btn_fit)
            bar.addStretch(1)
        if self._is_video:
            self._build_controls(bar)
        btn_ext = QPushButton(t("preview.open_external"))
        btn_ext.clicked.connect(self._open_external)
        bar.addWidget(btn_ext)
        btn_close = QPushButton(t("dialog.close"))
        btn_close.setProperty("btnType", "primary")
        set_btn_type(btn_close, "primary")
        btn_close.clicked.connect(self.accept)
        bar.addWidget(btn_close)
        root.addLayout(bar)

        self._loaded = False

    # ------------------------------------------------------------------ controller
    def _build_controls(self, bar: QHBoxLayout) -> None:
        if self._player is None:
            self._lbl_time = QLabel("0:00 / 0:00")
            bar.addWidget(self._lbl_time)
            return
        btn_play = QToolButton()
        btn_play.setText(t("preview.play"))
        btn_play.setCheckable(True)
        btn_play.clicked.connect(self._toggle_play)
        bar.addWidget(btn_play)
        self.btn_play = btn_play

        self.slider_seek = QSlider(Qt.Orientation.Horizontal)
        self.slider_seek.setRange(0, 0)
        self.slider_seek.setMinimumWidth(240)
        bar.addWidget(self.slider_seek)

        self.btn_volume = QToolButton()
        self.btn_volume.setText(t("preview.mute"))
        self.btn_volume.setCheckable(True)
        self.btn_volume.clicked.connect(self._toggle_mute)
        bar.addWidget(self.btn_volume)

        self.lbl_time = QLabel("0:00 / 0:00")
        bar.addWidget(self.lbl_time)

        if self._video_widget is not None:
            btn_full = QToolButton()
            btn_full.setText("⛶")
            btn_full.clicked.connect(self._toggle_fullscreen)
            bar.addWidget(btn_full)

        player = self._player
        player.positionChanged.connect(self._on_position)
        player.durationChanged.connect(self._on_duration)
        player.errorOccurred.connect(self._on_player_error)
        self.slider_seek.sliderMoved.connect(player.setPosition)

    def _build_media(self, root: QVBoxLayout) -> None:
        player, video = _temp_player(self)
        self._player = player
        self._video_widget = video
        if video is not None:
            video.setVisible(self._kind == "video")
            root.addWidget(video, 1)
        elif self._kind == "video":
            lab = QLabel(t("preview.no_backend"))
            lab.setObjectName("muted")
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            root.addWidget(lab, 1)
        self._play_source()

    def _play_source(self) -> None:
        if self._player is None or not hasattr(self._player, "setSource"):
            return
        if self._stream_url:
            self._player.setSource(QUrl(self._stream_url))
        elif self._path is not None:
            self._player.setSource(QUrl.fromLocalFile(str(self._path)))
        try:
            self._player.play()
        except Exception:  # pragma: no cover - اجرای واقعی فقط روی دسکتاپ
            pass

    def _toggle_play(self) -> None:
        if self._player is None:
            return
        if self._player.playbackState() and str(self._player.playbackState()).endswith("PlaybackState.PlayingState"):
            self._player.pause()
        else:
            self._player.play()
        self.btn_play.setChecked(False)

    def _toggle_mute(self) -> None:
        if self._player is None:
            return
        output = getattr(self._player, "_audio_output", None)
        if output is not None:
            output.setMuted(not output.isMuted())

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _on_position(self, pos: int) -> None:
        if self.slider_seek.maximum() > 0:
            self.slider_seek.setValue(pos)
        self.lbl_time.setText(self._fmt(pos) + " / " + self._fmt(self.slider_seek.maximum()))

    def _on_duration(self, dur: int) -> None:
        self.slider_seek.setRange(0, max(0, dur))
        self.lbl_time.setText("0:00 / " + self._fmt(dur))

    def _on_player_error(self, *_args) -> None:
        self.lbl_time.setText(t("preview.play_error"))

    @staticmethod
    def _fmt(ms: int) -> str:
        sec = max(0, int(ms) // 1000)
        m, s = divmod(sec, 60)
        return f"{m}:{s:02d}"

    @property
    def _zoom_step(self) -> float:
        return _ZOOM_STEP

    # ------------------------------------------------------------------ static kinds
    def _build_static(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        if self._kind == "image":
            lay.addWidget(self._build_image(), 1)
        elif self._kind == "text":
            lay.addWidget(self._build_text(), 1)
        elif self._kind == "pdf":
            lay.addWidget(self._build_pdf(), 1)
        elif self._kind == "zip":
            lay.addWidget(self._build_zip(), 1)
        else:
            lab = QLabel(t("preview.unsupported"))
            lab.setObjectName("muted")
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(lab, 1)
        return page

    def _build_image(self) -> QWidget:
        scene = QGraphicsScene()
        pix = QPixmap(str(self._path or ""))
        if pix.isNull():
            lab = QLabel(t("preview.unsupported"))
            lab.setObjectName("muted")
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            return lab
        item = QGraphicsPixmapItem(pix)
        scene.addItem(item)
        view = QGraphicsView(scene)
        view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        view.fitInView(item, Qt.AspectRatioMode.KeepAspectRatio)
        self._pix_item = item
        self._preview_view = view
        return view

    def _zoom(self, factor: float) -> None:
        view = getattr(self, "_preview_view", None)
        if view is not None:
            view.scale(factor, factor)

    def _zoom_fit(self) -> None:
        view = getattr(self, "_preview_view", None)
        item = getattr(self, "_pix_item", None)
        if view is not None and item is not None:
            view.fitInView(item, Qt.AspectRatioMode.KeepAspectRatio)

    def _build_text(self) -> QWidget:
        box = QPlainTextEdit()
        box.setReadOnly(True)
        try:
            if self._path is not None:
                size = self._path.stat().st_size
                with self._path.open("r", encoding="utf-8", errors="replace") as fh:
                    box.setPlainText(fh.read(_MAX_TEXT))
                if size > _MAX_TEXT:
                    box.appendPlainText("\n…\n" + t("preview.truncated"))
        except OSError:
            box.setPlainText(t("preview.unsupported"))
        return box

    def _build_pdf(self) -> QWidget:
        try:
            from PySide6.QtPdf import QPdfDocument
            from PySide6.QtPdfWidgets import QPdfView
        except Exception:  # pragma: no cover
            return self._fallback_lab(t("preview.unsupported"))
        doc = QPdfDocument(self)
        doc.load(str(self._path or ""))
        if doc.status() != QPdfDocument.Status.Ready:
            return self._fallback_lab(t("preview.pdf_error"))
        view = QPdfView()
        view.setDocument(doc)
        self._pdf_doc = doc
        return view

    def _build_zip(self) -> QWidget:
        lst = QListWidget()
        try:
            import zipfile

            with zipfile.ZipFile(str(self._path or "")) as zf:
                infos = sorted(zf.infolist(), key=lambda i: i.filename)
                total = 0
                for info in infos:
                    if info.is_dir():
                        continue
                    lst.addItem(f"{info.filename}  ·  {_human(info.file_size)}")
                    total += info.file_size
                head = QLabel(t("preview.zip_entries", count=str(len(infos))))

        except (zipfile.BadZipFile, OSError):
            return self._fallback_lab(t("preview.zip_error"))
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(head)
        lay.addWidget(lst, 1)
        return page

    def _fallback_lab(self, message: str) -> QLabel:
        lab = QLabel(message)
        lab.setObjectName("muted")
        lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return lab

    def _open_external(self) -> None:
        import sys

        if self._path is not None and sys.platform == "win32" and self._path.is_file():
            os.startfile(str(self._path), "open")  # noqa: S606
        elif self._path is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._path)))


def _human(size: int) -> str:
    size = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} GB"