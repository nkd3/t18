# -*- coding: utf-8 -*-
# C:\T18\scripts\auth_doctor.py
# Usage: python C:\T18\scripts\auth_doctor.py <USERNAME> "<PASSWORD>"
import os, sys, sqlite3
from pathlib import Path

# PATH bootstrap
ROOT = Path(r"C:\T18").resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from t18_common.security import verify_password

DB_PATH = Path(os.getenv("DB_PATH", r"C:\T18\data\t18.db")).resolve()

def main():
    if len(sys.argv) < 3:
        print("Usage: auth_doctor.py <USERNAME> <PASSWORD>")
        return
    uname = sys.argv[1].strip()
    pw = sys.argv[2]
    uname_norm = uname.lower()

    print(f"[auth_doctor] DB_PATH = {DB_PATH}")
    if not DB_PATH.exists():
        print("DB file not found.")
        return

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("""
            SELECT user_id, username, username_norm, role, active, deleted_ts,
                   CASE WHEN password_hash IS NULL THEN NULL ELSE length(password_hash) END AS hash_len,
                   password_hash
            FROM users
            WHERE (username_norm = ? OR lower(username) = ?)
            LIMIT 1
        """, (uname_norm, uname_norm)).fetchone()

        if not row:
            print("RESULT = NOT_FOUND")
            return

        print(dict(row) | {"password_hash": "***redacted***"})
        if row["deleted_ts"] is not None:
            print("RESULT = FAIL (soft-deleted)")
            return
        if not row["active"]:
            print("RESULT = FAIL (inactive)")
            return
        ph = row["password_hash"]
        if ph is None:
            print("RESULT = BOOTSTRAP (no hash yet) -> set a password")
            return

        ok = verify_password(pw, ph)
        print(f"RESULT = {'OK' if ok else 'BAD_PASSWORD'}")

if __name__ == "__main__":
    main()
