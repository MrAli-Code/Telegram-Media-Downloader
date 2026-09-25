# گزارش نهایی — Telegram Downloader → Telegram File Manager / Personal Cloud

نسخه 1.0.1 — تاریخ ساخت: 2026-09-23

---

## ۱. قابلیت‌های اضافه‌شده

**هسته (Core / Data)**
- `core/index_store.py` — اندیس SQLite کامل: Telegram Message ID، Chat/Channel ID، File ID، نام، حجم، MIME، Media Type، Caption، تاریخ، مسیر، وضعیت دانلود، SHA-256، دلخواه/پنهان/آرشیو/زباله، Folder ID؛ قابل جستجو، مرور آفلاین، Export (JSON/CSV)
- `core/drive_manager.py` — فضاهای چندگانه (Channel / Group / Saved Messages) با اندیس و آمار مستقل
- `core/queue_manager.py` — صف هوشمند: اولویت (کم/عادی/بالا)، جابجایی به ابتدای صف، `_pump` مرتب‌شده با اولویت، صف مداوم (queue.json)
- `core/history_store.py` — تاریخچه مداوم
- `core/models.py` — `QueueItem.priority` (پایدار در serialize) + Shot يات
- `core/sync_service.py` — همگام‌سازی افزایشی با حفظ Sync Cursor (آخرین Message ID)
- `services/download_service.py` — Resume واقعی از `.part`، SHA-256 در پایان، تشخیص تکراری (Skip/Replace/Rename/Keep Both)، FloodWait با نمایش زمان انتظار، پخش/توقف/ادامه همگانی، بازیابی صف «دانلودهای ناتمام»، `add_indexed_files` از اندیس، `move_to_front`/`set_priority`
- `utils/security.py` — احراز نشست با KDF (PBKDF2-HMAC-SHA256)، CredentialStore (DPAPI/fallback)، فایل `credentials.bin` رمزنگاری‌شده
- `config/settings.py` + `config/features.py` — Settings مداوم (Auto-Sync، هم‌زمانی، سرعت، تم، RTL،... ) + Feature Flags (`ENABLE_BACKUP`، `ENABLE_ENCRYPTION`، `ENABLE_STREAMING`، `ENABLE_ANDROID`)
- `config/edition.py` + `scripts/generate_build_info.py` — دو نسخه Personal/Public

**GUI**
- سایدبار کامل: خانه/صف/فایل‌ها/فضاهای من/تاریخچه/تنظیمات/درباره
- `gui/main_window.py` — داشبورد آمار، میان‌برهای `Ctrl+F`/`Ctrl+V`/`Ctrl+Enter`/`Ctrl+Shift+V`، شروع خودکار بازیابی ناتمام، دکمه‌های توقف/ادامه همگانی در statusbar
- `gui/file_manager_page.py` — جدول فایل‌ها (List)، جستجو/فیلتر/مرتب‌سازی، پوشه‌ها، دلخواه/پنهان/زباله، چندانتخابی، دانلود/حذف گروهی، تغییر نام، انتقال، باز کردن، Refresh — رفع باگ `setRowCount` (نمایش صحیح ردیف‌ها)
- `gui/drive_manager_page.py` — کارت‌های فضاها (نام/منبع/تعداد فایل‌ها/حجم/آخرین همگام/وضعیت)، افزودن فضا، همگام‌سازی دستی/خودکار (۵/۱۵/۳۰/۶۰ دقیقه/دستی)، باز کردن Drive در تلگرام، Export اندیس با QFileDialog، نمایش هم‌زمان «در حال همگام‌سازی»
- `gui/download_widget.py` — منوی کارت (⋮): جابجایی به ابتدای صف، زیرمنوی اولویت (کم/عادی/بالا)، حذف؛ سیگنال‌های `moveToFrontClicked`/`priorityClicked`
- `gui/settings_dialog.py` — همه گزینه‌های Settings (شامل هم‌زمانی، پوسته، RTL، زبان، سرعت، زمان‌بندی، پروکسی، حساب‌ها، بروزرسانی، Import/Export)
- `gui/setup_wizard.py` — ویزارد ورود (شماره+کد+2FA) و در نسخه Public دریافت API ID/Hash

**Install / Release**
- `build_profiles/{personal,public}.json` + `build/build_edition.ps1` + `build_personal.bat`/`build_public.bat`/`build_all.bat`
- `installer/setup.iss` — **Clean Uninstall** (سؤال حذف/نگه‌داری داده‌ها در زمان Uninstall)، نصب ۶۴ بیتی، شدت Minimal
- `release/Personal/*` ، `release/Public/*` ، `release/Documentation/*` (مطابق ساختار درخواستی)
- `release/Personal/TelegramDownloader-Personal-Portable.zip` و `release/Public/TelegramDownloader-Public-Portable.zip` (Portable)

---

## ۲. فایل‌های ایجاد/تغییریافته (اصلی)

| ناحیه | فایل‌ها |
|---|---|
| هسته | `core/index_store.py`, `core/queue_manager.py`, `core/drive_manager.py`, `core/sync_service.py`, `core/history_store.py`, `core/models.py`, `core/hash_utils.py`, `core/duplicate_policy.py` |
| سرویس | `services/download_service.py`, `services/authentication.py`, `services/account_store_service.py` |
| GUI | `gui/main_window.py`, `gui/file_manager_page.py`, `gui/drive_manager_page.py`, `gui/download_widget.py`, `gui/settings_dialog.py`, `gui/setup_wizard.py`, `gui/history_window.py`, `gui/about_dialog.py`, `gui/dashboard_panel.py` |
| Config/Utils | `config/settings.py`, `config/edition.py`, `config/features.py`, `config/version.py`, `utils/security.py`, `utils/i18n.py`, `utils/updates.py`, `utils/link_parser.py` |
| i18n | `locales/fa.json`, `locales/en.json` |
| Build/Install | `build_profiles/*.json`, `build/*.ps1`, `build/*.spec`, `installer/setup.iss`, `build_personal.bat`, `build_public.bat`, `build_all.bat`, `scripts/generate_build_info.py`, `scripts/make_icon.py` |
| تست | `tests/test_*.py` (۲۴ فایل) |
| Docs | `README.md`, `release/Documentation/*`، `release/{Personal,Public}/README-*.txt` |

---

## ۳. تست‌های اجراشده

```
python -m pytest -q   →   154 passed in 21.11s
python -m ruff check →   All checks passed!
```

- Queue / Priority Ordering / Move-to-Front / Persistence
- Index Store CRUD / Folders / Favorites / Trash / Export/CSV / Migration
- Drive Manager (افزودن فضا، آمار، Sync Cursor)
- Sync Service (افزایشی)
- پیکربندی (Settings roundtrip، CredentialStore امن، زبان، Feature Flags)
- Link Parser (وضعیت‌های مختلف لینک) / Telegram Adapter (Telethon، FloodWait، FakeClient)
- تاریخچه، Hash/Integrity، Shutdown Safety
- GUI (MainWindow navig., میان‌برها، FileManager rows + toast دانلود، Drive auto-sync، Export، منوی اولویت کارت)
- Boot Smoke (هر دو EXE با QT_QPA_PLATFORM=offscreen: BOOT OK)

---

## ۴. محدودیت‌های باقی‌مانده

- **SmartScreen/Authenticode**: فایل‌ها امضای دیجیتال ندارند؛ ویندوز هشدار SmartScreen می‌دهد.
- **Encryption/Backup/Streaming/Android**: با Feature Flags وجود دارند ولی به‌صورت رسمی در این Release فعال/ویندوی کامل نشده‌اند (رد P2)؛ پیاده‌سازی به‌صورت ماژولار تا برنامهٔ اصلی پایدار بماند.
- **Streaming پیش از دانلود کامل**: معماری chunked آماده است ولی Play-from-cloud برای رسانه‌های تلگرام به قابلیت‌های خود Telethon وابسته است و در این نسخه فعال نشده.
- **App Lock / Screenshot Protection**: در Windows به حد «حالت حریم خصوصی» محدود شده است.
- **Metered-Connection pause** و **Backup Scheduler** طبق مشخصات Windows در نسخه بعدی.
- Update Server: `UPDATE_URL` خالی است (پیش‌فرض غیرفعال) تا کاربر URL سرویس خودش را تنظیم کند.

---

## ۵. محل خروجی‌ها

```
release/
├── Personal/
│   ├── TelegramDownloader-Personal.exe            (51.6 MB — پرتابل)
│   ├── TelegramDownloader-Personal-Setup.exe      (53 MB — نصب‌کننده)
│   ├── TelegramDownloader-Personal-Portable.zip   (51.3 MB)
│   └── README-Personal.txt
├── Public/
│   ├── TelegramDownloader-Public.exe
│   ├── TelegramDownloader-Public-Setup.exe
│   ├── TelegramDownloader-Public-Portable.zip
│   └── README-Public.txt
├── Documentation/
│   ├── README-fa.md
│   ├── INSTALL-fa.md
│   ├── SECURITY-fa.md
│   └── TROUBLESHOOTING-fa.md
└── (این گزارش: FINAL-REPORT.md)
```

- **Personal Build**: `release\Personal\TelegramDownloader-Personal[-Setup].exe` → 9/23 06:37 (Setup)، 9/22 14:52 (EXE)
- **Public Build**: `release\Public\TelegramDownloader-Public[-Setup].exe` → 9/23 06:37 (Setup)، 9/22 14:54 (EXE)
- هر دو با Build-Secret صحیح (Personal) و بدون Secret (Public) ساخته و Smoke-Test شده‌اند.

---

## ۶. چگونه دوباره Build کنم؟

پیش‌نیازها: Python 3.12، Inno Setup 6 (مسیر پیش‌فرض)، اعتبارنامه Personal در `secrets\personal.env`
یا env `TDL_API_ID`/`TDL_API_HASH`.

```powershell
# یک بار آماده‌سازی
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pip install pyinstaller

# هر دو نسخه (EXE یک‌فایله + نصب‌کننده)
.\build_all.bat

# یا جداگانه
.\build_personal.bat -Clean
.\build_public.bat -Clean
```

پس از ساخت، `scripts\make_icon.py` و `build\telegram_downloader_onefile.spec` و `installer\setup.iss`
به‌طور خودکار اجرا می‌شوند. خروجی Installer با Inno Setup در `release\<Ed>\\*-Setup.exe` قرار می‌گیرد.

---

© Telegram Downloader — علی خانمحمدی — https://alikhanmohammadi.ir/