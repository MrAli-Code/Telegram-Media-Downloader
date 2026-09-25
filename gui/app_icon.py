"""آیکون برنامه: بارگذاری از فایل یا رسم آیکون جایگزین."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRect, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

logger = logging.getLogger(__name__)

ACCENT = "#2aabee"


def _icon_paths() -> list[str]:
    candidates = []
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        candidates.append(str(Path(bundle) / "resources" / "icons" / "app.ico"))
    candidates.append(str(Path(__file__).resolve().parent.parent / "resources" / "icons" / "app.ico"))
    return candidates


def _draw_icon(size: int = 256) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # پس‌زمینه گرد
    path = QPainterPath()
    path.addRoundedRect(QRect(6, 6, size - 12, size - 12), size * 0.22, size * 0.22)
    painter.fillPath(path, QColor(ACCENT))

    # هواپیمای کاغذی (نماد تلگرام)
    plane = QPainterPath()
    plane.moveTo(size * 0.28, size * 0.30)
    plane.lineTo(size * 0.74, size * 0.20)
    plane.lineTo(size * 0.66, size * 0.64)
    plane.lineTo(size * 0.48, size * 0.52)
    plane.lineTo(size * 0.38, size * 0.64)
    plane.lineTo(size * 0.34, size * 0.50)
    plane.closeSubpath()
    painter.fillPath(plane, QColor("#ffffff"))

    # فلش دانلود زیر هواپیما
    pen = QPen(QColor("#ffffff"))
    pen.setWidth(round(size * 0.055))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    cy = size * 0.80
    painter.drawLine(QPointF(size * 0.30, cy), QPointF(size * 0.70, cy))
    path_arrow = QPainterPath()
    path_arrow.moveTo(size * 0.42, cy - size * 0.10)
    path_arrow.lineTo(size * 0.50, cy)
    path_arrow.lineTo(size * 0.58, cy - size * 0.10)
    painter.setBrush(QColor("#ffffff"))
    painter.drawPath(path_arrow)
    painter.end()
    return pm


def load_app_icon() -> QIcon:
    """بارگذاری آیکون فایل یا رسم آیکون جایگزین."""
    for candidate in _icon_paths():
        try:
            if Path(candidate).exists():
                return QIcon(candidate)
        except Exception:
            continue
    return QIcon(_draw_icon())
