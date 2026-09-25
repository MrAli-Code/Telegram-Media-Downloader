"""جادوگر تنظیمات اولیه (Wizard) با پشتیبانی از Edition شخصی/عمومی.

    - Personal: اعتبارنامه در Build تزریق شده؛ مستقیماً صفحه شماره تلفن.
    - Public:   ابتدا صفحه «تنظیم اتصال Telegram» (API ID/Hash) نمایش داده می‌شود.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from config.api_credentials import API_HASH, API_ID
from config.edition import current as current_edition
from gui.widgets import Toast, set_btn_type
from utils.i18n import t

logger = logging.getLogger(__name__)


class _Page(QWidget):
    submit = Signal()

    def __init__(self):
        super().__init__()
        self._lay = QVBoxLayout(self)
        self._lay.setSpacing(12)

    def body(self, widget: QWidget, stretch: int = 0) -> None:
        self._lay.addWidget(widget, stretch)


class SetupWizard(QDialog):
    """نمایش جادوگر تنظیمات اولیه و ورود به حساب تلگرام."""

    def __init__(self, service, parent: QWidget | None = None):
        super().__init__(parent)
        self._service = service
        self._edition = current_edition()
        self._succeeded = False
        self._btn_phone: QPushButton | None = None
        self._btn_phone_label = ""

        self.setWindowTitle(t("wizard.title") + f" — {self._edition.display_name}")
        self.setMinimumWidth(540)
        self.setModal(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        header = QVBoxLayout()
        title = QLabel(t("wizard.title"))
        title.setObjectName("title")
        self.lbl_subtitle = QLabel()
        self.lbl_subtitle.setObjectName("subtitle")
        self.lbl_subtitle.setWordWrap(True)
        header.addWidget(title)
        header.addWidget(self.lbl_subtitle)
        root.addLayout(header)

        self.stack = QStackedWidget()
        self._pages: list[_Page] = []
        self._index_api: int | None = None
        self._index_phone = 0
        self._index_code = 0
        self._index_password = 0
        self._index_done = 0

        self._build_pages()
        root.addWidget(self.stack)

        self.lbl_status = QLabel()
        self.lbl_status.setObjectName("errorText")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.hide()
        root.addWidget(self.lbl_status)

        self.toast = Toast(self)
        service.login_event.connect(self._on_login_event)

    # ------------------------------------------------------------------ pages
    def _build_pages(self) -> None:
        public = self._edition.show_api_wizard
        if public:
            api_page = self._build_api_page()
            self._index_api = 0
            self._index_phone = 1
            self._pages.append(api_page)
        else:
            self._index_phone = 0

        phone_page = self._build_phone_page()
        code_page = self._build_code_page()
        password_page = self._build_password_page()
        done_page = self._build_done_page()

        self._pages.extend([phone_page, code_page, password_page, done_page])
        self._index_code = self._index_phone + 1
        self._index_password = self._index_code + 1
        self._index_done = self._index_password + 1

        for page in self._pages:
            self.stack.addWidget(page)

        default = self._edition.show_api_wizard and bool(not API_ID or not API_HASH)
        first_page = self._index_api if default else self._index_phone
        self._set_page(first_page if first_page is not None else 0)
        if public:
            self.lbl_subtitle.setText(t("wizard.api.desc"))
        else:
            self.lbl_subtitle.setText(t("wizard.phone.label"))

    def _build_api_page(self) -> _Page:
        page = _Page()
        hint = QLabel(t("wizard.api.desc"))
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        page.body(hint)
        page.body(self._field_row(t("wizard.api.id"), self._make_input(placeholder="12345678")))
        page.body(self._field_row(t("wizard.api.hash"), self._make_input(placeholder=t("wizard.hash_ph"))))
        self.inp_api_id = self._find_input(page, 0)
        self.inp_api_hash = self._find_input(page, 1)
        btn_open = QPushButton(t("wizard.api.open"))
        btn_open.setProperty("btnType", "ghost")
        set_btn_type(btn_open, "ghost")
        btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open.clicked.connect(self._open_telegram_org)
        page.body(btn_open)
        page.body(self._action_row(t("wizard.login"), "primary", self._on_api_next))
        return page

    def _build_phone_page(self) -> _Page:
        page = _Page()
        hint = QLabel(t("wizard.phone.label"))
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        page.body(hint)
        page.body(self._field_row(t("wizard.phone.label"), self._make_input(placeholder="989123456789")))
        self.inp_phone = self._find_input(page, 0)
        holder = self._action_row(t("wizard.login"), "primary", self._on_request_code)
        page.body(holder)
        if self._edition.show_api_wizard:
            btn_api = QPushButton(t("wizard.api.title"))
            btn_api.setProperty("btnType", "ghost")
            set_btn_type(btn_api, "ghost")
            target = self._index_api if self._index_api is not None else 0
            btn_api.clicked.connect(lambda: self._set_page(target))
            page.body(btn_api)
        btn = holder.findChild(QPushButton)
        if isinstance(btn, QPushButton):
            self._btn_phone = btn
            self._btn_phone_label = btn.text()
        return page

    def _build_code_page(self) -> _Page:
        page = _Page()
        self.lbl_code_msg = QLabel()
        self.lbl_code_msg.setObjectName("muted")
        self.lbl_code_msg.setWordWrap(True)
        page.body(self.lbl_code_msg)
        page.body(self._field_row(t("wizard.code.label"), self._make_input(placeholder=t("wizard.code_ph"))))
        self.inp_code = self._find_input(page, 0)
        page.body(self._action_row(t("wizard.login"), "primary", self._on_submit_code))
        return page

    def _build_password_page(self) -> _Page:
        page = _Page()
        hint = QLabel(t("wizard.password_required"))
        hint.setObjectName("muted")
        page.body(hint)
        page.body(self._field_row(t("wizard.password.placeholder"), self._make_input(echo="•")))
        self.inp_password = self._find_input(page, 0)
        page.body(self._action_row(t("wizard.login"), "primary", self._on_submit_password))
        return page

    def _build_done_page(self) -> _Page:
        page = _Page()
        ok = QLabel("✓")
        ok.setObjectName("title")
        ok.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note = QLabel(t("wizard.done"))
        note.setObjectName("subtitle")
        note.setWordWrap(True)
        page.body(ok)
        page.body(note)
        page.body(self._action_row(t("wizard.login"), "primary", self._on_done))
        return page

    # ------------------------------------------------------------------ helpers
    def _open_telegram_org(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl("https://my.telegram.org/auth"))

    @staticmethod
    def _make_input(placeholder: str = "", echo: str = "") -> QLineEdit:
        inp = QLineEdit()
        inp.setPlaceholderText(placeholder)
        if echo:
            inp.setEchoMode(QLineEdit.EchoMode.Password)
        return inp

    @staticmethod
    def _field_row(label_text: str, widget: QWidget) -> QWidget:
        row = QHBoxLayout()
        lab = QLabel(label_text)
        lab.setObjectName("muted")
        lab.setMinimumWidth(120)
        row.addWidget(lab)
        row.addWidget(widget, 1)
        holder = QWidget()
        holder.setLayout(row)
        return holder

    def _action_row(self, text: str, kind: str, callback) -> QWidget:
        box = QDialogButtonBox()
        btn = box.addButton(text, QDialogButtonBox.ButtonRole.AcceptRole)
        btn.setProperty("btnType", kind)
        set_btn_type(btn, kind)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(callback)
        holder = QWidget()
        lay_box = QVBoxLayout(holder)
        lay_box.setContentsMargins(0, 0, 0, 0)
        lay_box.addWidget(box)
        return holder

    def _find_input(self, page: _Page, index: int) -> QLineEdit:
        inputs: list[QLineEdit] = list(page.findChildren(QLineEdit))
        return inputs[index]

    # ------------------------------------------------------------------ actions
    def _show_status(self, message: str) -> None:
        self.lbl_status.setText(message)
        self.lbl_status.show()

    def _clear_status(self) -> None:
        self.lbl_status.hide()
        self.lbl_status.clear()

    def _set_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)

    def _on_api_next(self) -> None:
        api_id = self.inp_api_id.text().strip()
        api_hash = self.inp_api_hash.text().strip()
        if not api_id.isdigit():
            self._show_status(t("wizard.numeric"))
            return
        if len(api_hash) != 32:
            self._show_status(t("wizard.api_hash_error"))
            return
        self._saved_api_id = api_id
        self._saved_api_hash = api_hash
        self._clear_status()
        self._set_page(self._index_phone)

    def _request_credentials(self) -> tuple[str, str]:
        saved = getattr(self, "_saved_api_id", "")
        if saved:
            return saved, self._saved_api_hash
        return str(API_ID if API_ID else ""), str(API_HASH or "")

    def _on_request_code(self) -> None:
        phone = self.inp_phone.text().strip()
        if not phone:
            self._show_status(t("wizard.phone_empty"))
            return
        api_id, api_hash = self._request_credentials()
        if not api_id.isdigit() or not api_hash:
            self._show_status(t("wizard.api.desc"))
            target = self._index_api if self._index_api is not None else 0
            self._set_page(target)
            return
        self._clear_status()
        self._set_btn_busy(True)
        self._service.begin_login(int(api_id), api_hash, phone)

    def _on_submit_code(self) -> None:
        code = self.inp_code.text().strip()
        if not code:
            self._show_status(t("wizard.code_needed"))
            return
        self._clear_status()
        self._service.submit_code(code)

    def _on_submit_password(self) -> None:
        password = self.inp_password.text()
        if not password:
            self._show_status(t("wizard.pass_needed"))
            return
        self._clear_status()
        self._service.submit_password(password)

    def _on_done(self) -> None:
        self._succeeded = True
        self.accept()

    def _set_btn_busy(self, busy: bool) -> None:
        if self._btn_phone is None:
            return
        self._btn_phone.setText(t("wizard.done") if busy else self._btn_phone_label)
        self._btn_phone.setEnabled(not busy)

    # ------------------------------------------------------------------ events
    def _on_login_event(self, kind: str, payload) -> None:
        if kind == "connecting":
            self._show_status(t("wizard.connecting"))
        elif kind == "ask_code":
            self._set_btn_busy(False)
            self.lbl_code_msg.setText((payload or {}).get("message", t("wizard.code_sent")))
            self._clear_status()
            self._set_page(self._index_code)
        elif kind == "ask_password":
            self._clear_status()
            self._set_page(self._index_password)
        elif kind == "authorized":
            self._clear_status()
            self._set_page(self._index_done)
        elif kind == "error":
            self._set_btn_busy(False)
            self._show_status(str((payload or {}).get("message", t("wizard.error", error=""))))
            if (payload or {}).get("retry_code"):
                self._set_page(self._index_code)

    @staticmethod
    def run(service, parent: QWidget | None = None) -> bool:
        wiz = SetupWizard(service, parent)
        wiz.exec()
        return wiz._succeeded