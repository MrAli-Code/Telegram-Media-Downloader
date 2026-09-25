"""مدیریت حافظه کش: فایل‌های موقت .part، سهمیه فضا و پاکسازی امن."""

from __future__ import annotations

import logging
import os
from typing import Callable

logger = logging.getLogger(__name__)

PART_SUFFIX = ".part"


def scan_partials(root: str) -> list[dict]:
    """اسکن بازگشتی فایل‌های موقت .part در یک پوشه."""
    entries: list[dict] = []
    if not root or not os.path.isdir(root):
        return entries
    for base, _dirs, files in os.walk(root):
        for name in files:
            if not name.lower().endswith(PART_SUFFIX):
                continue
            path = os.path.join(base, name)
            try:
                stat = os.stat(path)
            except OSError:
                continue
            entries.append(
                {
                    "path": path,
                    "name": name,
                    "size": int(stat.st_size),
                    "mtime": float(stat.st_mtime),
                }
            )
    return entries


def is_partial(path: str) -> bool:
    return bool(path and path.lower().endswith(PART_SUFFIX))


class CacheManager:
    """محاسبه حجم فایل‌های موقت و پاکسازی قدیمی‌ترین‌ها برای رعایت سهمیه."""

    def __init__(self, directory: str, quota_bytes: int = 0):
        self.directory = directory or ""
        self.quota_bytes = max(0, int(quota_bytes or 0))

    def entries(self) -> list[dict]:
        return scan_partials(self.directory)

    def status(self) -> dict:
        entries = self.entries()
        total = sum(int(e["size"]) for e in entries)
        return {
            "count": len(entries),
            "total": total,
            "quota": self.quota_bytes,
            "directory": self.directory,
            "oldest": sorted(entries, key=lambda e: float(e["mtime"]))[:20],
        }

    def cleanup(
        self,
        quota_bytes: int | None = None,
        is_active: Callable[[str], bool] | None = None,
    ) -> dict:
        """حذف قدیمی‌ترین .partها تا رسیدن به سهمیه؛ فایل‌های در حال دانلود را رد می‌کند."""
        quota = self.quota_bytes if quota_bytes is None else max(0, int(quota_bytes or 0))
        entries = sorted(self.entries(), key=lambda e: float(e["mtime"]))
        total = sum(int(e["size"]) for e in entries)
        if total <= quota:
            return {"deleted": 0, "freed": 0, "checked": len(entries), "total": total}
        deleted = 0
        freed = 0
        for entry in entries:
            if total <= quota:
                break
            path = str(entry["path"])
            if is_active is not None and is_active(path):
                continue
            try:
                os.remove(path)
            except OSError as exc:
                logger.warning("حذف کش ناموفق بود: %s (%s)", path, exc)
                continue
            total -= int(entry["size"])
            freed += int(entry["size"])
            deleted += 1
        return {"deleted": deleted, "freed": freed, "checked": len(entries), "total": total}