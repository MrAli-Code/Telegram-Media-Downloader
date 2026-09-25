"""سرور HTTP محلی برای پخش جریانی با پشتیبانی از Range (پخش قبل از تکمیل دانلود).

فایل موقت `.part` که دانلود هنوز در حال نوشتن است، با این سرور در دسترس پخش‌کننده قرار می‌گیرد؛
QMediaPlayer با درخواست‌های Range فقط بخش‌هایی را که تاکنون دریافت شده، پخش می‌کند و Seek تا حداکثر بایت موجود پشتیبانی می‌شود.
"""

from __future__ import annotations

import logging
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

logger = logging.getLogger(__name__)

_READ_CHUNK = 256 * 1024


class _FileState:
    def __init__(self) -> None:
        self.path: Path | None = None
        self.lock = threading.RLock()


class _Handler(BaseHTTPRequestHandler):
    server_version = "TDLStream/1.0"
    protocol_version = "HTTP/1.1"

    # ------------------------------------------------------------------ helpers
    def _resolve(self) -> tuple[Path | None, str]:
        state: _FileState = self.server.file_state  # type: ignore[attr-defined]
        with state.lock:
            path = state.path
        if path is None or not path.is_file():
            return None, ""
        return path, path.name

    def _send_head(self, file: Path, start: int, end: int, length: int, partial: bool) -> None:
        self.send_response(206 if partial else 200)
        self.send_header("Accept-Ranges", "bytes")
        if partial:
            self.send_header("Content-Range", f"bytes {start}-{end}/{length}")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _parse_range(self, header: str | None, length: int) -> tuple[int, int, bool] | None:
        if not header:
            return 0, length - 1, False
        if not header.startswith("bytes=") or "," in header:
            return None
        spec = header[len("bytes=") :].strip()
        if "-" not in spec:
            return None
        first, last = spec.split("-", 1)
        if first == "":
            suffix = int(last or 0)
            if suffix <= 0:
                return None
            start = max(0, length - suffix)
            return start, length - 1, True
        start = int(first)
        end = int(last) if last else length - 1
        if start > end or start >= length:
            return None
        return start, min(end, length - 1), True

    # ------------------------------------------------------------------ verbs
    def do_GET(self) -> None:  # noqa: N802
        file, name = self._resolve()
        if file is None:
            self.send_response(404)
            self.end_headers()
            return
        length = file.stat().st_size
        rng = self._parse_range(self.headers.get("Range"), length)
        if rng is None:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{length}")
            self.end_headers()
            return
        start, end, partial = rng
        self._send_head(file, start, end, length, partial)
        remaining = end - start + 1
        with file.open("rb") as fhandle:
            fhandle.seek(start)
            while remaining > 0:
                block = fhandle.read(min(_READ_CHUNK, remaining))
                if not block:
                    break
                try:
                    self.wfile.write(block)
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    break
                remaining -= len(block)

    def do_HEAD(self) -> None:  # noqa: N802
        file, _name = self._resolve()
        if file is None:
            self.send_response(404)
            self.end_headers()
            return
        length = file.stat().st_size
        self.send_response(200)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        self.end_headers()

    def log_message(self, fmt: str, *args) -> None:  # pragma: no cover
        logger.debug("HTTP %s", fmt % args)


class StreamRangeServer:
    """سرور Range روی 127.0.0.1 با فایل قابل تعویض (برای پخش پیشرونده فایل .part)."""

    def __init__(self) -> None:
        self._state = _FileState()
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self, file_path: Path | str | None = None) -> None:
        if self._httpd is not None:
            return
        if file_path is not None:
            self._state.path = Path(file_path)

        class _Server(ThreadingHTTPServer):
            daemon_threads = True
            allow_reuse_address = True

        self._httpd = _Server(("127.0.0.1", 0), _Handler)
        self._httpd.file_state = self._state  # type: ignore[attr-defined]
        self._thread = threading.Thread(target=self._httpd.serve_forever, name="stream-range", daemon=True)
        self._thread.start()

    def set_file(self, file_path: Path | str) -> None:
        with self._state.lock:
            self._state.path = Path(file_path)

    def url_for(self, file_path: Path | str) -> str:
        self.start()
        self.set_file(file_path)
        port = self._httpd.server_port
        return f"http://127.0.0.1:{port}/stream"

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._thread is not None:
            self._thread.join(timeout=3)
            self._thread = None


def fetch_range(url: str, start: int = 0, end: int | None = None) -> tuple[int, str, bytes]:
    """کمک تست: درخواست GET با هدر Range و برگرداندن (کد وضعیت، Content-Range، بدنه)."""
    req = urllib.request.Request(url)
    if end is not None:
        req.add_header("Range", f"bytes={start}-{end}")
    elif start:
        req.add_header("Range", f"bytes={start}-")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, str(resp.headers.get("Content-Range") or ""), resp.read()