# -*- coding: utf-8 -*-
# C:\T18\app\auth.py
import sqlite3
from pathlib import Path
from typing import Optional

from t18_common.security import verify_password, hash_password

DB_PATH = Path(r"C:\T18\data\t18.db")

class UserObj:
    def __init__(self, row: sqlite3.Row):
        # row contains alias: user_id AS id
        self.id          = row["id"]
        self.username    = row["username"]
        self.full_name   = row["display_name"] or row["username"]
        self.role        = row["role"]
        # optional/legacy-safe
        self.avatar_path = row["avatar_path"] if "avatar_path" in row.keys() else None

def _row_to_user(row: sqlite3.Row) -> UserObj:
    return UserObj(row)

def verify_credentials(username: str, password: str) -> Optional[UserObj]:
    """
    Case-insensitive username check using username_norm.
    If a user exists with NULL password_hash (bootstrap), set the provided password as hash and force_reset=1.
    Returns a UserObj on success, else None.
    """
    uname = (username or "").strip()
    if not uname or not password:
        return None
    uname_norm = uname.lower()

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        # Prefer username_norm for case-insensitive lookup; fallback to exact username
        row = conn.execute(
            """
            SELECT
                user_id AS id,
                username,
                COALESCE(display_name, username) AS display_name,
                role,
                password_hash,
                active,
                deleted_ts,
                force_reset
                -- avatar_path may not exist in older schemas; don't select it to avoid errors
            FROM users
            WHERE (username_norm = ? OR username = ?)
              AND active = 1
              AND deleted_ts IS NULL
            LIMIT 1
            """,
            (uname_norm, uname),
        ).fetchone()

        if not row:
            return None

        ph = row["password_hash"]

        # Bootstrap path: first-time users with NULL password_hash
        if ph is None:
            new_hash = hash_password(password)
            conn.execute(
                "UPDATE users SET password_hash=?, force_reset=1, last_login_ts=strftime('%s','now') WHERE user_id=?",
                (new_hash, row["id"]),
            )
            conn.commit()
            # re-select with new hash to build UserObj cleanly
            row = conn.execute(
                """
                SELECT
                    user_id AS id,
                    username,
                    COALESCE(display_name, username) AS display_name,
                    role,
                    password_hash
                FROM users WHERE user_id=? LIMIT 1
                """,
                (row["id"],),
            ).fetchone()
            return _row_to_user(row)

        # Normal path: verify password
        if not verify_password(password, ph):
            return None

        # Success -> update last login
        conn.execute("UPDATE users SET last_login_ts=strftime('%s','now') WHERE user_id=?", (row["id"],))
        conn.commit()

        return _row_to_user(row)
