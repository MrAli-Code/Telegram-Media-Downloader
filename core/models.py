"""مدل‌های داده مشترک بین هسته، سرویس‌ها و رابط کاربری."""

from __future__ import annotations

import html
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# وضعیت‌های دانلود
# ---------------------------------------------------------------------------

STATUS_PENDING = "pending"  # در انتظار
STATUS_RESOLVING = "resolving"  # در حال بررسی لینک
STATUS_DOWNLOADING = "downloading"  # در حال دریافت
STATUS_PAUSED = "paused"  # متوقف شده
STATUS_COMPLETED = "completed"  # تکمیل شد
STATUS_ERROR = "error"  # خطا
STATUS_CANCELLED = "cancelled"  # لغو شد

STATUS_LABELS: dict[str, str] = {
    STATUS_PENDING: "در انتظار",
    STATUS_RESOLVING: "در حال بررسی",
    STATUS_DOWNLOADING: "در حال دریافت",
    STATUS_PAUSED: "متوقف شده",
    STATUS_COMPLETED: "تکمیل شد",
    STATUS_ERROR: "خطا",
    STATUS_CANCELLED: "لغو شد",
}


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status)


# ---------------------------------------------------------------------------
# آیتم صف دانلود
# ---------------------------------------------------------------------------


@dataclass
class QueueItem:
    """یک آیتم در صف دانلود. فقط در ترد حلقه asyncio ویرایش می‌شود."""

    link: str
    order: int
    kind: str = "document"
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: str = STATUS_PENDING
    account: str = ""
    display_name: str = ""
    file_name: str = ""
    dest_dir: str = ""
    final_path: str = ""
    part_path: str = ""
    media_size: int = 0
    downloaded: int = 0
    speed: float = 0.0
    eta: float = 0.0
    elapsed: float = 0.0
    error: str = ""
    message_info: str = ""
    message_id: int = 0
    index_id: str = ""
    priority: int = 1
    pause_requested: bool = False
    cancel_requested: bool = False
    started_ts: float = 0.0
    _resolved: bool = False

    # ------------------------------------------------------- persistence
    def to_dict(self) -> dict:
        """فقط فیلدهای قابل ذخیره‌سازی (بدون اشیاء زنده)."""
        return {
            "id": self.id,
            "order": self.order,
            "link": self.link,
            "kind": self.kind,
            "status": self.status,
            "account": self.account,
            "display_name": self.display_name,
            "file_name": self.file_name,
            "dest_dir": self.dest_dir,
            "final_path": self.final_path,
            "part_path": self.part_path,
            "media_size": self.media_size,
            "downloaded": self.downloaded,
            "message_info": self.message_info,
            "message_id": self.message_id,
            "index_id": self.index_id,
            "priority": self.priority,
            "_resolved": self._resolved,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "QueueItem":
        item = cls(link=data.get("link", ""), order=int(data.get("order", 0)))
        item.id = data.get("id", item.id)
        for key in (
            "kind",
            "status",
            "account",
            "display_name",
            "file_name",
            "dest_dir",
            "final_path",
            "part_path",
            "message_info",
        ):
            setattr(item, key, data.get(key, "") or "")
        item.media_size = int(data.get("media_size", 0) or 0)
        item.downloaded = int(data.get("downloaded", 0) or 0)
        item.message_id = int(data.get("message_id", 0) or 0)
        item.index_id = data.get("index_id", "") or ""
        item.priority = int(data.get("priority", 1) or 1)
        item._resolved = bool(data.get("_resolved", False))
        return item

    # ------------------------------------------------------- gui snapshot
    def snapshot(self) -> dict:
        return {
            "id": self.id,
            "order": self.order,
            "link": self.link,
            "kind": self.kind,
            "status": self.status,
            "status_label": status_label(self.status),
            "display_name": html.escape(self.display_name or self.link),
            "file_name": self.file_name or self.link.rsplit("/", 1)[-1],
            "dest_dir": self.dest_dir,
            "final_path": self.final_path,
            "part_path": self.part_path,
            "media_size": self.media_size,
            "downloaded": self.downloaded,
            "speed": self.speed,
            "eta": self.eta,
            "elapsed": self.elapsed,
            "error": html.escape(self.error or ""),
            "message_info": html.escape(self.message_info or ""),
            "can_pause": self.status in (STATUS_DOWNLOADING,),
            "can_resume": self.status in (STATUS_PAUSED, STATUS_PENDING),
            "can_cancel": self.status in (STATUS_PENDING, STATUS_RESOLVING, STATUS_DOWNLOADING),
            "is_finished": self.status in (STATUS_COMPLETED, STATUS_ERROR, STATUS_CANCELLED),
            "priority": self.priority,
        }


# ---------------------------------------------------------------------------
# متادیتای رسانه پس از بررسی پیام
# ---------------------------------------------------------------------------


@dataclass
class MediaMeta:
    """اطلاعات رسانه استخراج‌شده از پیام تلگرام."""

    media: Any  # شیء رسانه Telethon (فقط در ترد حلقه معتبر است)
    name: str
    size: int
    mime: str
    kind: str
    duration: float | None
    date_text: str


# ---------------------------------------------------------------------------
# استثناهای داخلی
# ---------------------------------------------------------------------------


class MediaResolveError(Exception):
    """خطای قابل نمایش فارسی هنگام بررسی پیام."""


def generate_id() -> str:
    return uuid.uuid4().hex


def now_ts() -> float:
    return time.time()
