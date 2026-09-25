# نسخه همراه اندروید (Companion)

این اسکلت مخصوص آماده‌سازی نسخه همراه برای اندروید است. هدف: به اشتراک‌گذاری
لینک/فایل از گوشی به کامپیوتر، ادامه دانلود، و آپلود فایل به فضای تلگرام.

## وضعیت

- اسکلت ماژولار در پوشه `android/` پیاده‌سازی و روی دسکتاپ قابل اجرا/آزمون است.
- پرچم `ENABLE_ANDROID` در `config/features.py` (پیش‌فرض `False`) کنترل می‌شود.
- ساخت APK واقعی در این محیط امکان‌پذیر نیست (نیازمند Android SDK/NDK).

## ماژول‌ها

| فایل | نقش |
| --- | --- |
| `android/paths.py` | مسیرهای داده/کش/دانلود (معادل اندروید و دسکتاپ) |
| `android/share_action.py` | استخراج لینک‌های t.me / tgdrive از اشتراک‌گذاری |
| `android/worker.py` | صف آپلود چندبخشی و حدس مقصد بر اساس نوع فایل |
| `android/notifier.py` | اعلان‌های سیستم (با fallback توست روی دسکتاپ) |
| `buildozer.spec` | پیکربندی Buildozer برای آینده |

## آزمون

```powershell
.venv\Scripts\python.exe -m pytest tests\test_android_scaffold.py -q
```

## ساخت APK (در محیطی دارای Buildozer)

```bash
pip install buildozer
buildozer init   # یا از buildozer.spec فعلی استفاده شود
buildozer android debug
```

پس از فعال‌شدن `ENABLE_ANDROID=True`، نقطه ورود `android/main.py` باید ساخته شود تا
لینک‌های دریافتی را به صف دانلود همان ساختار دسکتاپ منتقل کند.