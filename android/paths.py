"""مسیرهای داده در نسخه همراه اندروید (و معادل دسکتاپ برای آزمون)."""

from __future__ import annotations

import os
from pathlib import Path

APP_DIR_NAME = "TelegramDownloader"


def data_dir(base: str | None = None) -> str:
    """پوشه داده برنامه (اندروید: filesDir؛ دسکتاپ: APPDATA)."""
    if base:
        return str(Path(base) / APP_DIR_NAME)
    android = os.environ.get("ANDROID_DATA")
    if android:
        return str(Path(android) / APP_DIR_NAME)
    return str(Path(os.environ.get("APPDATA", str(Path.home()))) / APP_DIR_NAME)


def cache_dir(base: str | None = None) -> str:
    """پوشه حافظه کش (قطعات دانلود و فایل‌های موقت)."""
    if base:
        return str(Path(base) / "cache")
    android = os.environ.get("ANDROID_CACHE")
    if android:
        return str(Path(android) / APP_DIR_NAME)
    local = os.environ.get("LOCALAPPDATA", data_dir())
    return str(Path(local) / APP_DIR_NAME / "cache")


def downloads_dir(base: str | None = None) -> str:
    """پوشه دانلود عمومی دستگاه (Shared Downloads)."""
    if base:
        return str(Path(base) / "Downloads")
    external = os.environ.get("EXTERNAL_STORAGE")
    if external:
        return str(Path(external) / "Download")
    return str(Path.home() / "Downloads")


def log_dir(base: str | None = None) -> str:
    return str(Path(cache_dir(base)) / "logs")