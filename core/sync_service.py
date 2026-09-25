"""موتور همگام‌سازی (Sync): اسکن کانال/گروه/پیام‌های ذخیره‌شده و ایندکس محلی.

- Incremental Sync با ذخیره Cursor (آخرین Message ID).
- تشخیص پیام‌های حذف‌شده و علامت‌گذاری removed.
- FloodWait و Rate-Limit به صورت «تقاضای انتظار» به برنامه اعلام می‌شود.
- همه عملیات در حلقه asyncio اجرا می‌شود تا GUI بلاک نشود.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Optional

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.types import Channel, Chat, User

from core import telegram_adapter
from core.drive_manager import DriveManager
from core.index_store import IndexStore

logger = logging.getLogger(__name__)

Progress = Callable[[dict], None]


class SyncError(Exception):
    """خطای قابل نمایش فارسی در همگام‌سازی."""


class SyncThrottled(SyncError):
    """تلگرام خواستار انتظار شده است؛ پس از پایان، ادامه داده می‌شود."""

    def __init__(self, seconds: float):
        super().__init__(f"تلگرام از ما خواسته {int(seconds)} ثانیه صبر کنیم.")
        self.seconds = seconds


class SyncCancelled(SyncError):
    """همگام‌سازی توسط کاربر لغو شد."""


class SyncEngine:
    """همگام‌سازی یک یا چند Drive با کلاینت Telethon."""

    def __init__(
        self,
        store: IndexStore,
        drives: DriveManager,
        batch_size: int = 200,
        max_messages: int = 200_000,
    ):
        self.store = store
        self.drives = drives
        self.batch_size = max(20, int(batch_size))
        self.max_messages = max(100, int(max_messages))
        self._cancel_event: Optional[asyncio.Event] = None
        self._cancel_requested = False

    # ------------------------------------------------------------------ cancel
    def request_cancel(self) -> None:
        if self._cancel_event is not None:
            self._cancel_event.set()
        else:
            self._cancel_requested = True

    # ------------------------------------------------------------------ entity
    async def resolve_entity(self, client: TelegramClient, drive: dict):
        source = (drive.get("source_type") or "channel").lower()
        try:
            if source in ("saved", "account", "user-mine"):
                return await client.get_entity("me")
            key = (drive.get("username") or "").strip()
            if key:
                return await client.get_entity(key)
            peer_id = int(drive.get("peer_id", 0) or 0)
            if peer_id:
                return await client.get_entity(peer_id)
        except Exception as exc:
            raise SyncError(
                "شناسایی منبع این فضا ممکن نشد؛ مطمئن شوید دسترسی لازم به کانال/گروه را دارید."
            ) from exc
        raise SyncError("برای این فضا منبع تلگرامی مشخص نشده است.")

    # ------------------------------------------------------------------ sync
    async def sync_drive(
        self,
        client: TelegramClient,
        drive: dict,
        full: bool = False,
        progress: Optional[Progress] = None,
        account: str = "",
    ) -> dict:
        """همگام‌سازی فایل‌های یک Drive؛ آمار را برمی‌گرداند."""
        self._cancel_event = asyncio.Event()
        if self._cancel_requested:
            self._cancel_event.set()
            self._cancel_requested = False
        drive_id = drive["id"]
        old_cursor = int(drive.get("sync_cursor", 0) or 0)
        stats = {"scanned": 0, "added": 0, "updated": 0, "deleted": 0, "errors": 0, "throttled": 0.0}
        self.drives.set_status(drive_id, "syncing")

        def emit() -> None:
            if progress:
                progress(dict(stats))

        try:
            entity = await self.resolve_entity(client, drive)
            if not isinstance(entity, (Channel, Chat, User)):
                raise SyncError("منبع انتخاب‌شده معتبر نیست.")
            info = telegram_adapter.entity_info(entity)

            self.store.upsert_drive(
                {
                    **drive,
                    "peer_id": info.get("peer_id", 0) or 0,
                    "username": info.get("username", "") or (drive.get("username") or ""),
                    "title": info.get("title", "") or drive.get("title", ""),
                }
            )
            drive["username"] = (info.get("username") or "") or (drive.get("username") or "")

            source = (drive.get("source_type") or "channel").lower()
            chat_key: object = "me" if source in ("saved", "account", "user-mine") else entity

            if full:
                old_cursor = 0
            else:
                # تشخیص حذف پیام‌های اخیر: اگر تازه‌ترین پیام کوچک‌تر از Cursor بود
                try:
                    latest_msg = await client.get_messages(chat_key, limit=1)
                except FloodWaitError as exc:
                    raise SyncThrottled(float(exc.seconds or 30)) from exc
                if latest_msg:
                    latest_id = int(getattr(latest_msg[0], "id", 0) or 0)
                    if latest_id < old_cursor:
                        stats["deleted"] += self._mark_removed_range(drive_id, latest_id, old_cursor)
                        # پس از حذف پیام‌ها، Cursor باز به تازه‌ترین پیام موجود برمی‌گردد
                        old_cursor = latest_id

            highest = old_cursor
            buffer: list[dict] = []
            seen = 0

            try:
                async for msg in client.iter_messages(
                    chat_key,
                    reverse=False,
                    min_id=old_cursor if (not full and old_cursor > 0) else 0,
                    limit=self.max_messages if self.max_messages else None,
                ):
                    if self._cancel_event.is_set():
                        raise SyncCancelled("همگام‌سازی توسط کاربر متوقف شد.")
                    mid = int(getattr(msg, "id", 0) or 0)
                    if mid > highest:
                        highest = mid
                    seen += 1
                    stats["scanned"] += 1
                    info_dict = telegram_adapter.message_media_info(msg)
                    if info_dict is None:
                        continue
                    info_dict["drive_id"] = drive_id
                    info_dict["peer_username"] = drive.get("username") or ""
                    buffer.append(info_dict)
                    if len(buffer) >= self.batch_size:
                        self._flush(stats, drive_id, buffer)
                        emit()
            except FloodWaitError as exc:
                raise SyncThrottled(float(exc.seconds or 30)) from exc

            self._cancel_event = None
            if buffer:
                self._flush(stats, drive_id, buffer)

            new_cursor = highest if highest >= old_cursor else old_cursor
            if not full and highest < old_cursor:
                stats["deleted"] += self._mark_removed_range(drive_id, highest, old_cursor)
                new_cursor = highest
            self.drives.set_cursor(drive_id, new_cursor)

            emit()
            return stats
        except SyncCancelled:
            self.drives.set_status(drive_id, "cancelled")
            raise
        except SyncThrottled as exc:
            self.drives.set_status(drive_id, "throttled", str(exc))
            stats["throttled"] = exc.seconds
            emit()
            raise
        except SyncError:
            self.drives.set_status(drive_id, "error")
            raise
        except Exception as exc:
            logger.exception("خطا در همگام‌سازی فضای %s", drive_id)
            self.drives.set_status(drive_id, "error", str(exc))
            stats["errors"] += 1
            emit()
            raise SyncError("همگام‌سازی ناموفق بود؛ اتصال تلگرام را بررسی کنید.") from exc

    # ------------------------------------------------------------- helpers
    def _flush(self, stats: dict, drive_id: str, buffer: list[dict]) -> None:
        """ثبت گروهی فایل‌ها و شمارش added/updated."""
        if not buffer:
            return
        keys = self._existing_keys(drive_id, buffer)
        self.store.upsert_batch(buffer, drive_id)
        added = updated = 0
        for record in buffer:
            key = (drive_id, int(record.get("chat_id", 0) or 0), int(record.get("message_id", 0) or 0))
            if key in keys:
                updated += 1
            else:
                added += 1
        stats["added"] += added
        stats["updated"] += updated
        buffer.clear()

    def _existing_keys(self, drive_id: str, records: list[dict]) -> set[tuple]:
        message_ids = [int(r.get("message_id", 0) or 0) for r in records if r.get("message_id")]
        if not message_ids:
            return set()
        marks = ",".join("?" * len(message_ids))
        with self.store._lock:
            rows = self.store._conn.execute(
                f"SELECT chat_id, message_id FROM files "
                f"WHERE drive_id = ? AND message_id IN ({marks})",
                [drive_id, *message_ids],
            ).fetchall()
        return {(drive_id, int(r["chat_id"] or 0), int(r["message_id"] or 0)) for r in rows}

    def _mark_removed_range(self, drive_id: str, from_id: int, to_id: int) -> int:
        """پیام‌های بازه (from_id, to_id] را به‌عنوان حذف‌شده علامت می‌زند."""
        if to_id <= from_id:
            return 0
        with self.store._lock:
            cur = self.store._conn.execute(
                "UPDATE files SET removed = 1, updated_at = ? "
                "WHERE drive_id = ? AND message_id > ? AND message_id <= ?",
                (0.0, drive_id, from_id, to_id),
            )
            return cur.rowcount or 0