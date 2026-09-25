"""مدیریت Session تلگرام به‌صورت رمز شده."""

from __future__ import annotations

from config.settings import CredentialStore


class SessionManager:
    """مدیریت Session تلگرام (رشته جلسه) با رمزنگاری Windows DPAPI."""

    def __init__(self, store: CredentialStore | None = None):
        self._store = store or CredentialStore()

    def save(self, *, api_id: int, api_hash: str, session: str, phone: str = "") -> None:
        self._store.save(
            {
                "api_id": api_id,
                "api_hash": api_hash,
                "session": session,
                "phone": phone or "",
            }
        )

    def load(self) -> dict:
        return self._store.load()

    def clear(self) -> None:
        self._store.delete()

    def has_session(self) -> bool:
        data = self._store.load()
        return bool(data.get("session") and data.get("api_id") and data.get("api_hash"))
