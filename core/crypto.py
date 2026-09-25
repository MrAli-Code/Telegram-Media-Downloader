"""رمزنگاری اختیاری: AES-256-GCM برای محتوا، اشتقاق کلید از عبارت بازیابی و لفاف کلید با DPAPI.

این ماژول پیاده‌سازی مستقل به زبان پایتون از الگوی امنیتی TeleDrive است (Apache-2.0، فقط اقتباس الگو و بدون کپی کد).
قالب بسته هر بدنه رمزشده: ۱ بایت نسخه + ۱۲ بایت nonce + متن رمزشده + ۱۶ بایت تگ GCM.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import struct
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from utils.security import decrypt_bytes, encrypt_bytes

VERSION = 1
HEADER = 1 + 12  # نسخه + nonce
TAG = 16
CHUNK = 1024 * 1024
PBKDF2_ITERATIONS = 310_000
SALT_SIZE = 16

KEY_BYTES = 32


class CipherError(Exception):
    """خطای رمزنگاری (کلید نادرست یا داده خراب)."""


def new_content_key() -> bytes:
    """تولید کلید محتوای تصادفی ۲۵۶ بیتی."""
    return os.urandom(KEY_BYTES)


def encrypt_bytes_gcm(key: bytes, plaintext: bytes) -> bytes:
    """رمز کردن بایت‌ها با AES-256-GCM؛ الگوی nonce به فرمت سراسری ماژول."""
    _check_key(key)
    nonce = os.urandom(12)
    cipher = AESGCM(key)
    return VERSION.to_bytes(1, "big") + nonce + cipher.encrypt(nonce, plaintext, None)


def decrypt_bytes_gcm(key: bytes, token: bytes) -> bytes:
    """رمزگشایی بسته ساخته‌شده توسط encrypt_bytes_gcm؛ داده دستکاری‌شده خطا می‌دهد."""
    _check_key(key)
    if len(token) < HEADER + TAG or token[0] != VERSION:
        raise CipherError("بسته رمزشده معتبر نیست (نسخه یا اندازه نادرست).")
    nonce = token[1 : 1 + 12]
    body = token[1 + 12 :]
    try:
        return AESGCM(key).decrypt(nonce, body, None)
    except Exception as exc:  # noqa: BLE001
        raise CipherError("رمزگشایی ناموفق بود؛ کلید نادرست است یا داده دستکاری شده.") from exc


def derive_passphrase_key(passphrase: str, salt: bytes) -> bytes:
    """اشتقاق کلید ۲۵۶ بیتی از عبارت بازیابی (PBKDF2-HMAC-SHA256، تکرار ۳۱۰هزار)."""
    if not passphrase:
        raise CipherError("عبارت بازیابی نمی‌تواند خالی باشد.")
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=KEY_BYTES, salt=salt, iterations=PBKDF2_ITERATIONS)
    return kdf.derive(passphrase.encode("utf-8"))


def wrap_key_dpapi(secret_key: bytes) -> str:
    """لفاف کلید محتوا با کلید حاکم پلتفرم (DPAPI در ویندوز) برای ذخیره محلی."""
    _check_key(secret_key)
    return base64.b64encode(encrypt_bytes(secret_key)).decode("ascii")


def unwrap_key_dpapi(token: str) -> bytes:
    """بازکردن کلید محتوا از لفاف DPAPI."""
    try:
        return decrypt_bytes(base64.b64decode(token.encode("ascii")))
    except Exception as exc:  # noqa: BLE001
        raise CipherError("کلید محتوا قابل بازکردن نیست (کاربر یا ماشین متفاوت است).") from exc


def build_recovery_manifest(secret_key: bytes, passphrase: str, hint: str = "") -> dict:
    """ساخت مانیفست بازیابی: کلید محتوا با عبارت بازیابی لفاف می‌شود و در Telegram ذخیره قابل استناد است."""
    _check_key(secret_key)
    salt = os.urandom(SALT_SIZE)
    key = derive_passphrase_key(passphrase, salt)
    envelope = encrypt_bytes_gcm(key, secret_key)
    return {
        "version": VERSION,
        "kdf": "pbkdf2-sha256",
        "iterations": PBKDF2_ITERATIONS,
        "salt": base64.b64encode(salt).decode("ascii"),
        "envelope": base64.b64encode(envelope).decode("ascii"),
        "hint": hint.strip()[:200],
    }


def restore_secret_key(manifest: dict, passphrase: str) -> bytes:
    """بازیابی کلید محتوا از مانیفست بازیابی با وارد کردن عبارت درست."""
    try:
        salt = base64.b64decode(str(manifest["salt"]))
        envelope = base64.b64decode(str(manifest["envelope"]))
        key = derive_passphrase_key(passphrase, salt)
        secret = decrypt_bytes_gcm(key, envelope)
    except (KeyError, ValueError, CipherError) as exc:
        raise CipherError("بازیابی ناموفق بود؛ عبارت بازیابی نادرست است یا مانیفست خراب است.") from exc
    _check_key(secret)
    return secret


def encrypt_file_gcm(secret_key: bytes, src: Path, dst: Path) -> None:
    """رمز کردن یک فایل محلی به شکل جریانی (حافظه ثابت): هر قطعه ۱ مگابایتی به‌صورت مستقل GCM می‌شود."""
    _check_key(secret_key)
    src = Path(src)
    dst = Path(dst)
    size = src.stat().st_size
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    with src.open("rb") as fin, tmp.open("wb") as fout:
        cipher = AESGCM(secret_key)
        fout.write(struct.pack("<I", size))
        index = 0
        while True:
            block = fin.read(CHUNK)
            if not block:
                break
            nonce = _chunk_nonce(index)
            fout.write(cipher.encrypt(nonce, block, None))
            index += 1
    os.replace(tmp, dst)


def decrypt_file_gcm(secret_key: bytes, src: Path, dst: Path) -> None:
    """رمزگشایی جریانی یک فایل رمزشده با encrypt_file_gcm."""
    _check_key(secret_key)
    src = Path(src)
    dst = Path(dst)
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    try:
        with src.open("rb") as fin, tmp.open("wb") as fout:
            cipher = AESGCM(secret_key)
            raw = fin.read(4)
            if len(raw) != 4:
                raise CipherError("فایل رمزشده ناقص است.")
            (size,) = struct.unpack("<I", raw)
            index = 0
            written = 0
            while True:
                block = fin.read(CHUNK + TAG)
                if not block:
                    break
                try:
                    plain = cipher.decrypt(_chunk_nonce(index), block, None)
                except Exception as exc:  # noqa: BLE001
                    raise CipherError("رمزگشایی فایل ناموفق بود؛ فایل خراب یا کلید نادرست است.") from exc
                fout.write(plain)
                written += len(plain)
                index += 1
            if written < size:
                raise CipherError("فایل رمزشده ناقص است.")
    except CipherError:
        tmp.unlink(missing_ok=True)
        raise
    os.replace(tmp, dst)


def _chunk_nonce(index: int) -> bytes:
    return hashlib.sha256(index.to_bytes(8, "big")).digest()[:12]


def _check_key(key: bytes) -> None:
    if not isinstance(key, bytes) or len(key) != KEY_BYTES:
        raise CipherError("کلید باید ۲۵۶ بیت (۳۲ بایت) باشد.")


def manifest_to_json(manifest: dict) -> str:
    return json.dumps(manifest, ensure_ascii=False, indent=2)


def manifest_from_json(text: str) -> dict:
    data = json.loads(text)
    if not isinstance(data, dict) or "envelope" not in data:
        raise CipherError("مانیفست بازیابی معتبر نیست.")
    return data


def _repr_dumps(data: Any) -> str:  # pragma: no cover - کمکی
    return json.dumps(data, ensure_ascii=False)