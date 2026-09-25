"""پوسته (تم) تیره/روشن/سیستمی و فونت برنامه."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Optional

from PySide6.QtGui import QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication, QWidget


@dataclass
class Palette:
    bg: str
    bg_card: str
    bg_input: str
    bg_hover: str
    border: str
    text: str
    muted: str
    accent: str
    accent_hover: str
    accent_pressed: str
    danger: str
    success: str
    warn: str
    badge_info: str
    # دکمه‌ها: بدنه واضح برای دکمه پیش‌فرض و دکمه ثانویه (ghost)
    btn_bg: str
    btn_border: str
    btn_hover: str
    btn_pressed: str
    btn_fg: str
    ghost_bg: str
    ghost_border: str
    ghost_fg: str


DARK = Palette(
    bg="#14181f",
    bg_card="#1e2430",
    bg_input="#171c26",
    bg_hover="#2a3242",
    border="#303a4a",
    text="#eef2f9",
    muted="#96a2b4",
    accent="#2aabee",
    accent_hover="#42b9f7",
    accent_pressed="#187fb3",
    danger="#f0565a",
    success="#2ecc8f",
    warn="#f3b743",
    badge_info="#3b82f6",
    btn_bg="#2c3548",
    btn_border="#45536e",
    btn_hover="#3a465e",
    btn_pressed="#222a3b",
    btn_fg="#f4f7fc",
    ghost_bg="#212939",
    ghost_border="#3c4a5d",
    ghost_fg="#c9d3e0",
)

LIGHT = Palette(
    bg="#f2f4f8",
    bg_card="#ffffff",
    bg_input="#f7f9fc",
    bg_hover="#eef2f7",
    border="#d9dfea",
    text="#1b2330",
    muted="#64708a",
    accent="#1f9bef",
    accent_hover="#1283d8",
    accent_pressed="#0e6fb2",
    danger="#e5484d",
    success="#17a673",
    warn="#d89116",
    badge_info="#1f6feb",
    btn_bg="#ffffff",
    btn_border="#c3cddd",
    btn_hover="#f0f4fa",
    btn_pressed="#e2e8f1",
    btn_fg="#1b2330",
    ghost_bg="#e9eef5",
    ghost_border="#cdd5e3",
    ghost_fg="#42506a",
)

FONT_CANDIDATES = ["Vazirmatn", "Segoe UI", "Tahoma", "Arial"]


def system_is_dark() -> bool:
    """تشخیص حالت روشن/تیره ویندوز (رِجیستری Windows یا پالت Qt)."""
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            ) as key:
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return int(value) == 0
        except OSError:
            pass
    app = QApplication.instance()
    if isinstance(app, QApplication):
        try:
            return app.palette().color(QPalette.ColorRole.Window).lightness() < 128
        except Exception:
            pass
    return False


def resolve_theme(theme: str) -> str:
    """تبدیل مقدار پوسته به dark/light واقعی (پشتیبانی از system)."""
    if theme == "system":
        return "dark" if system_is_dark() else "light"
    return theme if theme in ("dark", "light") else "dark"


def palette(theme: str) -> Palette:
    return DARK if resolve_theme(theme) == "dark" else LIGHT


def build_qss(theme: str, font_family: str, font_size: int) -> str:
    p = palette(theme)
    base = f"""
    * {{ font-family: "{font_family}"; font-size: {font_size}pt; }}
    QMainWindow, QDialog, QWidget#root {{ background: {p.bg}; }}
    QLabel {{ color: {p.text}; background: transparent; }}
    QLabel#muted, QLabel#sub {{ color: {p.muted}; }}
    QLabel#title {{ font-size: {font_size + 6}pt; font-weight: 700; }}
    QLabel#subtitle {{ font-size: {font_size + 1}pt; color: {p.muted}; }}
    QLabel#section {{ font-size: {font_size + 1}pt; font-weight: 700; }}
    QLabel#pathLabel {{ color: {p.muted}; }}
    QLabel#nameText {{ font-weight: 700; }}
    QLabel#errorText {{ color: {p.danger}; }}
    QWidget#brandFooter {{ border-top: 1px solid {p.border}; }}
    QLabel#brandName {{ font-size: {font_size}pt; font-weight: 700; color: {p.text}; }}
    QLabel#brandSite {{ color: {p.accent}; }}
    QLabel#brandTitle {{ color: {p.muted}; }}
    """
    card = f"""
    QFrame#card, QFrame#cardWidget {{
        background: {p.bg_card};
        border: 1px solid {p.border};
        border-radius: 12px;
    }}
    QFrame#card:hover {{ border-color: {p.accent}; }}
    """
    inputs = f"""
    QLineEdit, QComboBox, QSpinBox {{
        background: {p.bg_input};
        color: {p.text};
        border: 1px solid {p.border};
        border-radius: 8px;
        padding: 7px 10px;
        selection-background-color: {p.accent};
        selection-color: #ffffff;
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border: 1px solid {p.accent}; }}
    QLineEdit:hover, QComboBox:hover, QSpinBox:hover {{ border-color: {p.btn_border}; }}
    QLineEdit:disabled, QComboBox:disabled {{ color: {p.muted}; }}
    QComboBox::drop-down {{ border: none; width: 26px; }}
    QComboBox QAbstractItemView, QListView, QTreeView {{
        background: {p.bg_card};
        color: {p.text};
        border: 1px solid {p.border};
        outline: none;
        selection-background-color: {p.accent};
        selection-color: #ffffff;
    }}
    """
    buttons = f"""
    QPushButton {{
        background: {p.btn_bg};
        color: {p.btn_fg};
        border: 1px solid {p.btn_border};
        border-radius: 9px;
        padding: 8px 16px;
        font-weight: 600;
    }}
    QPushButton:hover {{ background: {p.btn_hover}; border-color: {p.accent}; }}
    QPushButton:pressed {{ background: {p.btn_pressed}; }}
    QPushButton:disabled {{ color: {p.muted}; background: transparent; border-color: {p.border}; }}
    QPushButton:focus {{ border-color: {p.accent}; }}
    QPushButton[btnType="primary"] {{
        background: {p.accent}; border: none; color: #ffffff; font-weight: 700;
    }}
    QPushButton[btnType="primary"]:hover {{ background: {p.accent_hover}; }}
    QPushButton[btnType="primary"]:pressed {{ background: {p.accent_pressed}; }}
    QPushButton[btnType="danger"] {{
        background: transparent; color: {p.danger}; border: 1.5px solid {p.danger}; font-weight: 700;
    }}
    QPushButton[btnType="danger"]:hover {{ background: {p.danger}; color: #ffffff; }}
    QPushButton[btnType="danger"]:pressed {{ background: {p.accent_pressed}; border-color: {p.accent_pressed}; }}
    QPushButton[btnType="success"] {{
        background: transparent; color: {p.success}; border: 1.5px solid {p.success}; font-weight: 700;
    }}
    QPushButton[btnType="success"]:hover {{ background: {p.success}; color: #ffffff; }}
    QPushButton[btnType="ghost"] {{
        background: {p.ghost_bg}; color: {p.ghost_fg};
        border: 1px solid {p.ghost_border};
        font-weight: 600;
    }}
    QPushButton[btnType="ghost"]:hover {{
        background: {p.bg_hover}; color: {p.text}; border-color: {p.accent};
    }}
    QPushButton[btnType="ghost"]:pressed {{ background: {p.btn_pressed}; }}
    QToolButton {{
        background: {p.ghost_bg}; color: {p.ghost_fg};
        border: 1px solid {p.ghost_border}; border-radius: 7px; padding: 5px 10px;
    }}
    QToolButton:hover {{ background: {p.bg_hover}; color: {p.text}; border-color: {p.accent}; }}
    """
    progress = f"""
    QProgressBar {{
        background: {p.bg_input};
        border: none;
        border-radius: 5px;
        height: 10px;
        text-align: center;
        color: transparent;
    }}
    QProgressBar::chunk {{
        background: {p.accent}; border-radius: 5px;
    }}
    QProgressBar::chunk[paused="true"] {{ background: {p.warn}; }}
    """
    tables = f"""
    QTableWidget, QTableView {{
        background: {p.bg_card};
        alternate-background-color: {p.bg};
        gridline-color: {p.border};
        color: {p.text};
        border: 1px solid {p.border};
        border-radius: 8px;
        selection-background-color: {p.accent};
        selection-color: #ffffff;
    }}
    QHeaderView::section {{
        background: {p.bg_hover}; color: {p.text};
        border: none; border-bottom: 1px solid {p.border};
        padding: 7px 8px; font-weight: 700;
    }}
    QTableCornerButton::section {{ background: {p.bg_hover}; border: none; }}
    """
    menus = f"""
    QMenu {{
        background: {p.bg_card}; color: {p.text};
        border: 1px solid {p.border}; border-radius: 8px; padding: 6px;
    }}
    QMenu::item {{ padding: 7px 26px 7px 18px; border-radius: 6px; }}
    QMenu::item:selected {{ background: {p.accent}; color: #ffffff; }}
    QMenu::item:disabled {{ color: {p.muted}; }}
    QMenu::separator {{ height: 1px; background: {p.border}; margin: 4px 10px; }}
    QMenu::icon {{ padding-left: 6px; }}
    """
    misc = f"""
    QCheckBox {{ color: {p.text}; spacing: 7px; }}
    QCheckBox::indicator {{ width: 16px; height: 16px; }}
    QCheckBox::indicator:unchecked {{
        border: 1.5px solid {p.btn_border}; border-radius: 4px; background: {p.bg_input};
    }}
    QCheckBox::indicator:unchecked:hover {{ border-color: {p.accent}; }}
    QCheckBox::indicator:checked {{
        background: {p.accent}; border: 1.5px solid {p.accent}; border-radius: 4px;
    }}
    QScrollArea {{ border: none; background: transparent; }}
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
    QScrollBar::handle:vertical {{ background: {p.border}; border-radius: 5px; min-height: 30px; }}
    QScrollBar::handle:vertical:hover {{ background: {p.muted}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
    QScrollBar::handle:horizontal {{ background: {p.border}; border-radius: 5px; min-width: 30px; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
    QTabWidget::pane {{
        border: 1px solid {p.border}; border-radius: 10px; background: {p.bg_card};
    }}
    QTabBar::tab {{
        background: transparent; color: {p.muted};
        padding: 9px 20px; margin-right: 4px;
        border: 1px solid transparent; border-bottom: 2px solid transparent;
        border-top-left-radius: 8px; border-top-right-radius: 8px;
    }}
    QTabBar::tab:hover {{ color: {p.text}; background: {p.bg_hover}; }}
    QTabBar::tab:selected {{
        color: {p.accent}; background: {p.bg}; border-color: {p.border};
        border-bottom: 2px solid {p.accent}; font-weight: 700;
    }}
    QMessageBox {{ background: {p.bg_card}; }}
    QDialogButtonBox {{ spacing: 10px; }}
    QStatusBar {{ background: transparent; color: {p.muted}; }}
    QToolTip {{
        background: {p.bg_card}; color: {p.text};
        border: 1px solid {p.border}; padding: 5px; border-radius: 6px;
    }}
    QSplitter::handle {{ background: {p.border}; }}
    """
    badge = f"""
    QLabel#badge {{
        border-radius: 9px; padding: 2px 10px; font-size: {font_size - 2}pt; font-weight: 600;
    }}
    QLabel#badge[pending="true"] {{ background: {p.badge_info}; color: #ffffff; }}
    QLabel#badge[downloading="true"] {{ background: {p.accent}; color: #ffffff; }}
    QLabel#badge[paused="true"] {{ background: {p.warn}; color: #1b2330; }}
    QLabel#badge[completed="true"] {{ background: {p.success}; color: #ffffff; }}
    QLabel#badge[error="true"] {{ background: {p.danger}; color: #ffffff; }}
    QLabel#badge[cancelled="true"] {{ background: {p.bg_hover}; color: {p.muted}; }}
    """
    nav = f"""
    QPushButton[nav="true"] {{
        background: transparent; color: {p.muted};
        border: none; border-radius: 9px; padding: 9px 16px; font-weight: 600;
    }}
    QPushButton[nav="true"]:hover {{ background: {p.bg_hover}; color: {p.text}; }}
    QPushButton[nav="true"][checked="true"] {{ background: {p.accent}; color: #ffffff; }}
    """
    stats = f"""
    QFrame#statCard {{
        background: {p.bg_card}; border: 1px solid {p.border}; border-radius: 12px;
    }}
    QFrame#statCard:hover {{
        border: 1px solid {p.accent};
    }}
    QLabel#statValue {{
        font-size: {font_size + 3}pt; font-weight: 700; color: {p.accent};
    }}
    QLabel#kpiIcon {{ font-size: {font_size + 2}pt; }}
    QLabel#kpiSub {{ color: {p.muted}; font-size: {max(6, font_size - 1)}pt; }}
    QWidget#emptyState {{
        background: {p.bg_card}; border: 1px solid {p.border}; border-radius: 12px;
    }}
    QLabel#emptyIcon {{ font-size: {font_size + 18}pt; }}
    QLabel#emptyTitle {{ font-size: {font_size + 2}pt; font-weight: 700; color: {p.text}; }}
    QFrame#card > QWidget#emptyState {{ background: transparent; border: none; }}
    """
    return base + card + inputs + buttons + progress + tables + menus + badge + misc + nav + stats


_STATUS_TO_PROP = {
    "pending": ("pending", True),
    "resolving": ("pending", True),
    "downloading": ("downloading", True),
    "paused": ("paused", True),
    "completed": ("completed", True),
    "error": ("error", True),
    "cancelled": ("cancelled", True),
}


def apply_badge_props(widget: QWidget, status: str) -> None:
    """اعمال ویژگی پویا برای رنگ نشان وضعیت (ابتدا همه ویژگی‌های قبلی پاک می‌شوند)."""
    for key in ("pending", "downloading", "paused", "completed", "error", "cancelled"):
        widget.setProperty(key, False)
    key, val = _STATUS_TO_PROP.get(status, ("pending", True))
    widget.setProperty(key, val)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def set_font(app: QApplication, family: str, size: int) -> None:
    font = QFont(family, size)
    app.setFont(font)


def pick_font(app: QApplication, candidates: Optional[list[str]] = None) -> str:
    """انتخاب اولین فونت موجود از فهرست پیشنهادی."""
    installed = set(QFontDatabase.families())
    for name in candidates or FONT_CANDIDATES:
        if name in installed:
            return name
    return "Tahoma"