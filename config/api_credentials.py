"""سازگار با کد قبلی؛ مقادیر از config.edition (Build-time) تأمین می‌شود.

هیچ Secretی به‌صورت متن ساده در Source وجود ندارد؛ اعتبارنامه از طریق
Build-Profile / Environment / فایل secrets/ (gitignored) تأمین می‌شود.
"""

from __future__ import annotations

from config.edition import (  # noqa: F401
    API_HASH,
    API_ID,
    APP_SHORT_NAME,
    APP_VERSION,
    CURRENT_EDITION,
    DISPLAY_NAME,
)


def is_configured() -> bool:
    from config.edition import is_configured as _cfg

    return _cfg()
