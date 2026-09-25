"""ساخت کلاینت تلگرام، بررسی پیام و استخراج اطلاعات رسانه."""

from __future__ import annotations

import logging
from typing import Any

from telethon import TelegramClient
from telethon.network.connection.tcpmtproxy import ConnectionTcpMTProxyRandomizedIntermediate
from telethon.sessions import StringSession
from telethon.tl import types

from core.models import MediaMeta, MediaResolveError
from utils.format_utils import format_datetime
from utils.link_utils import TelegramRef

logger = logging.getLogger(__name__)

KIND_LABELS = {
    "video": "ویدئو",
    "document": "سند",
    "audio": "صدا",
    "photo": "عکس",
    "video_note": "ویدئو کوتاه",
    "voice": "ویس",
    "webpage": "پیوند",
}

_MIME_EXT = {
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/x-matroska": ".mkv",
    "video/webm": ".webm",
    "video/x-msvideo": ".avi",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/ogg": ".ogg",
    "audio/opus": ".ogg",
    "audio/x-wav": ".wav",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
    "application/zip": ".zip",
    "text/plain": ".txt",
}

_KIND_EXT = {
    "video": ".mp4",
    "video_note": ".mp4",
    "audio": ".mp3",
    "voice": ".ogg",
    "photo": ".jpg",
    "document": "",
}


def _build_proxy_kwargs(proxy: dict | None) -> dict:
    """تبدیل تنظیمات پروکسی به آرگومان‌های TelegramClient.

    پشتیبانی از SOCKS5، HTTP و MTProto. خروجی خالی یعنی بدون پروکسی.
    """
    if not proxy or not proxy.get("enabled"):
        return {}
    proxy_type = str(proxy.get("type") or "socks5").lower()
    host = str(proxy.get("host") or "").strip()
    port = int(proxy.get("port") or 0)
    if not host or not port:
        return {}
    if proxy_type == "mtproto":
        secret = str(proxy.get("secret") or "").strip()
        if not secret:
            return {}
        return {
            "connection": ConnectionTcpMTProxyRandomizedIntermediate,
            "proxy": (host, port, secret),
        }
    username = str(proxy.get("username") or "").strip() or None
    password = str(proxy.get("password") or "").strip() or None
    kind = proxy_type if proxy_type in ("socks5", "socks4", "http") else "socks5"
    return {"proxy": (kind, host, port, True, username, password)}


def create_client(
    api_id: int,
    api_hash: str,
    session_string: str | None = None,
    proxy: dict | None = None,
    app_version: str | None = None,
) -> TelegramClient:
    """ساخت یک کلاینت Telethon با تنظیمات اتصال مجدد خودکار و پروکسی دلخواه."""
    session = StringSession(session_string) if session_string else StringSession()
    kwargs: dict[str, Any] = {
        "connection_retries": 10,
        "retry_delay": 2,
        "request_retries": 5,
        "auto_reconnect": True,
        "timeout": 45,
    }
    kwargs.update(_build_proxy_kwargs(proxy))
    return TelegramClient(session, api_id, api_hash, app_version=app_version, **kwargs)


def normalize_phone(phone: str) -> str:
    """حذف فاصله و کاراکترهای اضافی از شماره تلفن."""
    return "".join(ch for ch in phone if ch.isdigit() or ch == "+").strip()


def _mime_ext(mime: str) -> str:
    return _MIME_EXT.get((mime or "").lower(), "")


def _kind_ext(kind: str) -> str:
    return _KIND_EXT.get(kind, "")


def detect_kind(msg: types.Message) -> str:
    """تشخیص نوع رسانه از روی ویژگی‌های سند تلگرام."""
    m = msg.media
    if isinstance(m, types.MessageMediaPhoto):
        return "photo"
    if isinstance(m, types.MessageMediaDocument):
        for attr in m.document.attributes:
            if isinstance(attr, types.DocumentAttributeVideo):
                return "video_note" if getattr(attr, "round", False) else "video"
            if isinstance(attr, types.DocumentAttributeAudio):
                return "voice" if getattr(attr, "voice", False) else "audio"
        return "document"
    if isinstance(m, types.MessageMediaWebPage):
        return "webpage"
    return "document"


async def fetch_message(client: TelegramClient, ref: TelegramRef) -> types.Message:
    """بازیابی پیام هدف با احترام به دسترسی‌های حساب کاربر."""
    entity: Any
    if ref.kind == "channel":
        from telethon.tl.types import PeerChannel

        peer = PeerChannel(int(ref.value))
        try:
            entity = await client.get_entity(peer)
        except Exception as exc:
            logger.info("خطا در بازیابی موجودیت کانال %s: %r", ref.value, exc)
            raise MediaResolveError(
                "شناسه کانال خصوصی برای این حساب شناخته‌شده نیست؛ "
                "لطفاً ابتدا در تلگرام به کانال دسترسی داشته باشید یا از لینک با نام کاربری استفاده کنید."
            ) from exc
    else:
        entity = ref.value

    try:
        msg = await client.get_messages(entity, ids=ref.message_id)
    except Exception as exc:
        logger.info("بازیابی پیام %s (%s) ناموفق بود: %r", ref.value, ref.message_id, exc)
        raise

    if msg is None or getattr(msg, "id", None) != ref.message_id:
        raise MediaResolveError("پیام موردنظر یافت نشد یا شناسه آن نامعتبر است.")
    return msg


def build_media_meta(msg: types.Message) -> MediaMeta:
    """تبدیل پیام به متادیتای رسانه برای صف دانلود."""
    if msg.media is None:
        raise MediaResolveError("این پیام رسانه‌ای برای دانلود ندارد.")
    if isinstance(msg.media, types.MessageMediaUnsupported):
        raise MediaResolveError("رسانه این پیام توسط تلگرام پشتیبانی نمی‌شود.")

    kind = detect_kind(msg)
    if kind == "webpage":
        raise MediaResolveError("این پیام فقط یک پیوند است و رسانه قابل‌دانلودی ندارد.")

    fobj = msg.file
    name = (fobj.name if fobj else None) or ""
    if not name:
        ext = _mime_ext(fobj.mime_type if fobj else "") or _kind_ext(kind)
        name = f"دانلود-{msg.id}{ext}"
    size = int(fobj.size or 0) if fobj else 0
    mime = (fobj.mime_type or "") if fobj else ""
    duration = float(fobj.duration) if fobj and fobj.duration else None

    return MediaMeta(
        media=msg.media,
        name=name,
        size=size,
        mime=mime,
        kind=kind,
        duration=duration,
        date_text=format_datetime(msg.date),
    )


async def get_me_display(client: TelegramClient) -> str:
    """شماره تلفن (یا نام کاربری) برای نمایش در نوار وضعیت."""
    try:
        me = await client.get_me()
        if me is None:
            return ""
        return getattr(me, "phone", "") or getattr(me, "username", "") or ""
    except Exception:
        return ""
