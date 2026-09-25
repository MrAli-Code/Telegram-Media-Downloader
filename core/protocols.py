"""لایه انتزاع بک‌اند تلگرام (استاندارد برای تعویض آسان در آینده)."""

from __future__ import annotations

import importlib
from typing import Any, Protocol, TypedDict, runtime_checkable


class MediaAttachment(TypedDict):
    kind: str
    mime: str
    size: int
    name: str
    file_id: str
    access_hash: int
    dc_id: int


@runtime_checkable
class ClientLike(Protocol):
    """سطح کلاینت تلگرامی مصرف‌شده توسط موتورها (استقاده از اردک‌تایپ)."""

    async def connect(self) -> None: ...

    async def disconnect(self) -> None: ...

    def is_connected(self) -> bool: ...

    async def is_user_authorized(self) -> bool: ...

    async def get_me(self) -> Any: ...

    async def get_entity(self, peer: Any) -> Any: ...

    async def get_messages(self, entity: Any, **kwargs: Any) -> Any: ...

    def iter_messages(self, entity: Any, **kwargs: Any) -> Any: ...

    def iter_download(self, media: Any, **kwargs: Any) -> Any: ...

    async def send_code_request(self, phone: str) -> None: ...

    async def sign_in(self, *args: Any, **kwargs: Any) -> Any: ...

    async def log_out(self) -> None: ...


@runtime_checkable
class BackendModule(Protocol):
    """سطح ماژول بک‌اند؛ تابع‌های رایج کمکی را فراهم می‌کند."""

    def create_client(self, *args: Any, **kwargs: Any) -> ClientLike: ...

    def normalize_phone(self, phone: str) -> str: ...

    def detect_kind(self, msg: Any) -> str: ...

    async def fetch_message(self, client: ClientLike, ref: Any) -> Any: ...

    def build_media_meta(self, msg: Any) -> Any: ...

    async def get_me_display(self, client: ClientLike) -> str: ...


BACKENDS: dict[str, str] = {
    "telethon": "core.telegram_client",
}

BACKEND_MODULE_ATTRS = (
    "create_client",
    "normalize_phone",
    "detect_kind",
    "fetch_message",
    "build_media_meta",
    "get_me_display",
)


class BackendUnavailable(Exception):
    """بک‌اند خواسته‌شده موجود یا قابل واردکردن نیست."""


def available_backends() -> list[str]:
    return sorted(BACKENDS)


def resolve_backend(name: str | None = None) -> BackendModule:
    """وارد کردن ماژول بک‌اند (پیش‌فرض: telethon) و اعتبارسنجی سطح آن."""
    key = str(name or "telethon").lower()
    if key not in BACKENDS:
        raise BackendUnavailable(f"بک‌اند ناشناخته: {key}")
    try:
        module = importlib.import_module(BACKENDS[key])
    except ImportError as exc:  # pragma: no cover - وابسته به محیط
        raise BackendUnavailable(f"بک‌اند {key} در دسترس نیست") from exc
    missing = [attr for attr in BACKEND_MODULE_ATTRS if not hasattr(module, attr)]
    if missing:
        raise BackendUnavailable(f"بک‌اند {key} ناقص است: {', '.join(missing)}")
    return module  # type: ignore[return-value]