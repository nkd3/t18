# -*- coding: utf-8 -*-
# C:\T18\tools\init_users.py

from __future__ import annotations

# ---- Path bootstrap so imports work when running this file directly ----
import sys
from pathlib import Path
FILE = Path(__file__).resolve()
ROOT = FILE.parents[1]  # -> C:\T18
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ---- Normal imports ----
import argparse
from t18_common.db import fetch_one, execute
from t18_common.schema import ensure_schema
from app.auth import hash_password


def upsert_user(username: str, full_name: str, role: str, password: str, avatar_path: str | None = None):
    ensure_schema()
    row = fetch_one("SELECT id FROM users WHERE username_norm = lower(?)", (username,))
    pwd_hash = hash_password(password)
    if row:
        execute(
            """UPDATE users
               SET username = ?, full_name = ?, role = ?, password_hash = ?, avatar_path = ?, is_active = 1, is_deleted = 0
               WHERE id = ?""",
            (username, full_name, role, pwd_hash, avatar_path, row["id"])
        )
        return row["id"], "updated"
    else:
        new_id = execute(
            """INSERT INTO users (username, username_norm, full_name, role, password_hash, avatar_path, is_active, is_deleted)
               VALUES (?, lower(?), ?, ?, ?, ?, 1, 0)""",
            (username, username, full_name, role, pwd_hash, avatar_path)
        )
        return new_id, "created"


def main(argv=None):
    p = argparse.ArgumentParser(description="Init/Manage #t18 users (local SQLite)")
    p.add_argument("--create-admin", action="store_true")
    p.add_argument("--username", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--full-name", required=True)
    p.add_argument("--role", default="admin", choices=["admin","trader","viewer"])
    p.add_argument("--avatar", default=None)
    args = p.parse_args(argv)

    if args.create_admin and args.role != "admin":
        print("Warning: --create-admin used but role != admin; overriding to admin.")
        args.role = "admin"

    ensure_schema()
    user_id, action = upsert_user(args.username, args.full_name, args.role, args.password, args.avatar)
    print(f"User {args.username!r} {action} with id={user_id}")


if __name__ == "__main__":
    raise SystemExit(main())
