"""آداپتور تلگرام: تبدیل پیام‌های Telethon به متادیتای مستقل (Dict).

بخش مرزی معماری: تایپ‌های Telethon نباید خارج از لایه Data پخش شوند.
فقط این ماژول و services/authentication با Telethon کار می‌کنند و بقیه برنامه
با Dictهای ساده سر و کار دارد.
"""

from __future__ import annotations

import logging
from typing import Any

from telethon.tl import types

from core.index_store import DL_REMOTE
from core.telegram_client import detect_kind

logger = logging.getLogger(__name__)

# رسانه‌هایی که در ایندکس ثبت می‌شوند
SUPPORTED_KINDS = {"video", "video_note", "audio", "voice", "photo", "document"}

_PHOTO_EXT = ".jpg"


def _document_identity(media: Any) -> tuple[str, str]:
    doc = getattr(media, "document", None)
    if doc is not None:
        return str(getattr(doc, "id", 0)), str(getattr(doc, "access_hash", 0))
    photo = getattr(media, "photo", None)
    if photo is not None:
        return str(getattr(photo, "id", 0)), str(getattr(photo, "access_hash", 0))
    return "", ""


def message_media_info(msg: types.Message) -> dict | None:
    """استخراج متادیتای قابل‌ایندکس از پیام؛ None اگر رسانه قابل‌ایندکسی نیست."""
    if msg.media is None:
        return None
    if isinstance(msg.media, types.MessageMediaUnsupported):
        return None
    kind = detect_kind(msg)
    if kind == "webpage" or kind not in SUPPORTED_KINDS:
        return None

    fobj = msg.file
    file_id, access_hash = _document_identity(msg.media)

    name = (fobj.name if fobj else None) or ""
    if not name:
        if kind == "photo":
            name = f"photo-{msg.id or 0}{_PHOTO_EXT}"
        else:
            name = f"media-{msg.id or 0}"
    size = int(fobj.size or 0) if fobj else 0
    mime = (fobj.mime_type or "") if fobj else ""
    duration = float(fobj.duration) if fobj and fobj.duration else None

    sender = getattr(msg, "sender", None)
    sender_id = int(getattr(msg, "sender_id", 0) or 0)
    sender_name = ""
    if sender is not None:
        sender_name = getattr(sender, "first_name", "") or ""
        last = getattr(sender, "last_name", "") or ""
        if last:
            sender_name = (sender_name + " " + last).strip()
        if not sender_name and getattr(sender, "username", None):
            sender_name = "@" + sender.username

    return {
        "chat_id": int(getattr(msg, "chat_id", 0) or 0),
        "message_id": int(getattr(msg, "id", 0) or 0),
        "file_id": file_id,
        "access_hash": access_hash,
        "file_name": name,
        "file_size": size,
        "mime_type": mime,
        "media_type": kind,
        "caption": (msg.message or "").strip(),
        "duration": duration,
        "message_date": float(msg.date.timestamp()) if msg.date else 0.0,
        "sender_id": sender_id,
        "sender_name": sender_name,
        "download_status": DL_REMOTE,
        "downloaded_bytes": 0,
    }


def entity_info(entity: Any) -> dict:
    """استخراج شناسه/نام/یوزرنیم یک موجودیت (channel/group/user)."""
    peer_id = int(getattr(entity, "id", 0) or 0)
    username = getattr(entity, "username", "") or ""
    title = ""
    if isinstance(entity, (types.Channel, types.Chat)):
        title = getattr(entity, "title", "") or ""
    elif isinstance(entity, types.User):
        title = (getattr(entity, "first_name", "") or "") + " " + (
            getattr(entity, "last_name", "") or ""
        )
        title = title.strip()
    return {
        "peer_id": peer_id,
        "username": username,
        "title": title or username or str(peer_id),
    }


def source_type_for_entity(entity: Any) -> str:
    if isinstance(entity, types.Channel):
        return "channel"
    if isinstance(entity, types.Chat):
        return "group"
    if isinstance(entity, types.User):
        return "user"
    return "channel"