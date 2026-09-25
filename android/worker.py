"""پردازگر پس‌زمینه نسخه همراه: صف‌بندی آپلود و انتخاب مقصد (اسکلت)."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

DEFAULT_CHUNK_BYTES = 8 * 1024 * 1024  # 8 MiB


@dataclass
class UploadJob:
    """یک کار آپلود فایل به فضای تلگرام."""

    source: str
    drive_id: str = "default"
    dest_folder: str = ""
    chunk_bytes: int = DEFAULT_CHUNK_BYTES
    sha256: str = ""
    size: int = 0
    filename: str = ""
    status: str = "queued"  # queued | uploading | done | failed
    error: str = ""

    @classmethod
    def from_file(cls, source: str, *, drive_id: str = "default", dest_folder: str = "") -> "UploadJob":
        path = Path(source)
        digest = ""
        try:
            digest = _sha256_of(path)
        except OSError:
            pass
        return cls(
            source=str(path),
            drive_id=drive_id,
            dest_folder=dest_folder,
            sha256=digest,
            size=int(path.stat().st_size) if path.exists() else 0,
            filename=path.name,
        )


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def pick_destination(local_file: str, *, base_folder: str = "") -> str:
    """حدس مقصد مناسب بر اساس نوع فایل (در پوشه Documents/Media)."""
    suffix = Path(local_file).suffix.lower()
    if suffix in (".mp4", ".mkv", ".webm", ".mov", ".avi"):
        return "Media/Videos"
    if suffix in (".mp3", ".m4a", ".ogg", ".wav", ".opus", ".flac"):
        return "Media/Audio"
    if suffix in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic"):
        return "Media/Photos"
    if suffix in (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".zip"):
        return "Documents"
    if base_folder:
        return base_folder
    return "Other"


def chunk_defs(size: int, chunk_bytes: int = DEFAULT_CHUNK_BYTES) -> list[tuple[int, int]]:
    """فهرست بازه‌های (شروع، پایان) قطعات فایل برای آپلود چندبخشی."""
    if size <= 0:
        return []
    steps = []
    start = 0
    chunk = max(1, int(chunk_bytes))
    while start < size:
        end = min(start + chunk, size)
        steps.append((start, end))
        start = end
    return steps


class UploadWorker:
    """ناظر صف آپلود؛ با عکس‌العمل روی دسکتاپ بدون اندروید بی‌اثر است."""

    def __init__(self, *, on_progress: Optional[Callable[[UploadJob], None]] = None, limit: int = 4):
        self.on_progress = on_progress
        self.limit = max(1, int(limit))
        self._jobs: list[UploadJob] = []

    def enqueue(self, job: UploadJob) -> bool:
        if len(self._jobs) >= self.limit:
            return False
        self._jobs.append(job)
        return True

    def pending(self) -> list[UploadJob]:
        return [j for j in self._jobs if j.status == "queued"]

    def active(self) -> list[UploadJob]:
        return [j for j in self._jobs if j.status == "uploading"]

    def count(self, status: str | None = None) -> int:
        if status is None:
            return len(self._jobs)
        return sum(1 for j in self._jobs if j.status == status)

    def reset(self) -> None:
        self._jobs = []


def build_queue(files: list[str], *, limit: int = 4, dest_folder: str = "") -> list[UploadJob]:
    """ساخت صف آپلود اولیه از فهرست فایل‌های محلی."""
    worker = UploadWorker(limit=limit)
    for path in files:
        if not os.path.isfile(path):
            continue
        job = UploadJob.from_file(path, dest_folder=dest_folder)
        job.dest_folder = pick_destination(job.filename, base_folder=dest_folder)
        worker.enqueue(job)
    return list(worker._jobs)