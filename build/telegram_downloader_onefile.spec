# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller Spec - One File build for a specific edition.

Reads edition data from the generated config/_build_info.py so the EXE name
and version metadata match the current build profile (Personal / Public).
"""

import os
import re
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    from config.branding import DEV_NAME as _DEV_NAME
    from config.branding import DEV_WEBSITE as _DEV_WEBSITE
    from config.edition import current as _current

    _INFO = _current()
    APP_NAME = _INFO.exe_name
    PRODUCT_NAME = _INFO.display_name
    APP_VERSION = _INFO.app_version
except Exception:  # noqa: BLE001 - fallback for manual spec runs
    _INFO = None
    _DEV_NAME = "Ali Khanmohammadi"
    _DEV_WEBSITE = "https://alikhanmohammadi.ir/"
    APP_NAME = "TelegramDownloader"
    PRODUCT_NAME = "Telegram Downloader"
    APP_VERSION = "1.0.1"


def _edition_version_info(product: str, version: str, company: str, exe_name: str = ""):
    try:
        from PyInstaller.utils.win32.versioninfo import (
            FixedFileInfo,
            StringFileInfo,
            StringStruct,
            StringTable,
            VarFileInfo,
            VarStruct,
            VSVersionInfo,
        )
    except Exception:  # noqa: BLE001
        return None

    m = re.match(r"^(\d+)\.(\d+)(?:\.(\d+))?", version)
    parts = [int(g) for g in (m.groups() if m else ("1", "0", "0"))] + [0]
    vv = (parts[0], parts[1], parts[2], 0)
    return VSVersionInfo(
        ffi=FixedFileInfo(
            filevers=vv,
            prodvers=vv,
            mask=0x3F,
            flags=0x0,
            OS=0x40004,
            fileType=0x1,
            subtype=0x0,
            date=(0, 0),
        ),
        kids=[
            StringFileInfo(
                [
                    StringTable(
                        "040904B0",
                        [
                            StringStruct("CompanyName", company),
                            StringStruct("FileDescription", product + " - by " + _DEV_NAME),
                            StringStruct("FileVersion", version),
                            StringStruct("InternalName", exe_name or product),
                            StringStruct("LegalCopyright", "(c) " + _DEV_NAME + " - " + _DEV_WEBSITE),
                            StringStruct("OriginalFilename", (exe_name or product) + ".exe"),
                            StringStruct("ProductName", product),
                            StringStruct("ProductVersion", version),
                        ],
                    )
                ]
            ),
            VarFileInfo([VarStruct("Translation", [1033, 1200])]),
        ],
    )


datas = [
    (os.path.join(ROOT, "resources", "icons", "app.ico"), "resources/icons"),
    (os.path.join(ROOT, "resources", "icons", "app.png"), "resources/icons"),
    (os.path.join(ROOT, "locales"), "locales"),
]

a = Analysis(
    [os.path.join(ROOT, "app.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "PIL._tkinter_finder",
        "socks"
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(ROOT, "resources", "icons", "app.ico"),
    version=_edition_version_info(PRODUCT_NAME, APP_VERSION, _DEV_NAME, APP_NAME)
    if _INFO is not None
    else None,
)