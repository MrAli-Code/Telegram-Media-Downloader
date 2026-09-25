"""زمان‌بندی دانلود: تعیین بازه مجاز (پشتیبانی از بازه‌های شبانه)."""

from __future__ import annotations

from datetime import datetime


def parse_hhmm(value: str) -> int:
    """تبدیل "HH:MM" به دقیقه از نیمه‌شب؛ مقدار معتبر خارج از بازه = صفر."""
    value = (value or "").strip()
    try:
        hour, minute = value.split(":")
        h, m = int(hour), int(minute)
        if not (0 <= h <= 23 and 0 <= m <= 59):
            return 0
        return h * 60 + m
    except (ValueError, AttributeError):
        return 0


def now_minutes(now: datetime | None = None) -> int:
    dt = now or datetime.now()
    return dt.hour * 60 + dt.minute


def within_window(start: str, stop: str, now: datetime | None = None) -> bool:
    """آیا الان داخل بازه [start, stop) هستیم؟ بازه شبانه (stop <= start) را هم می‌فهمد."""
    s = parse_hhmm(start)
    e = parse_hhmm(stop)
    if s == e:
        return True  # نبود زمان‌بندی (بازه برابر)
    n = now_minutes(now)
    if e > s:
        return s <= n < e
    return n >= s or n < e


def window_label(start: str, stop: str) -> str:
    return f"{start.strip()} - {stop.strip()}"


def best_window_end(start: str, stop: str, now: datetime | None = None) -> int:
    """دقیقه تا پایان بازه فعلی (برای پست سرعت‌تر UI)."""
    s = parse_hhmm(start)
    e = parse_hhmm(stop)
    n = now_minutes(now)
    if s == e:
        return 24 * 60
    if e > s:
        return (e - n) % (24 * 60)
    if n >= s:
        return (24 * 60 + e - n) % (24 * 60)
    return (s - n) % (24 * 60)
