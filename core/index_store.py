"""ایندکس محلی SQLite برای فایل‌های Telegram (File Manager / Personal Cloud).

- شامل Drive ها، پوشه‌های مجازی و فایل‌های ایندکس‌شده (متدیتای پیام).
- نسخه‌بندی Schema با PRAGMA user_version و Migration خودکار.
- قبل از هر Migration از دیتابیس فعلی Backup خودکار می‌گیرد.
- جستجو و مرتب‌سازی سمت دیتابیس برای هزاران فایل؛ همه عملیات‌ها با Lock امن هستند.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import os
import shutil
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Iterable

from utils.file_utils import ensure_dir

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 3

# وضعیت دانلود در ایندکس
DL_REMOTE = "remote"  # فقط در تلگرام ایندکس شده
DL_QUEUED = "queued"
DL_DOWNLOADING = "downloading"
DL_PARTIAL = "partial"  # فایل ناقص .part
DL_DOWNLOADED = "downloaded"
DL_ERROR = "error"
DL_SKIPPED = "skipped"

_PLACEHOLDER = ""


def now_ts() -> float:
    return time.time()


def _new_id() -> str:
    return uuid.uuid4().hex


# ---------------------------------------------------------------------------
# تعریف Schema نسخه به نسخه
# ---------------------------------------------------------------------------

_MIGRATIONS: dict[int, list[str]] = {
    1: [
        """
        CREATE TABLE IF NOT EXISTS drives (
            id TEXT PRIMARY KEY,
            account TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL,
            source_type TEXT NOT NULL DEFAULT 'channel',
            peer_id INTEGER NOT NULL DEFAULT 0,
            username TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            sync_cursor INTEGER NOT NULL DEFAULT 0,
            last_sync_at REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'ok',
            last_error TEXT NOT NULL DEFAULT '',
            auto_sync_enabled INTEGER NOT NULL DEFAULT 1,
            auto_sync_minutes INTEGER NOT NULL DEFAULT 15,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS folders (
            id TEXT PRIMARY KEY,
            drive_id TEXT NOT NULL,
            parent_id TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS files (
            id TEXT PRIMARY KEY,
            drive_id TEXT NOT NULL,
            chat_id INTEGER NOT NULL DEFAULT 0,
            message_id INTEGER NOT NULL,
            file_id TEXT NOT NULL DEFAULT '',
            access_hash TEXT NOT NULL DEFAULT '',
            file_name TEXT NOT NULL DEFAULT '',
            file_size INTEGER NOT NULL DEFAULT 0,
            mime_type TEXT NOT NULL DEFAULT '',
            media_type TEXT NOT NULL DEFAULT 'document',
            caption TEXT NOT NULL DEFAULT '',
            duration REAL,
            message_date REAL NOT NULL DEFAULT 0,
            sender_id INTEGER NOT NULL DEFAULT 0,
            sender_name TEXT NOT NULL DEFAULT '',
            peer_username TEXT NOT NULL DEFAULT '',
            local_path TEXT NOT NULL DEFAULT '',
            download_status TEXT NOT NULL DEFAULT 'remote',
            downloaded_bytes INTEGER NOT NULL DEFAULT 0,
            sha256 TEXT NOT NULL DEFAULT '',
            favorite INTEGER NOT NULL DEFAULT 0,
            hidden INTEGER NOT NULL DEFAULT 0,
            archived INTEGER NOT NULL DEFAULT 0,
            trashed INTEGER NOT NULL DEFAULT 0,
            trash_timestamp REAL NOT NULL DEFAULT 0,
            folder_id TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_files_msg
            ON files(drive_id, chat_id, message_id);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_files_drive ON files(drive_id);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_files_folder ON files(folder_id);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_files_status ON files(download_status);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_files_drive_status
            ON files(drive_id, download_status);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_files_name ON files(file_name);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_files_date ON files(message_date);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_files_sha ON files(sha256) WHERE sha256 != '';
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_folders_path
            ON folders(drive_id, parent_id, name);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_folders_drive ON folders(drive_id);
        """,
    ],
    2: [
        """
        ALTER TABLE files ADD COLUMN removed INTEGER NOT NULL DEFAULT 0;
        """,
    ],
    3: [
        """
        ALTER TABLE files ADD COLUMN file_ext TEXT NOT NULL DEFAULT '';
        """,
    ],
}


class IndexError(Exception):
    """خطای عمومی ایندکس محلی."""


# ---------------------------------------------------------------------------
# ذخیره‌گاه اصلی
# ---------------------------------------------------------------------------


class IndexStore:
    """ایندکس محلی فایل‌های Telegram روی SQLite."""

    def __init__(self, path: str | Path | None = None, data_dir: str | Path | None = None):
        if path is None:
            from config.settings import DEFAULT_DATA_DIR  # noqa: PLC0415

            data_dir = data_dir or DEFAULT_DATA_DIR
            ensure_dir(str(data_dir))
            path = Path(data_dir) / "index.db"
        self.path = str(path)
        self._in_memory = self.path == ":memory:"
        if not self._in_memory:
            parent = Path(self.path).parent
            if str(parent) != ".":
                ensure_dir(str(parent))
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            self.path, check_same_thread=False, timeout=30
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._migrate()

    # ------------------------------------------------------------- lifecycle
    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass

    def _migrate(self) -> None:
        with self._lock:
            current = self._version()
            target = SCHEMA_VERSION
            if current >= target:
                return
            has_tables = self._conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'"
            ).fetchone()
            has_tables = bool(has_tables and has_tables[0])
            # Backup خودکار قبل از Migration (مگر در Memory یا دیتابیس تازه)
            if not self._in_memory and has_tables:
                self._backup(f"index-prev-v{current}")
            tx = self._conn.cursor()
            try:
                with self._conn:
                    for version in range(current + 1, target + 1):
                        for stmt in _MIGRATIONS.get(version, []):
                            tx.execute(stmt)
                        tx.execute(f"PRAGMA user_version = {version}")
            except Exception as exc:  # pragma: no cover
                self._conn.rollback()
                raise IndexError(f"اجرای Migration دیتابیس ایندکس شکست خورد: {exc}") from exc

    def _version(self) -> int:
        row = self._conn.execute("PRAGMA user_version").fetchone()
        return int(row[0] if row else 0)

    def _backup(self, label: str) -> str | None:
        """کپی امن از فایل دیتابیس در پوشه backups؛ مسیر را برمی‌گرداند."""
        if self._in_memory or not os.path.exists(self.path):
            return None
        backups_dir = Path(self.path).parent / "backups"
        ensure_dir(str(backups_dir))
        stamp = time.strftime("%Y%m%d-%H%M%S")
        dest = backups_dir / f"{label}-{stamp}.db"
        try:
            self._conn.commit()
            shutil.copy2(self.path, dest)
            logger.info("Backup خودکار دیتابیس گرفته شد: %s", dest)
            return str(dest)
        except OSError as exc:  # pragma: no cover
            logger.warning("گرفتن Backup دیتابیس ناموفق بود: %s", exc)
            return None

    def backup_now(self) -> str | None:
        """Backup دستی دیتابیس ایندکس."""
        return self._backup("index-backup")

    def schema_version(self) -> int:
        with self._lock:
            return self._version()

    # ------------------------------------------------------------- drives
    def upsert_drive(self, drive: dict) -> str:
        """ذخیره/به‌روزرسانی یک Drive؛ شناسه drive را برمی‌گرداند."""
        drive = dict(drive)
        drive_id = drive.get("id") or _new_id()
        now = now_ts()
        with self._lock:
            existing = self._conn.execute(
                "SELECT id, created_at FROM drives WHERE id = ?", (drive_id,)
            ).fetchone()
            created = existing["created_at"] if existing else drive.get("created_at", now)
            self._conn.execute(
                """
                INSERT INTO drives (
                    id, account, name, source_type, peer_id, username, title,
                    sync_cursor, last_sync_at, status, last_error,
                    auto_sync_enabled, auto_sync_minutes, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    account=excluded.account, name=excluded.name,
                    source_type=excluded.source_type, peer_id=excluded.peer_id,
                    username=excluded.username, title=excluded.title,
                    auto_sync_enabled=excluded.auto_sync_enabled,
                    auto_sync_minutes=excluded.auto_sync_minutes, updated_at=excluded.updated_at
                """,
                (
                    drive_id,
                    drive.get("account", "") or "",
                    (drive.get("name") or "").strip() or drive_id,
                    drive.get("source_type", "channel"),
                    int(drive.get("peer_id", 0) or 0),
                    drive.get("username", "") or "",
                    drive.get("title", "") or "",
                    int(drive.get("sync_cursor", 0) or 0),
                    float(drive.get("last_sync_at", 0) or 0),
                    drive.get("status", "ok") or "ok",
                    drive.get("last_error", "") or "",
                    1 if drive.get("auto_sync_enabled", True) else 0,
                    int(drive.get("auto_sync_minutes", 15) or 15),
                    created,
                    now,
                ),
            )
            return drive_id

    def get_drive(self, drive_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM drives WHERE id = ?", (drive_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_drives(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM drives ORDER BY created_at, name"
            ).fetchall()
            return [dict(r) for r in rows]

    def remove_drive(self, drive_id: str) -> bool:
        with self._lock:
            with self._conn:
                cur = self._conn.execute("DELETE FROM drives WHERE id = ?", (drive_id,))
                if cur.rowcount == 0:
                    return False
                self._conn.execute("DELETE FROM folders WHERE drive_id = ?", (drive_id,))
                self._conn.execute("DELETE FROM files WHERE drive_id = ?", (drive_id,))
            return True

    def set_drive_cursor(self, drive_id: str, cursor: int) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE drives SET sync_cursor = ?, last_sync_at = ?, status = 'ok', "
                "last_error = '' WHERE id = ?",
                (max(0, int(cursor)), now_ts(), drive_id),
            )

    def set_drive_status(self, drive_id: str, status: str, error: str = "") -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE drives SET status = ?, last_error = ? WHERE id = ?",
                (status, error or "", drive_id),
            )

    # ------------------------------------------------------------- folders
    def create_folder(self, drive_id: str, name: str, parent_id: str = "") -> dict:
        name = (name or "").strip()
        if not name:
            raise IndexError("نام پوشه نمی‌تواند خالی باشد.")
        now = now_ts()
        with self._lock:
            existing = self._conn.execute(
                "SELECT * FROM folders WHERE drive_id = ? AND parent_id = ? AND name = ?",
                (drive_id, parent_id, name),
            ).fetchone()
            if existing:
                return dict(existing)
            folder_id = _new_id()
            self._conn.execute(
                "INSERT INTO folders (id, drive_id, parent_id, name, sort_order, created_at, updated_at)"
                " VALUES (?,?,?,?,0,?,?)",
                (folder_id, drive_id, parent_id, name, now, now),
            )
            return self.get_folder(folder_id)  # type: ignore[return-value]

    def get_folder(self, folder_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM folders WHERE id = ?", (folder_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_folders(self, drive_id: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM folders WHERE drive_id = ? ORDER BY name",
                (drive_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def rename_folder(self, folder_id: str, new_name: str) -> bool:
        new_name = (new_name or "").strip()
        if not new_name:
            return False
        with self._lock:
            cur = self._conn.execute(
                "UPDATE folders SET name = ?, updated_at = ? WHERE id = ?",
                (new_name, now_ts(), folder_id),
            )
            return cur.rowcount > 0

    def move_folder(self, folder_id: str, new_parent_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "UPDATE folders SET parent_id = ?, updated_at = ? WHERE id = ?",
                (new_parent_id or "", now_ts(), folder_id),
            )
            return cur.rowcount > 0

    def delete_folder(self, folder_id: str) -> bool:
        """حذف پوشه؛ فایل‌ها به ریشه (uncategorized) منتقل و زیرپوشه‌ها به ریشه می‌روند."""
        with self._lock:
            with self._conn:
                folder = self.get_folder(folder_id)
                if not folder:
                    return False
                self._conn.execute(
                    "UPDATE folders SET parent_id = '' WHERE parent_id = ?", (folder_id,)
                )
                self._conn.execute(
                    "UPDATE files SET folder_id = '' WHERE folder_id = ?", (folder_id,)
                )
                self._conn.execute("DELETE FROM folders WHERE id = ?", (folder_id,))
            return True

    # ------------------------------------------------------------- files
    def upsert_file(self, record: dict, drive_id: str | None = None) -> str:
        """درج یا به‌روزرسانی یک فایل ایندکس‌شده بر اساس (drive, chat, message)."""
        record = dict(record)
        drive_id = drive_id or record.get("drive_id")
        if not drive_id:
            raise IndexError("drive_id برای ثبت فایل لازم است.")
        chat_id = int(record.get("chat_id", 0) or 0)
        message_id = int(record.get("message_id", 0) or 0)
        if not message_id:
            raise IndexError("message_id برای ثبت فایل لازم است.")
        now = now_ts()
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM files WHERE drive_id = ? AND chat_id = ? AND message_id = ?",
                (drive_id, chat_id, message_id),
            ).fetchone()
            base = dict(row) if row else {}
            file_id = record.get("id") or base.get("id") or _new_id()
            fname = (record.get("file_name") or base.get("file_name") or "").strip()
            file_ext = Path(fname).suffix.lower().lstrip(".")
            created = base.get("created_at", now)
            self._conn.execute(
                """
                INSERT INTO files (
                    id, drive_id, chat_id, message_id, file_id, access_hash,
                    file_name, file_ext, file_size, mime_type, media_type, caption, duration,
                    message_date, sender_id, sender_name, peer_username,
                    local_path, download_status, downloaded_bytes, sha256,
                    favorite, hidden, archived, trashed, trash_timestamp,
                    folder_id, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(drive_id, chat_id, message_id) DO UPDATE SET
                    file_id=excluded.file_id, access_hash=excluded.access_hash,
                    file_name=excluded.file_name, file_ext=excluded.file_ext,
                    file_size=excluded.file_size,
                    mime_type=excluded.mime_type, media_type=excluded.media_type,
                    caption=excluded.caption, duration=excluded.duration,
                    message_date=excluded.message_date, sender_id=excluded.sender_id,
                    sender_name=excluded.sender_name, peer_username=excluded.peer_username,
                    folder_id=CASE WHEN excluded.folder_id != '' THEN excluded.folder_id
                                   ELSE files.folder_id END,
                    updated_at=excluded.updated_at
                """,
                (
                    file_id, drive_id, chat_id, message_id,
                    record.get("file_id", "") or base.get("file_id", ""),
                    record.get("access_hash", "") or base.get("access_hash", ""),
                    fname,
                    file_ext,
                    int(record.get("file_size", 0) or base.get("file_size", 0) or 0),
                    record.get("mime_type", "") or base.get("mime_type", ""),
                    record.get("media_type", "document") or base.get("media_type", "document"),
                    record.get("caption", "") or base.get("caption", ""),
                    record.get("duration") if "duration" in record else base.get("duration"),
                    float(record.get("message_date", 0) or 0),
                    int(record.get("sender_id", 0) or 0),
                    record.get("sender_name", "") or base.get("sender_name", ""),
                    record.get("peer_username", "") or base.get("peer_username", ""),
                    record.get("local_path", "") or base.get("local_path", ""),
                    record.get("download_status", DL_REMOTE) or base.get("download_status", DL_REMOTE),
                    int(record.get("downloaded_bytes", 0) or base.get("downloaded_bytes", 0) or 0),
                    record.get("sha256", "") or base.get("sha256", ""),
                    int(record.get("favorite", base.get("favorite", 0) or 0)),
                    int(record.get("hidden", base.get("hidden", 0) or 0)),
                    int(record.get("archived", base.get("archived", 0) or 0)),
                    int(record.get("trashed", base.get("trashed", 0) or 0)),
                    float(record.get("trash_timestamp", 0) or 0),
                    record.get("folder_id", "") or base.get("folder_id", ""),
                    created,
                    now,
                ),
            )
            return file_id

    def upsert_batch(self, records: list[dict], drive_id: str | None = None) -> int:
        """درج/به‌روزرسانی گروهی فایل‌ها در یک تراکنش برای سینک پرحجم."""
        if not records:
            return 0
        with self._lock:
            with self._conn:
                count = 0
                for record in records:
                    if record.get("message_id"):
                        self.upsert_file(record, drive_id or record.get("drive_id"))
                        count += 1
        return count

    def get_file(self, file_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM files WHERE id = ?", (file_id,)
            ).fetchone()
            return dict(row) if row else None

    def file_by_message(self, drive_id: str, chat_id: int, message_id: int) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM files WHERE drive_id = ? AND chat_id = ? AND message_id = ?",
                (drive_id, chat_id, message_id),
            ).fetchone()
            return dict(row) if row else None

    def list_files(
        self,
        drive_id: str | None = None,
        folder_id: str | None = None,
        statuses: Iterable[str] | None = None,
        include_trash: bool = False,
        include_hidden: bool = False,
        include_archived: bool = False,
        sort: str = "name",
        ascending: bool = True,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict]:
        """فهرست فایل‌ها با فیلتر، مرتب‌سازی و صفحه‌بندی."""
        where: list[str] = ["1=1"]
        params: list[Any] = []
        if drive_id:
            where.append("drive_id = ?")
            params.append(drive_id)
        if folder_id is not None:
            where.append("folder_id = ?")
            params.append(folder_id)
        if not include_trash:
            where.append("trashed = 0")
        if not include_hidden:
            where.append("hidden = 0")
        if not include_archived:
            where.append("archived = 0")
        if statuses:
            marks = ",".join("?" * len(list(statuses)))
            where.append(f"download_status IN ({marks})")
            params.extend(statuses)
        order = {
            "name": "file_name",
            "size": "file_size",
            "type": "media_type",
            "date": "message_date",
        }.get(sort, "file_name")
        direction = "ASC" if ascending else "DESC"
        sql = (
            f"SELECT * FROM files WHERE {' AND '.join(where)} "
            f"ORDER BY {order} {direction}, message_id DESC LIMIT ? OFFSET ?"
        )
        params.extend([int(limit), int(offset)])
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def count_files(
        self,
        drive_id: str | None = None,
        folder_id: str | None = None,
        statuses: Iterable[str] | None = None,
        include_trash: bool = False,
        include_hidden: bool = False,
        include_archived: bool = False,
    ) -> int:
        where: list[str] = ["1=1"]
        params: list[Any] = []
        if drive_id:
            where.append("drive_id = ?")
            params.append(drive_id)
        if folder_id is not None:
            where.append("folder_id = ?")
            params.append(folder_id)
        if not include_trash:
            where.append("trashed = 0")
        if not include_hidden:
            where.append("hidden = 0")
        if not include_archived:
            where.append("archived = 0")
        if statuses:
            marks = ",".join("?" * len(list(statuses)))
            where.append(f"download_status IN ({marks})")
            params.extend(statuses)
        with self._lock:
            row = self._conn.execute(
                f"SELECT COUNT(*) AS c FROM files WHERE {' AND '.join(where)}", params
            ).fetchone()
            return int(row["c"] if row else 0)

    def set_file_flags(
        self,
        file_ids: Iterable[str],
        favorite: bool | None = None,
        hidden: bool | None = None,
        archived: bool | None = None,
        trashed: bool | None = None,
    ) -> int:
        """اعمال پرچم‌ها (Favorites/Hidden/Archived/Trash) روی چند فایل."""
        ids = list(file_ids)
        if not ids:
            return 0
        updates: list[str] = []
        params: list[Any] = []
        if favorite is not None:
            updates.append("favorite = ?")
            params.append(1 if favorite else 0)
        if hidden is not None:
            updates.append("hidden = ?")
            params.append(1 if hidden else 0)
        if archived is not None:
            updates.append("archived = ?")
            params.append(1 if archived else 0)
        if trashed is not None:
            updates.append("trashed = ?")
            params.append(1 if trashed else 0)
            updates.append("trash_timestamp = ?")
            params.append(now_ts())
        if not updates:
            return 0
        updates.append("updated_at = ?")
        params.append(now_ts())
        marks = ",".join("?" * len(ids))
        with self._lock:
            params.extend(ids)
            cur = self._conn.execute(
                f"UPDATE files SET {', '.join(updates)} WHERE id IN ({marks})", params
            )
            return cur.rowcount

    def move_files_to_folder(self, file_ids: Iterable[str], folder_id: str) -> int:
        ids = list(file_ids)
        if not ids:
            return 0
        marks = ",".join("?" * len(ids))
        with self._lock:
            cur = self._conn.execute(
                f"UPDATE files SET folder_id = ?, updated_at = ? "
                f"WHERE id IN ({marks})",
                [folder_id or "", now_ts(), *ids],
            )
            return cur.rowcount

    def mark_download(
        self,
        file_id: str,
        status: str,
        downloaded_bytes: int | None = None,
        local_path: str | None = None,
        sha256: str | None = None,
    ) -> None:
        sets = ["download_status = ?", "updated_at = ?"]
        params: list[Any] = [status, now_ts()]
        if downloaded_bytes is not None:
            sets.append("downloaded_bytes = ?")
            params.append(int(downloaded_bytes))
        if local_path is not None:
            sets.append("local_path = ?")
            params.append(local_path)
        if sha256 is not None:
            sets.append("sha256 = ?")
            params.append(sha256 or "")
        file_id_ = (file_id,)
        with self._lock:
            self._conn.execute(f"UPDATE files SET {', '.join(sets)} WHERE id = ?", [*params, *file_id_])

    def delete_files(self, file_ids: Iterable[str]) -> int:
        ids = list(file_ids)
        if not ids:
            return 0
        marks = ",".join("?" * len(ids))
        with self._lock:
            cur = self._conn.execute(f"DELETE FROM files WHERE id IN ({marks})", ids)
            return cur.rowcount

    def rename_file(self, file_id: str, new_name: str) -> bool:
        """تغییر نام منطقی یک فایل ایندکس‌شده (بدون تغییر فایل تلگرام)."""
        new_name = (new_name or "").strip()
        if not new_name:
            return False
        ext = Path(new_name).suffix.lower().lstrip(".")
        with self._lock:
            exists = self._conn.execute("SELECT 1 FROM files WHERE id = ?", (file_id,)).fetchone()
            if not exists:
                return False
            self._conn.execute(
                "UPDATE files SET file_name = ?, file_ext = ?, updated_at = ? WHERE id = ?",
                (new_name, ext, now_ts(), file_id),
            )
        return True

    # ------------------------------------------------------------- search
    def search(
        self,
        query: str,
        drive_id: str | None = None,
        folder_id: str | None = None,
        include_trash: bool = False,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict]:
        """جستجوی محلی در نام، پسوند، کپشن، نوع، تاریخ و نام پوشه."""
        q = (query or "").strip()
        if not q:
            return self.list_files(
                drive_id=drive_id, folder_id=folder_id,
                include_trash=include_trash, limit=limit, offset=offset,
            )
        where: list[str] = ["(file_name LIKE ? OR caption LIKE ? OR media_type LIKE ?)"]
        params: list[Any] = [f"%{q}%", f"%{q}%", f"%{q}%"]
        if drive_id:
            where.insert(0, "drive_id = ?")
            params.insert(0, drive_id)
        if folder_id is not None:
            where.append("folder_id = ?")
            params.append(folder_id)
        if not include_trash:
            where.append("trashed = 0")
        sql = (
            "SELECT files.*, folders.name AS folder_name "
            "FROM files LEFT JOIN folders ON folders.id = files.folder_id "
            f"WHERE {' AND '.join(where)} "
            "ORDER BY message_date DESC LIMIT ? OFFSET ?"
        )
        params.extend([int(limit), int(offset)])
        with self._lock:
            try:
                rows = self._conn.execute(sql, params).fetchall()
            except sqlite3.OperationalError:
                return []
            return [dict(r) for r in rows]

    # ------------------------------------------------------------- duplicates
    def files_by_hash(self, sha256: str, file_size: int, exclude_id: str = "") -> list[dict]:
        """همه نسخه‌های هم‌هش یک فایل (بدون فایل خودش) برای مدیریت تعارض/تکراری."""
        sql = (
            "SELECT * FROM files WHERE sha256 = ? AND file_size = ? "
            "AND trashed = 0 AND id != ?"
        )
        with self._lock:
            rows = self._conn.execute(sql, (sha256, int(file_size), exclude_id)).fetchall()
            return [dict(r) for r in rows]

    def duplicates(self, drive_id: str | None = None) -> list[dict]:
        """فایل‌های تکراری بر اساس SHA-256 (و حجم)؛ خروجی گروه‌بندی‌شده."""
        where = "sha256 != '' AND trashed = 0"
        params: list[Any] = []
        if drive_id:
            where += " AND drive_id = ?"
            params.append(drive_id)
        sql = (
            f"SELECT sha256, file_size, COUNT(*) AS n, "
            "GROUP_CONCAT(id) AS ids, GROUP_CONCAT(file_name, '\\n') AS names "
            f"FROM files WHERE {where} "
            "GROUP BY sha256, file_size HAVING COUNT(*) > 1 "
            "ORDER BY n DESC LIMIT 200"
        )
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------- stats
    def drive_stats(self, drive_id: str | None = None) -> dict:
        """آمار هر Drive: تعداد فایل‌ها، حجم ایندکس، حجم دانلودشده و..."""
        where = "1=1"
        params: list[Any] = []
        if drive_id:
            where = "drive_id = ?"
            params.append(drive_id)
        base_sql = f"FROM files WHERE {where} AND trashed = 0"
        with self._lock:
            row = self._conn.execute(
                f"SELECT COUNT(*) AS files_count, "
                f"COALESCE(SUM(file_size),0) AS total_size, "
                f"COALESCE(SUM(CASE WHEN download_status='downloaded' THEN file_size ELSE 0 END),0) "
                f"AS downloaded_size, "
                f"COALESCE(SUM(CASE WHEN download_status='downloaded' THEN 1 ELSE 0 END),0) "
                f"AS downloaded_count, "
                f"COALESCE(SUM(CASE WHEN favorite=1 THEN 1 ELSE 0 END),0) AS favorites "
                f"{base_sql}",
                params,
            ).fetchone()
            return dict(row if row else {})

    def totals(self) -> dict:
        """آمار کلی (بدون در نظر گرفتن سطل زباله)."""
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS files_count, "
                "COALESCE(SUM(file_size),0) AS total_size, "
                "COALESCE(SUM(CASE WHEN download_status='downloaded' THEN file_size ELSE 0 END),0) "
                "AS downloaded_size, "
                "COALESCE(SUM(CASE WHEN download_status='downloaded' THEN 1 ELSE 0 END),0) "
                "AS downloaded_count, "
                "COALESCE(SUM(CASE WHEN download_status IN ('downloading','queued','partial') THEN 1 ELSE 0 END),0) "
                "AS active_count "
                "FROM files WHERE trashed = 0"
            ).fetchone()
            return dict(row if row else {})

    def folders_count(self, drive_id: str | None = None) -> int:
        where = "1=1"
        params: list[Any] = []
        if drive_id:
            where = "drive_id = ?"
            params.append(drive_id)
        with self._lock:
            row = self._conn.execute(
                f"SELECT COUNT(*) AS c FROM folders WHERE {where}", params
            ).fetchone()
            return int(row["c"] if row else 0)

    # ------------------------------------------------------------- integrity
    def compute_sha256(self, path: str, chunk_size: int = 1024 * 1024) -> str | None:
        """محاسبه SHA-256 بدون بار کردن کل فایل در حافظه (فایل‌های بزرگ)."""
        try:
            h = hashlib.sha256()
            with open(path, "rb") as fh:
                while True:
                    chunk = fh.read(chunk_size)
                    if not chunk:
                        break
                    h.update(chunk)
            return h.hexdigest()
        except OSError:
            return None

    def verify_file_health(self, file_id: str) -> dict:
        """بررسی سلامت فایل دانلودشده؛ SHA-256 را دوباره محاسبه و مقایسه می‌کند."""
        file_rec = self.get_file(file_id)
        if not file_rec:
            return {"ok": False, "reason": "not_found", "message": "فایل در ایندکس نیست."}
        path = file_rec.get("local_path") or ""
        if not path or not os.path.exists(path):
            return {"ok": False, "reason": "missing", "message": "فایل محلی وجود ندارد."}
        actual = self.compute_sha256(path)
        stored = file_rec.get("sha256") or ""
        expected_size = int(file_rec.get("file_size") or 0)
        actual_size = os.path.getsize(path)
        ok = actual is not None and (not stored or actual == stored)
        if stored and actual and actual != stored:
            reason = "corrupt"
            message = "فایل نیاز به بررسی مجدد دارد."
        elif expected_size and actual_size != expected_size:
            reason = "size_mismatch"
            message = "حجم فایل با متادیتای تلگرام مطابقت ندارد."
        else:
            reason = ""
            message = "فایل سالم است."
        return {
            "ok": ok,
            "reason": reason,
            "message": message,
            "sha256": actual or "",
            "size": actual_size,
            "expected_size": expected_size,
        }

    def find_incomplete_local(self) -> list[dict]:
        """فایل‌های ناقص/در حال دانلود برای بازیابی Queue در اجرای بعدی."""
        statuses = (DL_QUEUED, DL_PARTIAL, DL_DOWNLOADING)
        marks = ",".join("?" * len(statuses))
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM files WHERE download_status IN ({marks})", statuses
            ).fetchall()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------- export
    def export(self, path: str | Path, fmt: str = "json", drive_id: str | None = None) -> int:
        """خروجی متادیتا به JSON یا CSV (بدون Session و داده حساس)."""
        records = self.list_files(
            drive_id=drive_id, include_trash=True, include_hidden=True,
            include_archived=True, limit=10**6,
        )
        for r in records:
            r.pop("access_hash", None)
        path = str(path)
        if fmt.lower() == "csv":
            if not records:
                Path(path).write_text("", encoding="utf-8")
                return 0
            keys = list(records[0].keys())
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                writer = csv.DictWriter(fh, fieldnames=keys)
                writer.writeheader()
                writer.writerows(records)
            return len(records)
        data = {"exported_at": now_ts(), "schema": SCHEMA_VERSION, "files": records}
        tmp = Path(path + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
        return len(records)