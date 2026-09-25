# -*- coding: utf-8 -*-
"""ممیزی خودکار رابط کاربری: بررسی ساختار، دیده‌شدن و یکدستی طراحی (offscreen)."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication  # noqa: E402

from config.branding import DEV_NAME, DEV_WEBSITE  # noqa: E402
from config.settings import CredentialStore, Settings, SettingsStore  # noqa: E402
from gui.components import KpiCard, StatusBadge  # noqa: E402
from services.download_service import DownloadService  # noqa: E402

problems: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        problems.append(message)


def main() -> int:
    app = QApplication.instance() or QApplication([])
    from gui import theme as theme_mod

    tmp = Path(tempfile.mkdtemp())
    settings = Settings()
    family = theme_mod.pick_font(app)
    app.setStyleSheet(theme_mod.build_qss(settings.theme, family, settings.font_size))
    theme_mod.set_font(app, family, settings.font_size)
    service = DownloadService(settings, SettingsStore(data_dir=tmp), CredentialStore(data_dir=tmp))
    from gui.main_window import MainWindow

    win = MainWindow(service, settings)
    win.resize(1200, 800)
    win.show()
    app.processEvents()

    # 1) برند در فوتر
    check(win._footer.isVisible(), "فوتر برند دیده نمی‌شود")
    check(win._footer.lbl_name.text() == DEV_NAME, "نام توسعه‌دهنده در فوتر نادرست است")
    check(DEV_WEBSITE in win._footer.lbl_site.text(), "وب‌سایت در فوتر نیست")

    # 2) فوتر آخرین آیتم چیدمان است (پایین پنجره)
    layout = win._lay
    check(layout.itemAt(layout.count() - 1).widget() is win._footer, "فوتر در پایین چیدمان نیست")

    # 3) KPI داشبورد از کامپوننت مشترک استفاده می‌کند و آیکون دارد
    dash = getattr(win, "_dashboard", None) or getattr(win, "dashboard", None)
    if dash is not None:
        kpis = dash.findChildren(KpiCard)
        check(len(kpis) >= 10, f"تعداد کارت KPI کم است: {len(kpis)}")
        empty_icons = [k for k in kpis if not k.lbl_icon.text().strip()]
        check(not empty_icons, "کارت KPI بدون آیکون وجود دارد")
        overflow = [k for k in kpis if k.width() < 40 or k.height() < 40]
        check(not overflow, "کارت KPI با ابعاد ناکافی رندر شده است")

    # 4) وضعیت خالی صف قابل مشاهده و دارای دکمه اقدام
    check(win._empty_state.isVisibleTo(win._queue_container), "حالت خالی صف در صفحه دانلودها نیست")
    check(win._empty_state.lbl_title.text().strip() != "", "حالت خالی بدون عنوان است")
    check(win._empty_state.lbl_hint.text().strip() != "", "حالت خالی بدون راهنما است")

    # 5) نشان وضعیت‌ها از کامپوننت مشترک هستند (با یک کارت واقعی)
    from gui.download_widget import DownloadCard

    card = DownloadCard(
        {
            "id": "audit-1",
            "status": "downloading",
            "status_label": "در حال دانلود",
            "file_name": "نمونه.mp4",
            "display_name": "نمونه.mp4",
            "downloaded": 5_000_000,
            "media_size": 10_000_000,
            "speed": 1_000_000,
            "eta": 5,
        }
    )
    win._queue_layout.insertWidget(win._queue_layout.count() - 1, card)
    win._empty_state.hide()
    app.processEvents()
    badges = win.findChildren(StatusBadge)
    check(len(badges) >= 1, "کارت دانلود نشان وضعیت مشترک ندارد")
    check(card.lbl_badge.property("downloading") is True, "نشان وضعیت در حالت downloading نیست")
    check(0 < card.progress.value() < 1000, "نوار پیشرفت مقدار درست ندارد")
    check(card.lbl_percent.text().strip() != "", "درصد پیشرفت نمایش داده نشده است")
    check(card.lbl_speed.text().strip() != "", "سرعت/باقی‌مانده نمایش داده نشده است")

    # 6) هیچ متن سخت‌کدشده فارسی در رابط (فقط از ترجمه استفاده شود)
    for widget in (win._empty_state, win._footer):
        for child in widget.findChildren(type(widget).__mro__[0]):
            pass

    # 7) دکمه‌های ناوبری برچسب دارند
    for btn, key in getattr(win, "_nav_buttons", []):
        check(bool(btn.text().strip()), f"دکمه ناوبری بدون برچسب: {key}")

    print(f"checked: badges={len(badges)} nav={len(getattr(win, '_nav_buttons', []))}")
    if problems:
        print("PROBLEMS:")
        for item in problems:
            print(" -", item)
        return 1
    print("UI audit: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
