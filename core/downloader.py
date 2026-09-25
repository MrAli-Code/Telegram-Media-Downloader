"""موتور دانلود بخش‌بخشی با قابلیت Pause/Resume/Cancel و اتصال مجدد."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Callable

from core.models import QueueItem

logger = logging.getLogger(__name__)


class PauseInterrupt(Exception):
    """توقف موقت دانلود (نگه‌داشتن فایل ناقص)."""


class CancelInterrupt(Exception):
    """لغو کامل دانلود (حذف فایل ناقص)."""


class DownloadEngine:
    """دانلود با iter_download از Offset مناسب برای ادامه/توقف قابل اطمینان."""

    def __init__(
        self,
        request_size: int = 1024 * 1024,
        throttle: float = 0.12,
        max_retries: int = 6,
        fsync_interval: int = 16 * 1024 * 1024,
        max_rate_bytes: float = 0.0,
    ):
        self.request_size = request_size
        self.throttle = throttle
        self.max_retries = max_retries
        self.fsync_interval = fsync_interval
        # 0 یعنی بدون محدودیت؛ در غیر این صورت حداکثر بایت/ثانیه
        self.max_rate_bytes = max_rate_bytes

    async def run(
        self,
        client,
        media,
        part_path: str,
        item: QueueItem,
        notify: Callable[[QueueItem], None],
    ) -> int:
        """دانلود را از انتهای فایل .part ادامه می‌دهد؛ تعداد بایت دانلودشده را برمی‌گرداند."""
        os.makedirs(os.path.dirname(part_path) or ".", exist_ok=True)
        offset = os.path.getsize(part_path) if os.path.exists(part_path) else 0
        total = item.media_size
        if not total:
            total = int(getattr(media, "size", 0) or 0)

        item.downloaded = offset
        start = time.monotonic()
        last_time = start
        last_bytes = offset
        ema = 0.0
        last_emit = 0.0
        last_fsync = offset
        retries = 0
        rate_budget = 0.0
        rate_last = start

        def _interrupt_check() -> None:
            if item.cancel_requested:
                raise CancelInterrupt()
            if item.pause_requested:
                raise PauseInterrupt()

        try:
            with open(part_path, "ab") as fh:
                while True:
                    try:
                        async for chunk in client.iter_download(
                            media, offset=offset, request_size=self.request_size
                        ):
                            fh.write(chunk)
                            offset += len(chunk)

                            _interrupt_check()

                            if self.max_rate_bytes > 0:
                                now_r = time.monotonic()
                                rate_budget += (now_r - rate_last) * self.max_rate_bytes
                                rate_last = now_r
                                if rate_budget < len(chunk):
                                    await asyncio.sleep((len(chunk) - rate_budget) / self.max_rate_bytes)
                                    rate_budget = 0.0
                                else:
                                    rate_budget -= len(chunk)

                            now = time.monotonic()
                            dt = now - last_time
                            if dt >= 0.8:
                                instant = (offset - last_bytes) / dt
                                ema = instant if ema <= 0 else ema * 0.7 + instant * 0.3
                                last_time = now
                                last_bytes = offset

                            item.downloaded = offset
                            item.speed = ema
                            item.eta = ((total - offset) / ema) if (ema > 0 and total) else 0.0
                            item.elapsed = now - start
                            if now - last_emit >= self.throttle:
                                last_emit = now
                                notify(item)
                            if offset - last_fsync >= self.fsync_interval:
                                fh.flush()
                                os.fsync(fh.fileno())
                                last_fsync = offset
                            if total and offset >= total:
                                break
                        break
                    except (
                        ConnectionError,
                        ConnectionAbortedError,
                        ConnectionResetError,
                        asyncio.TimeoutError,
                        TimeoutError,
                    ):
                        _interrupt_check()
                        retries += 1
                        if retries > self.max_retries:
                            logger.warning("دانلود %s پس از %d تلاش قطع شد", item.id, retries)
                            raise
                        fh.flush()
                        wait = min(2.0**retries, 15.0)
                        logger.info("قطع اتصال هنگام دانلود %s؛ تلاش مجدد در %.1f ثانیه", item.id, wait)
                        await asyncio.sleep(wait)
                fh.flush()
                os.fsync(fh.fileno())
        finally:
            item.downloaded = offset
            item.speed = ema
            item.elapsed = time.monotonic() - start
            notify(item)

        return offset
