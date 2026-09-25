"""ذخیره‌سازی چند اکانت تلگرام به‌صورت رمزشده (DPAPI)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from utils import security
from utils.file_utils import ensure_dir

logger = logging.getLogger(__name__)


class AccountStore:
    """مدیریت فهرست اکانت‌ها و اکانت فعال؛ session ها رمز شده نگه داشته می‌شوند."""

    FILE_NAME = "accounts.json"

    def __init__(self, path: Path | None = None, data_dir: Path | None = None):
        from config.settings import DEFAULT_DATA_DIR

        self.data_dir = data_dir or DEFAULT_DATA_DIR
        self.path = path or self.data_dir / self.FILE_NAME
        ensure_dir(str(self.data_dir))

    # ------------------------------------------------------------------ internals
    def _load(self) -> list[dict]:
        try:
            if self.path.exists():
                token = self.path.read_text(encoding="utf-8")
                data = security.decode_secret(token)
                if isinstance(data, list):
                    return [dict(item) for item in data]
        except Exception as exc:
            logger.warning("خواندن فایل اکانت‌ها ناموفق بود: %s", exc)
        return []

    def _save(self, accounts: list[dict]) -> None:
        ensure_dir(str(self.path.parent))
        token = security.encode_secret(accounts)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(token, encoding="utf-8")
        os.replace(tmp, self.path)

    # ------------------------------------------------------------------ public
    def accounts(self) -> list[dict]:
        """بازگرداندن کپی از اکانت‌ها (شامل session؛ در رابط کاربری فیلتر شود)."""
        return self._load()

    def get(self, key: str) -> dict | None:
        for item in self._load():
            if item.get("key") == key:
                return dict(item)
        return None

    def upsert(self, record: dict) -> None:
        accounts = self._load()
        key = record.get("key")
        for i, item in enumerate(accounts):
            if item.get("key") == key:
                accounts[i] = dict(record)
                break
        else:
            accounts.append(dict(record))
        self._save(accounts)

    def set_active(self, key: str) -> None:
        accounts = self._load()
        for item in accounts:
            item["active"] = item.get("key") == key
        self._save(accounts)

    def active_key(self) -> str | None:
        accounts = self._load()
        if not accounts:
            return None
        for item in accounts:
            if item.get("active"):
                return item.get("key")
        return accounts[0].get("key")

    def remove(self, key: str) -> None:
        accounts = [item for item in self._load() if item.get("key") != key]
        if len(accounts) == 1:
            accounts[0]["active"] = True
        self._save(accounts)

    def migrate_from_credentials(self, legacy: dict) -> bool:
        """انتقال رکورد قدیمی credentials.bin به فهرست اکانت‌ها (در صورت خالی بودن)."""
        if not legacy.get("session") or legacy.get("api_hash") is None:
            return False
        if self._load():
            return False
        key = str(legacy.get("phone") or "account-1")
        self.upsert(
            {
                "key": key,
                "phone": key,
                "api_id": legacy.get("api_id"),
                "api_hash": legacy.get("api_hash"),
                "session": legacy.get("session"),
                "active": True,
            }
        )
        return True
