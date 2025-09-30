# -*- coding: utf-8 -*-
# C:\T18\scripts\seed_neel_admin.py
# Creates/updates an active Admin user: username=neel, password=neel

from pathlib import Path
import sqlite3
from t18_common.security import hash_password

DB_PATH = Path(r"C:\T18\data\t18.db")

def main():
    if not DB_PATH.exists():
        raise SystemExit(f"DB not found: {DB_PATH}")

    uname = "neel"
    uname_norm = uname.lower()
    display = "Neel"
    role = "admin"
    pw_hash = hash_password("neel")

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Ensure username_norm column exists (safety)
        cols = [r[1] for r in cur.execute("PRAGMA table_info(users)").fetchall()]
        if "username_norm" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN username_norm TEXT;")

        # Upsert user
        row = cur.execute("""
            SELECT user_id FROM users
            WHERE (username = ? OR username_norm = ?) AND deleted_ts IS NULL
            LIMIT 1
        """, (uname, uname_norm)).fetchone()

        if row:
            uid = row["user_id"]
            cur.execute("""
                UPDATE users
                   SET username = ?,
                       username_norm = ?,
                       display_name = ?,
                       role = ?,
                       password_hash = ?,
                       active = 1,
                       mfa_enabled = COALESCE(mfa_enabled, 0),
                       force_reset = COALESCE(force_reset, 0)
                 WHERE user_id = ?
            """, (uname, uname_norm, display, role, pw_hash, uid))
            print(f"Updated existing user #{uid} -> neel (admin, active).")
        else:
            cur.execute("""
                INSERT INTO users
                    (username, username_norm, display_name, role,
                     password_hash, active, mfa_enabled, profile_pic,
                     force_reset, last_login_ts, created_ts, deleted_ts)
                VALUES (?, ?, ?, ?, ?, 1, 0, NULL, 0, NULL, strftime('%s','now'), NULL)
            """, (uname, uname_norm, display, role, pw_hash))
            print("Inserted new user -> neel (admin, active).")

        # Helpful index (idempotent)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_users_username_norm ON users(username_norm);")

        conn.commit()

if __name__ == "__main__":
    main()
