"""ویجت‌های کمکی رابط کاربری: دکمه با نوع، اعلان (Toast)."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QEasingCurve, QEvent, QPropertyAnimation, Qt, QTimer
from PySide6.QtWidgets import QLabel, QPushButton, QWidget


def set_btn_type(btn: QPushButton, kind: str) -> None:
    """اعمال نوع دکمه برای استایل‌دهی پویا (primary/danger/success/ghost)."""
    btn.setProperty("btnType", kind)
    btn.style().unpolish(btn)
    btn.style().polish(btn)


class Toast(QLabel):
    """اعلان کوتاه نمایش داده‌شده روی پنجره اصلی."""

    MARGIN_BOTTOM = 56
    DURATION = 3200

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setWordWrap(True)
        self.setMaximumWidth(560)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setObjectName("toast")
        self.setStyleSheet(
            "QLabel#toast { background: #2b3344; color: #ffffff; border-radius: 12px;"
            " padding: 12px 20px; font-weight: 600; }"
        )
        self.hide()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)
        self._effect = None
        self._animation: QPropertyAnimation | None = None
        if parent is not None:
            parent.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if watched is self.parentWidget() and event.type() == QEvent.Type.Resize and self.isVisible():
            self._reposition()
        return super().eventFilter(watched, event)

    def show_toast(self, message: str) -> None:
        self.setText(message)
        self.adjustSize()
        self._reposition()
        self.show()
        self.raise_()
        self._fade_in()
        self._timer.start(self.DURATION)

    def _reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        self.adjustSize()
        x = (parent.width() - self.width()) // 2
        y = parent.height() - self.height() - self.MARGIN_BOTTOM
        self.move(x, y)

    def _fade_in(self) -> None:
        from PySide6.QtWidgets import QGraphicsOpacityEffect

        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, QByteArray(b"opacity"), self)
        anim.setDuration(180)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._animation = anim

    def _fade_out(self) -> None:
        effect = self.graphicsEffect()
        if effect is None:
            self.hide()
            return
        anim = QPropertyAnimation(effect, QByteArray(b"opacity"), self)
        anim.setDuration(220)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.finished.connect(self.hide)
        anim.start()
        self._animation = anim
