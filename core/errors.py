"""تبدیل خطاهای تلگرام/شبکه به پیام‌های فارسی قابل فهم برای کاربر."""

from __future__ import annotations

import asyncio
import errno
import logging

from telethon.errors import (
    AccessTokenExpiredError,
    AccessTokenInvalidError,
    AuthKeyUnregisteredError,
    ChannelInvalidError,
    ChannelPrivateError,
    FloodWaitError,
    MessageIdInvalidError,
    MessageNotModifiedError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    SessionExpiredError,
    SessionPasswordNeededError,
    UsernameNotOccupiedError,
    UserNotParticipantError,
)

from core.models import MediaResolveError

logger = logging.getLogger(__name__)

MSG_CHANNEL_PRIVATE = "این پیام خصوصی است و حساب فعلی شما به آن دسترسی ندارد."
MSG_MESSAGE_NOT_FOUND = "پیام موردنظر یافت نشد یا شناسه آن نامعتبر است."
MSG_SESSION_INVALID = "نشست تلگرام منقضی شده است. لطفاً دوباره وارد حساب خود شوید."
MSG_FLOOD = "درخواست‌ها بیش‌ازحد مجاز است؛ لطفاً لحظاتی بعد دوباره تلاش کنید."
MSG_NETWORK = "اتصال اینترنت قطع شده است؛ برنامه به‌صورت خودکار دوباره متصل می‌شود."
MSG_PHONE_CODE = "کد واردشده نامعتبر است؛ دوباره تلاش کنید."
MSG_PASSWORD = "رمز عبور دومرحله‌ای واردشده نامعتبر است."
MSG_DISK_FULL = "فضای دیسک کافی نیست."
MSG_PERMISSION = "اجازه نوشتن در پوشه مقصد وجود ندارد."
MSG_TIMEOUT = "ارتباط با تلگرام به موقع برقرار نشد؛ دوباره تلاش کنید."
MSG_UNKNOWN = "خطای غیرمنتظره‌ای رخ داد؛ جزئیات در گزارش ثبت شده است."


def flood_wait_message(seconds: float) -> str:
    return f"{MSG_FLOOD} (صبر: {int(seconds)} ثانیه)"


def friendly_error(exc: BaseException) -> str:
    """تبدیل استثنا به پیام فارسی قابل نمایش."""
    if isinstance(exc, MediaResolveError):
        return str(exc)
    if isinstance(exc, FloodWaitError):
        return flood_wait_message(int(getattr(exc, "seconds", 0)))
    if isinstance(exc, (ChannelPrivateError, UserNotParticipantError, ChannelInvalidError)):
        return MSG_CHANNEL_PRIVATE
    if isinstance(exc, (MessageIdInvalidError, UsernameNotOccupiedError, AccessTokenExpiredError)):
        return MSG_MESSAGE_NOT_FOUND
    if isinstance(exc, (AuthKeyUnregisteredError, SessionExpiredError)):
        return MSG_SESSION_INVALID
    if isinstance(exc, PhoneCodeInvalidError):
        return MSG_PHONE_CODE
    if isinstance(exc, PhoneCodeExpiredError):
        return "کد واردشده منقضی شده است؛ کد جدید بگیرید."
    if isinstance(exc, SessionPasswordNeededError):
        return MSG_PASSWORD
    if isinstance(exc, AccessTokenInvalidError):
        return "توکن دسترسی نامعتبر است."
    if isinstance(exc, MessageNotModifiedError):
        return MSG_MESSAGE_NOT_FOUND

    # خطاهای شبکه و سیستم
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return MSG_TIMEOUT
    if isinstance(
        exc, (ConnectionError, ConnectionAbortedError, ConnectionResetError, ConnectionRefusedError)
    ):
        return MSG_NETWORK
    if isinstance(exc, OSError):
        err = getattr(exc, "errno", None)
        if err in (errno.ENOSPC, 28, 39):
            return MSG_DISK_FULL
        if err in (errno.EACCES, errno.EPERM, 13, 5):
            return MSG_PERMISSION
        if err in (errno.ECONNRESET, errno.ETIMEDOUT, errno.ENETUNREACH, errno.ECONNABORTED, 10053, 10060):
            return MSG_NETWORK
        return str(exc)
    logger.debug("خطای نگاشت‌نشده: %r", exc)
    return str(exc) if str(exc) else MSG_UNKNOWN
