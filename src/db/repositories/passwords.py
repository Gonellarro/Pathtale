"""Password hashing shared by identity and user-administration repositories."""

import hashlib


def hash_password(password: str, salt_hex: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), 100000).hex()
