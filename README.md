# دانلودر تلگرام — Telegram Downloader / File Manager / Personal Cloud

برنامه دسکتاپ ویندوز (Python 3.12 + PySide6 + Telethon) برای دانلود، مدیریت و سازمان‌دهی
فایل‌های قابل‌دسترس حساب تلگرام — از یک Downloader ساده به یک **Telegram File Manager /
Personal Cloud** کامل ارتقا یافته.

واسط کاربری فارسی، راست‌چین، با تم تیره/روشن/سیستمی.

## امکانات

- **صف دانلود هوشمند**: دانلود موازی (هم‌زمانی قابل تنظیم)، توقف/ادامه، لغو، تلاش مجدد، تلاش مجدد همگانی،
  **اولویت (کم/عادی/بالا)**، **جابجایی به ابتدای صف**، صف **مداوم** (بازیابی «دانلودهای ناتمام» در اجرای بعدی)
- **مدیریت فایل**: مشاهده، جستجو، مرتب‌سازی (نام/حجم/تاریخ/نوع)، پوشه‌بندی، دلخواه، پنهان، زباله،
  چندانتخابی، دانلود گروهی، حذف گروهی، تغییر نام، انتقال به پوشه، باز کردن فایل/پوشه
- **فضاهای من (Multiple Drives)**: اتصال چند فضای تلگرام (Channel / Group / Saved Messages)
  هرکدام با اندیس و آمار مستقل؛ باز کردن در تلگرام
- **همگام‌سازی**: دستی یا **خودکار** (5/15/30/60 دقیقه یا دستی) با مقداردهی در Settings؛
  **Syncing افزایشی** با نگهداری آخرین Message ID
- **مغز داده‌ها (Local Index)**: SQLite شامل متادیتای کامل فایل‌ها (Message ID، Chat، File ID، نام، حجم،
  MIME، Media Type، Caption، تاریخ، مسیر، وضعیت، SHA-256، دلخواه/پنهان/آرشیو/زباله، Folder ID)
  — جستجوی آنی و **مرور آفلاین** بدون نیاز به پرسمان مکرر تلگرام
- **داشبورد**: وضعیت تلگرام، دانلودهای فعال/در انتظار/کامل/ناموفق، حجم کل، فایل‌های اخیر، ظرفیت فضای دیسک
- **تاریخچه دانلود** با جستجو، حذف، پاک‌سازی، باز کردن فایل/پوشه
- **انتگرتی چک**: دانلود ابتدا به `*.part` و پس از تأیید SHA-256 → نام نهایی؛ «بررسی سلامت فایل»
- **تشخیص تکراری**: Skip / Replace / Rename / Keep Both (بر پایه Hash در صورت وجود)
- **سینی سیستم**: توقف/ادامه همگانی، ماندن در Tray هنگام بستن/کمینه‌کردن، اعلان‌ها
- **عملکرد پس از پایان صف**: خروج / Shutdown / Restart / Sleep / Hibernate با شمارش معکوس، لغو و تأیید نهایی
- **محدود کردن سرعت** دانلود، **زمان‌بندی دانلود** (شبانه)، **پروکسی (SOCKS5/HTTP/MTProto)**
- **چند حساب** تلگرام، **کد امن نشست** (Session رمزنگاری‌شده)، ورود با 2FA
- **Export / Import تنظیمات** (با گزینه رمزنگاری‌شده)، **خروجی متادیتای اندیس** (JSON)
- **بررسی خودکار بروزرسانی** از URL قابل تنظیم (بدون جایگزینی بدون اجازه)
- **میان‌برهای صفحه‌کلید**: `Ctrl+F` جستجو، `Ctrl+V`/`Ctrl+Enter` افزودن لینک، `Ctrl+Shift+V` از کلیپ‌بورد
- **Design**: سایدبار کامل (خانه/صف/فایل‌ها/فضاهای من/تاریخچه/تنظیمات/درباره…)

Feature Flags (ماژول‌های اختیاری) در `config/features.py`:
`ENABLE_BACKUP`، `ENABLE_ENCRYPTION`، `ENABLE_STREAMING`، `ENABLE_ANDROID`.

## دو نسخه (Build)

| | نسخه Personal | نسخه Public |
|---|---|---|
| API ID / Hash | در زمان Build از `secrets\personal.env` تزریق می‌شود | کاربر در ویزارد اولین اجرا وارد می‌کند |
| اعتبارنامه Build | خارج از Source (gitignored) | خیر — Build بدون اعتبارنامه |
| ساخت | `build_personal.bat` | `build_public.bat` |
| خروجی | `release\Personal\TelegramDownloader-Personal[-Setup].exe` | `release\Public\TelegramDownloader-Public[-Setup].exe` |

هر دو نصب‌کننده Inno Setup هنگام Uninstall از کاربر می‌پرسند که داده‌ها نیز حذف شوند یا خیر
(Clean Uninstall). نسخه Portable: همان `.exe` یک‌فایله یا بسته‌های `*-Portable.zip`.

## ساخت نسخه‌ها

نیازمندی‌ها: Python 3.12 (venv)، PyInstaller، Inno Setup 6.

```bat
:: هر دو نسخه
build_all.bat

:: یا جداگانه
build_personal.bat
build_public.bat
```

اعتبارنامه Personal از `TDL_API_ID` / `TDL_API_HASH` یا فایل gitignored `secrets\personal.env` خوانده
می‌شود. هیچ اعتبارنامه‌ای در Source قرار نمی‌گیرد؛ `config\_build_info.py` تولیدی و پوشه `secrets\` در Git نیستند.

## طراحی رابط کاربری (Design System)

همه صفحات از کامپوننت‌های مشترک gui/components.py استفاده می‌کنند تا کد تکراری و ظاهر ناهمگون ایجاد نشود:

| کامپوننت | کاربرد |
| --- | --- |
| KpiCard | کارت آماری داشبورد (آیکون + مقدار + وضعیت) |
| StatusBadge | نشان رنگی وضعیت (دانلود/توقف/تکمیل/خطا/لغو) |
| ProgressCard | کارت پیشرفت با بازه، سرعت و زمان مانده |
| EmptyState | حالت خالی حرفه‌ای با آیکون و یک اقدام اصلی |
| SectionHeader | سربرگ بخش با عنوان و توضیح |
| AppButton | دکمه شرکت با آیکون + برچسب فارسی |
| DeveloperFooter | فوتر برند با نام توسعه‌دهنده و وب‌سایت |

رنگ‌های وضعیت از تم مرکزی (gui/theme.py) می‌آیند، بنابراین در تم روشن/تیره یکدست می‌مانند.
ممیزی خودکار رابط با دستور زیر انجام می‌شود:

    python build/ui_audit.py

## برند و هویت

- در فوتر همه صفحات، دیالوگ About، و مشخصات فایل EXE/Installer نمایش داده می‌شود.
- خروجی مخزن عمومی با دستور زیر ساخته می‌شود و هیچ Secret یا باینری Personal ندارد:

    python scripts/export_public_repo.py

## تست و کیفیت

```bat
python -m pytest -q
python -m ruff check .
```

## اطلاعات توسعه‌دهنده

- **برنامه‌نویس**: علی خانمحمدی (Ali Khanmohammadi) — Software Developer & IT Specialist
- **وب‌سایت**: https://alikhanmohammadi.ir/

---

© Telegram Downloader — نسخه 1.1.0 — Ali Khanmohammadi
