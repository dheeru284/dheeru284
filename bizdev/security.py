"""Token encryption, password hashing, and log redaction."""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import re

from cryptography.fernet import Fernet

from .config import get_settings


def _fernet() -> Fernet:
    key = get_settings().token_encryption_key
    if not key:
        raise RuntimeError("TOKEN_ENCRYPTION_KEY is not set; refusing to store credentials.")
    return Fernet(key.encode())


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()


def hash_password(pw: str, *, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 390_000)
    return "pbkdf2$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, s, h = stored.split("$")
    except ValueError:
        return False
    return hmac.compare_digest(hash_password(pw, salt=base64.b64decode(s)), stored)


_PATTERNS = [
    (re.compile(r"(?i)(authorization:\s*bearer\s+)[A-Za-z0-9._~+/=-]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)\b(access_token|refresh_token|client_secret|api_key|password|token)(\"?\s*[:=]\s*\"?)[^\s\"',}]+"), r"\1\2[REDACTED]"),
    (re.compile(r"\bya29\.[A-Za-z0-9._-]+"), "[REDACTED]"),          # Google access tokens
    (re.compile(r"\bsk-[A-Za-z0-9_-]{10,}"), "[REDACTED]"),          # API keys
    (re.compile(r"\bgAAAAA[A-Za-z0-9_=-]{20,}"), "[REDACTED]"),       # Fernet ciphertext
]


def redact(text: str) -> str:
    for pat, rep in _PATTERNS:
        text = pat.sub(rep, text)
    return text


def redact_obj(obj):
    if isinstance(obj, dict):
        return {k: ("[REDACTED]" if re.search(r"(?i)token|secret|password|api_key", str(k)) else redact_obj(v))
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_obj(v) for v in obj]
    if isinstance(obj, str):
        return redact(obj)
    return obj


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:  # noqa: BLE001
            msg = str(record.msg)
        record.msg, record.args = redact(msg), None
        return True


def install_log_redaction() -> None:
    root = logging.getLogger()
    for h in root.handlers or [logging.StreamHandler()]:
        h.addFilter(RedactingFilter())
    if not root.handlers:
        h = logging.StreamHandler(); h.addFilter(RedactingFilter()); root.addHandler(h)
