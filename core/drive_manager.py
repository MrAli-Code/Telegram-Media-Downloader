"""مدیریت فضاهای Telegram (Drive) و پوشه‌های مجازی (لایه Domain).

هر Drive به یک منبع تلگرامی متصل است (Channel/Group/Saved Messages) و ایندکس
مستقل از فایل‌ها در ایندکس محلی دارد. برای لینک‌دهی فایل‌ها به صف دانلود،
مسیرهای tgdrive:// ساخته می‌شود تا موتور دانلود فقط بر اساس شناسه ایندکس کار کند.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable

from core.index_store import (
    IndexStore,
    now_ts,
)

logger = logging.getLogger(__name__)

TGDRIVE_SCHEME = "tgdrive://"


class DriveManagerError(Exception):
    """خطای قابل نمایش مدیریت فضاها."""


class DriveManager:
    """عملیات فضاها، پوشه‌ها و دسترسی فایل‌های ایندکس‌شده."""

    def __init__(self, store: IndexStore):
        self.store = store

    # ------------------------------------------------------------------ drives
    def add_drive(self, payload: dict) -> dict:
        drive = dict(payload)
        drive_id = self.store.upsert_drive(drive)
        rec = self.store.get_drive(drive_id) or {}
        return rec

    def drives_with_stats(self) -> list[dict]:
        out = []
        for drive in self.store.list_drives():
            merged = dict(drive)
            merged.update(self.store.drive_stats(drive["id"]))
            out.append(merged)
        return out

    def get(self, drive_id: str) -> dict | None:
        return self.store.get_drive(drive_id)

    def remove(self, drive_id: str) -> bool:
        return self.store.remove_drive(drive_id)

    def set_status(self, drive_id: str, status: str, error: str = "") -> None:
        self.store.set_drive_status(drive_id, status, error)

    def set_cursor(self, drive_id: str, cursor: int) -> None:
        self.store.set_drive_cursor(drive_id, cursor)

    # ------------------------------------------------------------------ folders
    def create_folder(self, drive_id: str, name: str, parent_id: str = "") -> dict:
        return self.store.create_folder(drive_id, name, parent_id)

    def rename_folder(self, folder_id: str, new_name: str) -> bool:
        return self.store.rename_folder(folder_id, new_name)

    def move_folder(self, folder_id: str, new_parent_id: str) -> bool:
        return self.store.move_folder(folder_id, new_parent_id)

    def delete_folder(self, folder_id: str) -> bool:
        return self.store.delete_folder(folder_id)

    def folders(self, drive_id: str) -> list[dict]:
        return self.store.list_folders(drive_id)

    def folder_files_count(self, drive_id: str) -> dict[str, int]:
        """تعداد فایل هر پوشه برای نمایش در درخت پوشه‌ها."""
        counts: dict[str, int] = {}
        with self.store._lock:
            rows = self.store._conn.execute(
                "SELECT folder_id, COUNT(*) AS c FROM files WHERE drive_id = ? "
                "AND trashed = 0 AND hidden = 0 GROUP BY folder_id",
                (drive_id,),
            ).fetchall()
        for r in rows:
            counts[r["folder_id"]] = int(r["c"])
        return counts

    # ------------------------------------------------------------------ files
    def files(self, drive_id: str, folder_id: str = "", page: int = 1, page_size: int = 200, sort: str = "name", ascending: bool = True) -> list[dict]:
        return self.store.list_files(
            drive_id=drive_id, folder_id=folder_id, sort=sort, ascending=ascending,
            limit=page_size, offset=(max(1, page) - 1) * page_size,
        )

    def favorites(self, drive_id: str | None = None) -> list[dict]:
        return self.store.list_files(
            drive_id=drive_id, include_trash=False, limit=10**6,
        ) and self._filter_flags(drive_id, favorite=1)

    def trash(self, drive_id: str | None = None) -> list[dict]:
        return self._filter_flags(drive_id, trashed=1)

    def _filter_flags(self, drive_id: str | None, **flags: int) -> list[dict]:
        where = " AND ".join(f"{k} = ?" for k in flags)
        params: list[Any] = [*flags.values()]
        if drive_id:
            where = "drive_id = ? AND " + where
            params.insert(0, drive_id)
        with self.store._lock:
            rows = self.store._conn.execute(
                f"SELECT * FROM files WHERE {where} ORDER BY message_date DESC", params
            ).fetchall()
        return [dict(r) for r in rows]

    def recent(self, drive_id: str | None = None, limit: int = 20) -> list[dict]:
        return self.store.list_files(
            drive_id=drive_id, sort="date", ascending=False, limit=limit,
        )

    def search(self, query: str, drive_id: str | None = None, limit: int = 200) -> list[dict]:
        return self.store.search(query, drive_id=drive_id, limit=limit)

    def mark(self, file_ids: Iterable[str], favorite=None, hidden=None, archived=None, trashed=None) -> int:
        return self.store.set_file_flags(list(file_ids), favorite, hidden, archived, trashed)

    def move_to_folder(self, file_ids: Iterable[str], folder_id: str) -> int:
        return self.store.move_files_to_folder(list(file_ids), folder_id)

    def delete_records(self, file_ids: Iterable[str]) -> int:
        return self.store.delete_files(list(file_ids))

    def rename_file(self, file_id: str, new_name: str) -> bool:
        return self.store.rename_file(file_id, new_name)

    def stats(self) -> dict:
        return self.store.totals()

    # ------------------------------------------------------------------ download link
    def link_for_file(self, file_rec: dict, drive: dict | None = None) -> str:
        """ساخت لینک tgdrive:// برای اضافه‌کردن فایل ایندکس‌شده به صف دانلود."""
        if not file_rec:
            return ""
        drive = drive or self.store.get_drive(file_rec.get("drive_id") or "")
        if not drive:
            return ""
        return f"{TGDRIVE_SCHEME}{drive['id']}/{file_rec['id']}"

    def parse_drive_link(self, link: str) -> tuple[str, str] | None:
        """تجزیه لینک tgdrive:// و بازگرداندن (drive_id, file_id)."""
        if not link.startswith(TGDRIVE_SCHEME):
            return None
        rest = link[len(TGDRIVE_SCHEME):].strip()
        parts = rest.split("/", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            return None
        return parts[0], parts[1]

    # ------------------------------------------------------------------ integrity
    def verify_file(self, file_id: str) -> dict:
        return self.store.verify_file_health(file_id)

    def compute_sha256(self, path: str) -> str | None:
        return self.store.compute_sha256(path)

    def count_incomplete(self) -> int:
        return len(self.store.find_incomplete_local())


def default_drive_payload(name: str, source_type: str = "channel", account: str = "") -> dict:
    return {
        "name": name,
        "source_type": source_type,
        "account": account,
        "auto_sync_enabled": True,
        "auto_sync_minutes": 15,
        "created_at": now_ts(),
        "updated_at": now_ts(),
    }