"""بسته همراه اندروید (Companion).

این بسته صرفاً اسکلت قابلیت نسخه همراه است و روی دسکتاپ هم اجرا می‌شود.
فعال‌سازی نهایی با پرچم ENABLE_ANDROID در config/features.py کنترل می‌شود.
"""

from __future__ import annotations

__all__ = ["paths", "share_action", "worker", "notifier"]