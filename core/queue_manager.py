"""مدیر صف دانلود: ماشین حالت آیتم‌ها و برنامه‌ریز دانلود همزمان."""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Awaitable, Callable, Optional

from core.downloader import CancelInterrupt, PauseInterrupt
from core.errors import friendly_error
from core.models import (
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_DOWNLOADING,
    STATUS_ERROR,
    STATUS_PAUSED,
    STATUS_PENDING,
    STATUS_RESOLVING,
    QueueItem,
)
from utils.format_utils import monotonic

logger = logging.getLogger(__name__)


class ItemError(Exception):
    """خطای قابل نمایش فارسی مرتبط با آیتم دانلود."""


class SkipExisting(ItemError):
    """فایل از قبل موجود است و کاربر گزینه «رد کردن» را انتخاب کرده است."""

    def __init__(self, message: str = ""):
        super().__init__(message)
        self.message = message


Resolver = Callable[[QueueItem], Awaitable[Optional[object]]]
Downloader = Callable[[QueueItem, object], Awaitable[None]]
Notifier = Callable[[QueueItem], None]


class QueueManager:
    """صف دانلود با پشتیبانی از اجرای همزمان چند دانلود و وقفه/ادامه."""

    def __init__(self, concurrency: int = 2):
        self.concurrency = max(1, int(concurrency))
        self.resolver: Optional[Resolver] = None
        self.downloader: Optional[Downloader] = None
        self.notifier: Optional[Notifier] = None

        self._items: dict[str, QueueItem] = {}
        self._order: list[str] = []
        self._pending: deque[QueueItem] = deque()
        self._running = 0

    # ------------------------------------------------------------------ queries
    def item(self, item_id: str) -> QueueItem | None:
        return self._items.get(item_id)

    def ordered_items(self) -> list[QueueItem]:
        return [self._items[i] for i in self._order if i in self._items]

    def active_count(self) -> int:
        return self._running

    def pending_count(self) -> int:
        return sum(1 for i in self._order if self._items[i].status == STATUS_PENDING)

    # ------------------------------------------------------------------ mutation
    def add(self, item: QueueItem) -> None:
        if item.id in self._items:
            return
        self._items[item.id] = item
        self._order.append(item.id)
        if item.status == STATUS_PENDING:
            self._pending.append(item)
            self._pump()

    def enqueue(self, item_id: str) -> None:
        item = self._items.get(item_id)
        if not item or item.status in (STATUS_COMPLETED, STATUS_CANCELLED):
            return
        item.pause_requested = False
        item.status = STATUS_PENDING
        self._pending.append(item)
        if self.notifier:
            self.notifier(item)
        self._pump()

    def pause(self, item_id: str) -> None:
        item = self._items.get(item_id)
        if not item:
            return
        item.pause_requested = True
        if item.status == STATUS_PENDING:
            item.status = STATUS_PAUSED
            if self.notifier:
                self.notifier(item)

    def resume(self, item_id: str) -> None:
        item = self._items.get(item_id)
        if item and item.status == STATUS_PAUSED:
            item.pause_requested = False
            self.enqueue(item_id)

    def cancel(self, item_id: str) -> None:
        item = self._items.get(item_id)
        if not item:
            return
        item.cancel_requested = True
        item.pause_requested = False
        if item.status == STATUS_PENDING:
            item.status = STATUS_CANCELLED
            if self.notifier:
                self.notifier(item)

    def remove(self, item_id: str) -> QueueItem | None:
        item = self._items.pop(item_id, None)
        if item_id in self._order:
            self._order.remove(item_id)
        self._pending = deque(i for i in self._pending if i.id != item_id)
        return item

    def move_to_front(self, item_id: str) -> bool:
        """انتقال آیتم صف به ابتدای صف انتظار (بعد از دانلودهای در حال اجرا)."""
        item = self._items.get(item_id)
        if not item or item.status != STATUS_PENDING:
            return False
        self._pending = deque([i for i in self._pending if i.id != item_id])
        self._pending.appendleft(item)
        if item_id in self._order:
            self._order.remove(item_id)
            self._order.insert(0, item_id)
        return True

    def set_priority(self, item_id: str, priority: int) -> bool:
        """تنظیم اولویت آیتم (۰=کم، ۱=عادی، ۲=بالا)."""
        item = self._items.get(item_id)
        if not item:
            return False
        item.priority = max(0, min(2, int(priority)))
        self._pump()
        return True

    def set_concurrency(self, value: int) -> None:
        self.concurrency = max(1, int(value))
        self._pump()

    # ------------------------------------------------------------------ scheduler
    def _pump(self) -> None:
        while self._running < self.concurrency and self._pending:
            current = max(
                self._pending,
                key=lambda it: (it.priority, -self._order.index(it.id)),
            )
            self._pending.remove(current)
            if current.status != STATUS_PENDING or current.cancel_requested:
                continue
            self._running += 1
            try:
                asyncio.get_running_loop().create_task(self._run(current))
            except RuntimeError:
                logger.error("حلقه asyncio اجرا نیست؛ آیتم %s برنامه‌ریزی نشد", current.id)
                self._running -= 1
                self._pending.append(current)
                break

    async def _run(self, item: QueueItem) -> None:
        item.started_ts = monotonic()
        item.status = STATUS_RESOLVING
        try:
            if self.notifier:
                self.notifier(item)
            meta = None
            if self.resolver:
                meta = await self.resolver(item)
            if item.cancel_requested:
                raise CancelInterrupt()
            if item.pause_requested:
                raise PauseInterrupt()
            if meta is None:
                raise ItemError("این پیام رسانه قابل‌دانلودی ندارد.")

            item.status = STATUS_DOWNLOADING
            if self.notifier:
                self.notifier(item)
            if self.downloader:
                await self.downloader(item, meta)
            item.status = STATUS_COMPLETED
            logger.info("دانلود آیتم %s (فایل %s) تکمیل شد", item.id, item.file_name)
        except PauseInterrupt:
            item.status = STATUS_PAUSED
        except CancelInterrupt:
            item.status = STATUS_CANCELLED
        except SkipExisting as exc:
            item.status = STATUS_COMPLETED
            item.error = exc.message
        except ItemError as exc:
            item.status = STATUS_ERROR
            item.error = str(exc)
        except Exception as exc:  # noqa: BLE001
            item.status = STATUS_ERROR
            item.error = friendly_error(exc)
            logger.exception("خطا در دانلود آیتم %s", item.id)
        finally:
            if self.notifier:
                self.notifier(item)
            self._running -= 1
            self._pump()
