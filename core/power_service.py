"""اجرای عملیات پس از اتمام دانلودها (خروج/خاموشی/Restart/Sleep/Hibernate).

امنیت:
  - در حالت Dry-Run (متغیر محیطی TDL_POWER_DRY_RUN یا _build_info.POWER_DRY_RUN)
    هیچ فرمان واقعی اجرا نمی‌شود و فقط پیام نشان‌گر بازگردانده می‌شود.
  - اجرا همیشه از رابط استاندارد ویندوز (shutdown.exe و rundll32) انجام می‌شود
    و خطاها به‌صورت خوانا بازگردانده می‌شوند. در صورت نداشتن مجوز، پیام خطا
    به کاربر نشان داده می‌شود.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable, Optional

from config.edition import POWER_DRY_RUN

logger = logging.getLogger(__name__)

ACTION_NONE = "none"
ACTION_EXIT = "exit"
ACTION_SHUTDOWN = "shutdown"
ACTION_RESTART = "restart"
ACTION_SLEEP = "sleep"
ACTION_HIBERNATE = "hibernate"

VALID_ACTIONS = (
    ACTION_NONE,
    ACTION_EXIT,
    ACTION_SHUTDOWN,
    ACTION_RESTART,
    ACTION_SLEEP,
    ACTION_HIBERNATE,
)

_ACTION_LABELS = {
    ACTION_NONE: "none",
    ACTION_EXIT: "exit",
    ACTION_SHUTDOWN: "shutdown",
    ACTION_RESTART: "restart",
    ACTION_SLEEP: "sleep",
    ACTION_HIBERNATE: "hibernate",
}


def is_valid_action(action: str) -> bool:
    return action in VALID_ACTIONS


def action_key(action: str) -> str:
    return _ACTION_LABELS.get(action, "none")


@dataclass
class PowerResult:
    ok: bool
    dry_run: bool = False
    message: str = ""


class PowerService:
    """اجرای فرمان‌های سیستمی به‌صورت امن (Windows shutdown/restart/sleep/hibernate)."""

    def __init__(self, dry_run: Optional[bool] = None, exit_handler: Optional[Callable[[], None]] = None):
        self.dry_run = POWER_DRY_RUN if dry_run is None else bool(dry_run)
        self.exit_handler = exit_handler

    def execute(self, action: str) -> PowerResult:
        if not is_valid_action(action):
            return PowerResult(False, self.dry_run, f"invalid action: {action!r}")
        if action == ACTION_NONE:
            return PowerResult(True, self.dry_run, "none")
        if action == ACTION_EXIT:
            if self.exit_handler is None:
                return PowerResult(False, self.dry_run, "no exit handler")
            if self.dry_run:
                return PowerResult(True, True, "exit")
            self.exit_handler()
            return PowerResult(True, False, "exit")
        return self._system_action(action)

    def _system_action(self, action: str) -> PowerResult:
        args = self._build_command(action)
        if self.dry_run:
            logger.info("Dry-Run: دستور واقعی اجرا نمی‌شود: %s", " ".join(args))
            return PowerResult(True, True, " ".join(args))
        try:
            kwargs: dict = {"timeout": 20, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
            completed = subprocess.run(args, check=False, **kwargs)
            if completed.returncode != 0:
                msg = f"returncode={completed.returncode}"
                logger.warning("اجرای %s ناموفق بود (%s)", action, msg)
                return PowerResult(False, self.dry_run, msg)
            return PowerResult(True, False, " ".join(args))
        except Exception as exc:  # noqa: BLE001
            logger.warning("اجرای %s ناموفق بود: %s", action, exc)
            return PowerResult(False, self.dry_run, str(exc))

    def _build_command(self, action: str) -> list[str]:
        if sys.platform != "win32":  # pragma: no cover - فقط ویندوز
            if action == ACTION_SHUTDOWN:
                return ["shutdown", "-h", "now"]
            if action == ACTION_RESTART:
                return ["shutdown", "-r", "now"]
            return ["true"]
        if action in (ACTION_SHUTDOWN, ACTION_RESTART):
            flag = "/s" if action == ACTION_SHUTDOWN else "/r"
            # /t 5 اجازه می‌دهد فرآیند خاموشی شروع شود؛ /f باعث بستن پنجره‌ها می‌شود.
            return ["shutdown.exe", flag, "/t", "5", "/f"]
        if action == ACTION_HIBERNATE:
            # Hibernate=TRUE
            return ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,0,0"]
        if action == ACTION_SLEEP:
            # Hibernate=FALSE -> Sleep
            return ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"]
        raise ValueError(action)  # pragma: no cover
