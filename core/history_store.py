"""ذخیره تاریخچه دانلودها (JSON) + آمارکلی.

جدا از صف دانلود، هر نتیجه نهایی (کامل/خطا/لغو) در تاریخچه ثبت می‌شود تا
کاربر بتواند فایل را باز کند یا آمار کلی ببیند.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from utils.file_utils import ensure_dir

logger = logging.getLogger(__name__)

STATUS_COMPLETED = "completed"
STATUS_ERROR = "error"
STATUS_CANCELLED = "cancelled"

MAX_ENTRIES = 5000


class HistoryStore:
    """ذخیره‌سازی سبک تاریخچه دانلودها در فایل history.json."""

    def __init__(self, path: Path | None = None, data_dir: Path | None = None):
        from config.settings import DEFAULT_DATA_DIR  # noqa: PLC0415

        self.data_dir = data_dir or DEFAULT_DATA_DIR
        self.path = path or self.data_dir / "history.json"
        ensure_dir(str(self.data_dir))
        self._entries: list[dict] = []

    def load(self) -> None:
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self._entries = [e for e in data if isinstance(e, dict)]
        except Exception as exc:
            logger.warning("خواندن تاریخچه ناموفق بود: %s", exc)
            self._entries = []

    def save(self) -> None:
        ensure_dir(str(self.path.parent))
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._entries, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            tmp.replace(self.path)
        except OSError:  # pragma: no cover
            import os  # noqa: PLC0415

            os.replace(str(tmp), str(self.path))

    def add(
        self,
        filename: str,
        size: int,
        status: str,
        source: str,
        save_path: str,
    ) -> dict | None:
        """ثبت یک نتیجه نهایی؛ None برمی‌گرداند اگر قبلاً ثبت شده باشد."""
        if status not in (STATUS_COMPLETED, STATUS_ERROR, STATUS_CANCELLED):
            return None
        entry: dict[str, Any] = {
            "uid": f"{int(datetime.now().timestamp() * 1000)}-{abs(hash(filename) % 10**6)}",
            "filename": filename,
            "date": datetime.now().isoformat(timespec="seconds"),
            "size": int(size or 0),
            "status": status,
            "source": source,
            "save_path": save_path,
        }
        self._entries.insert(0, entry)
        if len(self._entries) > MAX_ENTRIES:
            self._entries = self._entries[:MAX_ENTRIES]
        self.save()
        return entry

    def all(self) -> list[dict]:
        return list(self._entries)

    def remove(self, uid: str) -> bool:
        before = len(self._entries)
        self._entries = [e for e in self._entries if e.get("uid") != uid]
        if len(self._entries) != before:
            self.save()
            return True
        return False

    def clear(self) -> None:
        self._entries = []
        self.save()

    def search(self, query: str) -> list[dict]:
        q = (query or "").strip().lower()
        if not q:
            return self.all()
        return [e for e in self._entries if q in (e.get("filename") or "").lower()]

    def totals(self) -> dict:
        """آمار کلی: تعداد و مجموع حجم فایل‌های کامل‌شده و ناموفق."""
        completed_count = 0
        completed_size = 0
        failed_count = 0
        for e in self._entries:
            if e.get("status") == STATUS_COMPLETED:
                completed_count += 1
                completed_size += int(e.get("size") or 0)
            elif e.get("status") == STATUS_ERROR:
                failed_count += 1
        return {
            "completed_count": completed_count,
            "completed_size": completed_size,
            "failed_count": failed_count,
        }
