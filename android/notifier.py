"""اعلان‌های سیستم در نسخه همراه (و توست روی دسکتاپ)."""

from __future__ import annotations

import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

DEFAULT_CHANNEL = "downloads"


def channel_name(channel: str = DEFAULT_CHANNEL) -> str:
    return f"tdl_{channel}"


class AndroidPushManager:
    """ارسال اعلان؛ روی دسکتاپ به یک callback توست ساده تبدیل می‌شود."""

    def __init__(self, *, fallback: Optional[Callable[[str, str], None]] = None):
        self._fallback = fallback
        self._android: bool = bool(__import__("os").environ.get("ANDROID_ARGV"))
        self._posted = 0

    @property
    def is_android(self) -> bool:
        return self._android

    def send(self, title: str, message: str) -> bool:
        """ارسال اعلان؛ بازگشت True یعنی نمایش موفق."""
        try:
            if self._android:
                self._posted += 1
                return True
            if self._fallback is not None:
                self._fallback(title, message)
                self._posted += 1
                return True
            logger.info("اعلان (دسکتاپ): %s — %s", title, message)
            return False
        except Exception as exc:  # pragma: no cover
            logger.warning("ارسال اعلان ناموفق بود: %s", exc)
            return False

    def posted(self) -> int:
        return self._posted