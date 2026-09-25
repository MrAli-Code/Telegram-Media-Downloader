"""ذخیره‌سازی تنظیمات و اعتبارنامه‌ها (API ID/Hash، شماره)."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from utils import security
from utils.file_utils import ensure_dir

logger = logging.getLogger(__name__)

APP_NAME = "TelegramDownloader"
DEFAULT_DATA_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / APP_NAME
DEFAULT_LOG_DIR = Path(os.environ.get("LOCALAPPDATA", str(DEFAULT_DATA_DIR))) / APP_NAME / "logs"


@dataclass
class Settings:
    """تنظیمات غیرحساس کاربر."""

    download_folder: str = str(Path.home() / "Downloads" / "TelegramDownloader")
    concurrent_downloads: int = 2
    auto_resume: bool = True
    overwrite_existing: bool = False
    skip_existing: bool = False
    theme: str = "dark"  # dark | light | system
    font_size: int = 13
    notify_on_complete: bool = True
    download_chunk_kb: int = 512
    proxy_enabled: bool = False
    proxy_type: str = "socks5"  # socks5 | http | mtproto
    proxy_host: str = ""
    proxy_port: int = 1080
    proxy_username: str = ""
    proxy_password: str = ""
    proxy_secret: str = ""
    # زبان و چیدمان
    language: str = "fa"
    rtl: bool = True
    # عملیات پس از اتمام همه دانلودها
    after_all_done: str = "none"  # none | exit | shutdown | restart | sleep | hibernate
    confirm_before_shutdown: bool = True
    success_only_action: bool = False
    power_delay_seconds: int = 30
    # System Tray
    close_to_tray: bool = True
    minimize_to_tray: bool = True
    # محدودیت سرعت (0 یعنی نامحدود، کیلوبایت/ثانیه)
    speed_limit_kb: int = 0
    # زمان‌بندی دانلود (قالب ساعت "HH:MM")
    schedule_enabled: bool = False
    schedule_start: str = "09:00"
    schedule_stop: str = "23:00"
    # بروزرسانی
    auto_check_updates: bool = True
    update_url: str = ""
    # همگام‌سازی خودکار فضاها (۰ = دستی)
    auto_sync_enabled: bool = True
    auto_sync_minutes: int = 15
    # حریم خصوصی و ظاهر فایل منیجر
    private_mode: bool = False
    fm_compact: bool = False
    # سهمیه حافظه کش فایل‌های موقت (گیگابایت)
    cache_quota_gb: float = 2.0

    def to_dict(self) -> dict:
        return asdict(self)

    def proxy_config(self) -> dict:
        """تبدیل فیلدهای پروکسی به ساختار قابل استفاده در ساخت کلاینت."""
        return {
            "enabled": self.proxy_enabled,
            "type": self.proxy_type,
            "host": self.proxy_host,
            "port": int(self.proxy_port or 0),
            "username": self.proxy_username,
            "password": self.proxy_password,
            "secret": self.proxy_secret,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "Settings":
        if not data:
            return cls()
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)


class SettingsStore:
    """ذخیره و بازیابی تنظیمات در پوشه داده برنامه."""

    def __init__(self, path: Path | None = None, data_dir: Path | None = None):
        self.data_dir = data_dir or DEFAULT_DATA_DIR
        self.path = path or self.data_dir / "settings.json"
        ensure_dir(str(self.data_dir))

    def load(self) -> Settings:
        try:
            if self.path.exists():
                with open(self.path, encoding="utf-8") as fh:
                    return Settings.from_dict(json.load(fh))
        except Exception as exc:
            logger.warning("خطا هنگام خواندن تنظیمات: %s", exc)
        return Settings()

    def save(self, settings: Settings) -> None:
        ensure_dir(str(self.path.parent))
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(settings.to_dict(), fh, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)


class CredentialStore:
    """ذخیره امن اعتبارنامه‌های تلگرام با Windows DPAPI."""

    def __init__(self, path: Path | None = None, data_dir: Path | None = None):
        self.data_dir = data_dir or DEFAULT_DATA_DIR
        self.path = path or self.data_dir / "credentials.bin"
        ensure_dir(str(self.data_dir))

    def load(self) -> dict:
        try:
            if self.path.exists():
                token = self.path.read_text(encoding="utf-8")
                return security.decode_secret(token)
        except Exception as exc:
            logger.warning("خواندن اعتبارنامه ناموفق بود: %s", exc)
        return {}

    def save(self, data: dict) -> None:
        ensure_dir(str(self.path.parent))
        token = security.encode_secret(data)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(token, encoding="utf-8")
        os.replace(tmp, self.path)

    def delete(self) -> None:
        try:
            if self.path.exists():
                self.path.unlink()
        except OSError as exc:
            logger.warning("حذف فایل اعتبارنامه ناموفق بود: %s", exc)

    def has_credentials(self) -> bool:
        data = self.load()
        return bool(data.get("api_id") and data.get("api_hash"))
