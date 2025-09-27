# -*- coding: utf-8 -*-
# C:\T18\app\auth.py
from __future__ import annotations
import os, secrets, hashlib, hmac
from dataclasses import dataclass
from typing import Optional
from t18_common.db import fetch_one

# PBKDF2-HMAC (SHA256) parameters
_ITERATIONS = 200_000
_SALT_BYTES = 16
_HASH_BYTES = 32

@dataclass
class User:
    id: int
    username: str
    full_name: str
    role: str
    avatar_path: Optional[str]
    is_active: bool

def _pbkdf2_hash(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS, dklen=_HASH_BYTES)

def hash_password(password: str) -> str:
    salt = os.urandom(_SALT_BYTES)
    dk = _pbkdf2_hash(password, salt)
    # store as hex: iterations$salthex$hashhex
    return f"{_ITERATIONS}${salt.hex()}${dk.hex()}"

def verify_password(password: str, stored: str) -> bool:
    try:
        it_s, salt_hex, hash_hex = stored.split("$")
        iterations = int(it_s)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, dklen=len(expected))
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False

def verify_credentials(username: str, password: str) -> Optional[User]:
    row = fetch_one(
        """
        SELECT id, username, full_name, role, avatar_path, is_active, password_hash
        FROM users
        WHERE username_norm = lower(?) AND is_deleted = 0
        """,
        (username.strip(),)
    )
    if not row:
        return None
    if row["is_active"] != 1:
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    return User(
        id=row["id"],
        username=row["username"],
        full_name=row["full_name"],
        role=row["role"],
        avatar_path=row["avatar_path"],
        is_active=bool(row["is_active"])
    )
