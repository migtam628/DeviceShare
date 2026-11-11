"""Local-first owner authentication and one-time activation/recovery codes.

The administrator's email is only a login identifier. No email delivery,
third-party identity provider or external cloud dependency is required.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets

SALT_BYTES = 16
# ~32 MiB memory; 64 MiB bound for OpenSSL implementations.
SCRYPT_N = 1 << 15
SCRYPT_R = 8
SCRYPT_P = 1
MEMORY_LIMIT = 64 * 1024 * 1024


def normalize_email(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Enter a valid email address")
    email = value.strip().lower()
    if len(email) > 254 or not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_\x60{|}~-]{1,64}@[a-z0-9-]+(?:\.[a-z0-9-]+)+", email):
        raise ValueError("Enter a valid email address")
    return email


def validate_password(password: str) -> None:
    if not isinstance(password, str) or not 12 <= len(password) <= 128:
        raise ValueError("Use a password between 12 and 128 characters")
    if not password.strip() or any(ord(char) < 32 for char in password):
        raise ValueError("Password cannot contain control characters")


def password_digest(password: str, salt_hex: str) -> str:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=bytes.fromhex(salt_hex),
        n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, maxmem=MEMORY_LIMIT, dklen=32
    ).hex()


def new_password_record(password: str) -> tuple[str, str]:
    validate_password(password)
    salt = secrets.token_hex(SALT_BYTES)
    return salt, password_digest(password, salt)


def check_password(password: str, salt: str, digest: str) -> bool:
    if not isinstance(password, str) or len(password) > 128:
        return False
    return hmac.compare_digest(password_digest(password, salt), digest)
