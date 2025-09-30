# -*- coding: utf-8 -*-
# C:\T18\scripts\set_password_or_create.py
# Usage:
#   python C:\T18\scripts\set_password_or_create.py <USERNAME> "<NEW_PASSWORD>"
# Optional flags:
#   --create-if-missing    -> create active Trader if not present
#   --role Admin|Trader    -> role to use when creating (default Trader)

import os, sys, sqlite3
from pathlib import Path

# --- PATH BOOTSTRAP so t18_common is importable
ROOT = Path(r"C:\T18").resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from t18_common.security import hash_password

DB_PATH = Path(os.getenv("DB_PATH", r"C:\T18\data\t18.db")).resolve()

def die(msg: str):
    print(msg)
    raise SystemExit(1)

def main():
    if len(sys.argv) < 3:
        die("Usage: set_password_or_create.py <USERNAME> <NEW_PASSWORD> [--create-if-missing] [--role Admin|Trader]")

    args = sys.argv[1:]
    uname = args[0].strip()
    new_pw = args[1]
    create_if_missing = "--create-if-missing" in args
    role = "Trader"
    if "--role" in args:
        try:
            role = args[args.index("--role")+1]
        except Exception:
            die("Missing value after --role")
    if role not in ("Admin","Trader"):
        die("Role must be 'Admin' or 'Trader'")

    if not DB_PATH.exists():
        die(f"DB not found at {DB_PATH}. Set DB_PATH or create DB.")

    uname_norm = uname.lower()

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Ensure username_norm column exists (safety)
        cols = [r[1] for r in cur.execute("PRAGMA table_info(users)").fetchall()]
        if "username_norm" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN username_norm TEXT;")
            cur.execute("UPDATE users SET username_norm = lower(username) WHERE username IS NOT NULL;")
            conn.commit()

        # Try to find user case-insensitively
        row = cur.execute("""
            SELECT user_id, username, username_norm, role, active, deleted_ts
            FROM users
            WHERE (username_norm = ? OR lower(username) = ?)
            LIMIT 1
        """, (uname_norm, uname_norm)).fetchone()

        if not row:
            if not create_if_missing:
                die(f"User not found: {uname}  (Tip: run with --create-if-missing to create)")
            # Create fresh user
            cur.execute("""
                INSERT INTO users
                    (username, username_norm, display_name, role, password_hash,
                     active, mfa_enabled, profile_pic, force_reset, last_login_ts,
                     created_ts, deleted_ts)
                VALUES (?, ?, ?, ?, ?, 1, 0, NULL, 0, NULL, strftime('%s','now'), NULL)
            """, (uname, uname_norm, uname, role, hash_password(new_pw)))
            conn.commit()
            print(f"Created user '{uname}' as {role} with new password.")
            return

        # Undelete & activate if needed
        uid = row["user_id"]
        changed = False
        if row["deleted_ts"] is not None:
            cur.execute("UPDATE users SET deleted_ts=NULL WHERE user_id=?", (uid,))
            changed = True
        if not row["active"]:
            cur.execute("UPDATE users SET active=1 WHERE user_id=?", (uid,))
            changed = True
        if changed:
            conn.commit()

        # Set password
        cur.execute("UPDATE users SET password_hash=?, force_reset=0 WHERE user_id=?",
                    (hash_password(new_pw), uid))
        conn.commit()
        print(f"Password set for '{row['username']}' (user_id={uid}). User is active and not deleted.")

if __name__ == "__main__":
    main()
