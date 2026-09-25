"""فایل ویژگی‌های ماژولار برنامه (Feature Flags).

قابلیت‌های سنگین به پشتِ این پرچم‌ها نگهداری می‌شوند تا برنامه اصلی حتی اگر
یک ماژول غیرفعال باشد، کاملاً پایدار بماند. مقدار هر پرچم می‌تواند با
متغیر محیطی TDL_FEATURES یا فایل config/_build_info.py بازنویسی شود.
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# پرچم‌های پیش‌فرض
# ---------------------------------------------------------------------------

DEFAULTS: dict[str, bool] = {
    # پشتیبان‌گیری خودکار از پوشه‌های ویندوز به تلگرام
    "ENABLE_BACKUP": True,
    # رمزنگاری اختیاری AES-256 (محتوا + متادیتا)
    "ENABLE_ENCRYPTION": True,
    # استریم ویدیو/صدا قبل از دانلود کامل
    "ENABLE_STREAMING": True,
    # نسخه اندروید (Companion)
    "ENABLE_ANDROID": False,
    # مدیریت فایل و ایندکس محلی (هسته اصلی File Manager)
    "ENABLE_FILE_MANAGER": True,
    # چند فضای Telegram (Multi-Drive)
    "ENABLE_MULTI_DRIVE": True,
    # همگام‌سازی خودکار
    "ENABLE_AUTO_SYNC": True,
    # سیستم Preview داخلی
    "ENABLE_PREVIEW": True,
    # تشخیص Duplicate بر پایه SHA-256
    "ENABLE_DEDUPE": True,
    # حالت حریم خصوصی (ماسک‌کردن نام فایل‌ها)
    "ENABLE_PRIVACY": True,
}

_OVERRIDES: dict[str, bool] = {}


def _load_overrides() -> None:
    if _OVERRIDES:
        return
    # اولویت: متغیر محیطی TDL_FEATURES="ENABLE_X=1,ENABLE_Y=0"
    raw = os.environ.get("TDL_FEATURES", "")
    for part in raw.split(","):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, _, value = part.partition("=")
        key = key.strip().upper()
        value = value.strip().lower()
        if key in DEFAULTS and value in ("1", "0", "true", "false", "yes", "no"):
            _OVERRIDES[key] = value in ("1", "true", "yes")
    # دوم: فایل Build-Time
    try:
        from config import _build_info  # noqa: PLC0415

        enabled = {
            k: v for k, v in vars(_build_info).items() if k.startswith("ENABLE_")
        }
        for key, value in enabled.items():
            if isinstance(value, bool):
                _OVERRIDES[key] = value
    except Exception:
        pass


def enabled(name: str) -> bool:
    """آیا یک قابلیت فعال است؟ (پیش‌فرض از DEFAULTS و با Override ممکن)."""
    _load_overrides()
    return _OVERRIDES.get(name, DEFAULTS.get(name, False))


def snapshot() -> dict[str, bool]:
    """خلاصه وضعیت همه پرچم‌ها برای نمایش در Dashboard/درباره."""
    _load_overrides()
    return {k: _OVERRIDES.get(k, v) for k, v in DEFAULTS.items()}