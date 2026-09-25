"""شناسایی Edition برنامه و اطلاعات Build-Time.

منبع حقیقت `config/_build_info.py` است که هنگام Build توسط
`scripts/generate_build_info.py` از پروفایل‌های build_profiles/ ساخته می‌شود
و در Git قرار نمی‌گیرد. در محیط توسعه، متغیرهای محیطی TDL_* مقدار جایگزین هستند.

دو Edition:
    - personal: بدون درخواست API از کاربر؛ اعتبارنامه به‌صورت Build-Secret تزریق می‌شود.
    - public:   کاربر در اولین اجرا API ID/Hash را وارد می‌کند (Wizard).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

PERSONAL = "personal"
PUBLIC = "public"

_PERSONAL_TABLE = {
    "display_name": "Telegram Downloader Personal",
    "exe_name": "TelegramDownloader-Personal",
    "installer_name": "TelegramDownloader-Personal-Setup",
    "folder": "Personal",
    "update_url": "",
    "app_id_guid": "{9B2A6D3E-5F4C-4A7B-9E11-3C0D1E2F4A56}",
    "theme": "dark",
}

_PUBLIC_TABLE = {
    "display_name": "Telegram Downloader Public",
    "exe_name": "TelegramDownloader-Public",
    "installer_name": "TelegramDownloader-Public-Setup",
    "folder": "Public",
    "update_url": "",
    "app_id_guid": "{9B2A6D3E-5F4C-4A7B-9E11-3C0D1E2F4A57}",
    "theme": "system",
}


@dataclass(frozen=True)
class EditionInfo:
    edition: str = PERSONAL
    display_name: str = "Telegram Downloader Personal"
    exe_name: str = "TelegramDownloader-Personal"
    installer_name: str = "TelegramDownloader-Personal-Setup"
    folder: str = "Personal"
    update_url: str = ""
    app_id_guid: str = "{9B2A6D3E-5F4C-4A7B-9E11-3C0D1E2F4A56}"
    theme: str = "dark"
    language: str = "fa"
    api_id: int = 0
    api_hash: str = ""
    app_version: str = "1.0.1"
    power_dry_run: bool = False

    @property
    def is_public(self) -> bool:
        return self.edition == PUBLIC

    @property
    def is_personal(self) -> bool:
        return self.edition == PERSONAL

    @property
    def show_api_wizard(self) -> bool:
        """Public باید صفحه تنظیم اتصال Telegram (API ID/Hash) را در Wizard نشان دهد."""
        return self.is_public


def _build_info_source() -> dict:
    try:
        from config import _build_info  # noqa: PLC0415

        return {k: v for k, v in vars(_build_info).items() if k.isupper()}
    except Exception:
        return {}


def _read_personal_secrets() -> tuple[int, str]:
    """در حالت توسعه (بدون _build_info) Secret شخصی را از فایل gitignored می‌خواند."""
    from pathlib import Path  # noqa: PLC0415

    env_file = Path(__file__).resolve().parent.parent / "secrets" / "personal.env"
    if not env_file.exists():
        return 0, ""
    api_id = api_hash = ""
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            value = value.strip().strip('"').strip("'")
            if key.strip() == "TDL_API_ID":
                api_id = value
            elif key.strip() == "TDL_API_HASH":
                api_hash = value
    return (int(api_id), api_hash) if api_id.isdigit() and api_hash else (0, "")


def current() -> EditionInfo:
    """بازگرداندن اطلاعات Edition جاری (هر بار می‌خواند؛ کش نمی‌شود).

    اولویت مقادیر: متغیر محیطی TDL_* > فایل _build_info.py > پروفایل پیش‌فرض.
    """
    src = _build_info_source()

    edition_raw = (
        os.environ.get("TDL_EDITION", "")
        or src.get("EDITION", "")
        or PERSONAL
    ).strip().lower()
    edition = edition_raw if edition_raw in (PERSONAL, PUBLIC) else PERSONAL
    is_public = edition == PUBLIC
    base = _PUBLIC_TABLE if is_public else _PERSONAL_TABLE

    def value(name: str, env_key: str = "", default: str = "") -> str:
        src_val = src.get(name, "") or ""
        if default and not src_val:
            src_val = default
        env = os.environ.get(env_key, "") if env_key else ""
        return env or src_val

    api_id = 0
    api_hash = ""
    if os.environ.get("TDL_API_ID", "").isdigit():
        api_id = int(os.environ["TDL_API_ID"])
        api_hash = os.environ.get("TDL_API_HASH", "")
    elif edition == PERSONAL:
        # اعتبارنامه فقط برای Personal از _build_info یا secrets خارج از Source خوانده می‌شود.
        api_id = int(src.get("API_ID", 0) or 0)
        api_hash = str(src.get("API_HASH", "") or "")
        if not api_id or not api_hash:
            dev_id, dev_hash = _read_personal_secrets()
            if dev_id:
                api_id, api_hash = dev_id, dev_hash

    dry_run = os.environ.get("TDL_POWER_DRY_RUN", "0") in ("1", "true", "yes") or bool(
        src.get("POWER_DRY_RUN", False)
    )

    return EditionInfo(
        edition=edition,
        display_name=value("DISPLAY_NAME", default=base["display_name"]),
        exe_name=value("EXE_NAME", "TDL_EXE_NAME", base["exe_name"]),
        installer_name=value("INSTALLER_NAME", "TDL_INSTALLER_NAME", base["installer_name"]),
        folder=value("FOLDER", "TDL_FOLDER", base["folder"]),
        update_url=value("UPDATE_URL", "TDL_UPDATE_URL", base["update_url"]),
        app_id_guid=value("APP_ID_GUID", default=base["app_id_guid"]),
        theme=value("THEME", "TDL_THEME", base["theme"]),
        language=value("LANGUAGE", "TDL_LANGUAGE", "fa"),
        api_id=api_id,
        api_hash=api_hash,
        app_version=value("APP_VERSION", "TDL_APP_VERSION", "1.0.1"),
        power_dry_run=dry_run,
    )


# ---------------------------------------------------------------------------
# سازگاری با import های قدیمی (config.api_credentials)
# ---------------------------------------------------------------------------

_effective = current()

API_ID = _effective.api_id
API_HASH = _effective.api_hash
APP_NAME = _effective.exe_name
APP_SHORT_NAME = "TelegramDownloader"
APP_VERSION = _effective.app_version
CURRENT_EDITION = _effective.edition
DISPLAY_NAME = _effective.display_name
UPDATE_URL = _effective.update_url
POWER_DRY_RUN = _effective.power_dry_run


def is_configured() -> bool:
    """آیا اعتبارنامه برای این Edition در دسترس است؟"""
    return bool(API_ID and API_HASH)
