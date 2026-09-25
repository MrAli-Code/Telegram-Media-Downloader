"""دریافت لینک‌های دانلود از اشتراک‌گذاری (Share / Send To) در اندروید."""

from __future__ import annotations

import os
from pathlib import Path

SUPPORTED_HOSTS = ("t.me", "telegram.me")
PROTOCOL_PREFIXES = ("tgdrive://", "telegram://")


def is_supported_share(item: str) -> bool:
    """آیا یک متن اشتراک‌گذاری‌شده لینک دانلواد تلگرام است؟"""
    item = (item or "").strip()
    if not item:
        return False
    lowered = item.lower()
    for host in SUPPORTED_HOSTS:
        if lowered.startswith(f"https://{host}/") or lowered.startswith(f"http://{host}/"):
            return True
        if lowered.startswith(f"{host}/"):
            return True
    for prefix in PROTOCOL_PREFIXES:
        if item.lower().startswith(prefix):
            return True
    return False


def share_links(items: list[str]) -> list[str]:
    """استخراج لینک‌های معتبر از لیست متون/مسیرهای اشتراک‌گذاری‌شده."""
    links: list[str] = []
    seen: set[str] = set()
    for item in items or []:
        if isinstance(item, os.PathLike):
            item = str(item)
        if not isinstance(item, str):
            continue
        item = item.strip()
        if not item:
            continue
        # فایل محلی (Send To / URI) — در مرحله نهایی به tgdrive ترجمه می‌شود
        if Path(item).is_file():
            continue
        if not is_supported_share(item):
            continue
        normalized = _normalize(item)
        if normalized and normalized not in seen:
            seen.add(normalized)
            links.append(normalized)
    return links


def _normalize(item: str) -> str | None:
    lowered = item.lower()
    if lowered.startswith("telegram://"):
        rest = item[len("telegram://") :]
        if rest.lower().startswith("t.me/"):
            return f"https://{rest.split('?', 1)[0]}"
        return None
    if lowered.startswith("tgdrive://"):
        return item.split("?", 1)[0]
    if lowered.startswith(("https://", "http://")):
        return f"https://{item.split('?', 1)[0].split('http://', 1)[-1]}" if lowered.startswith(
            "http://"
        ) else item.split("?", 1)[0]
    # بدون پروتکل (t.me/...)
    return f"https://{item.split('?', 1)[0]}"