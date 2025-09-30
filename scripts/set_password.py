# -*- coding: utf-8 -*-
# C:\T18\scripts\set_password.py
# Usage: python C:\T18\scripts\set_password.py <USERNAME> <NEW_PASSWORD>
import sys, sqlite3
from pathlib import Path

ROOT = Path(r"C:\T18").resolve()
DB_PATH = ROOT / "data" / "t18.db"

# PATH bootstrap for t18_common
import sys as _sys
if str(ROOT) not in _sys.path:
    _sys.path.insert(0, str(ROOT))
from t18_common.security import hash_password

def main():
    if len(sys.argv) < 3:
        print("Usage: set_password.py <USERNAME> <NEW_PASSWORD>")
        return
    uname, new_pw = sys.argv[1].strip(), sys.argv[2]
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT user_id, active, deleted_ts FROM users WHERE (username=? OR lower(username)=lower(?)) LIMIT 1",
            (uname, uname)
        ).fetchone()
        if not row:
            print(f"User not found: {uname}")
            return
        if row["deleted_ts"] is not None:
            print("User is deleted (soft). Undelete first.")
            return
        if not row["active"]:
            print("User is inactive. Activating...")
            conn.execute("UPDATE users SET active=1 WHERE user_id=?", (row["user_id"],))
        conn.execute(
            "UPDATE users SET password_hash=?, force_reset=0 WHERE user_id=?",
            (hash_password(new_pw), row["user_id"])
        )
        conn.commit()
        print(f"Password set for '{uname}'. Try login now.")

if __name__ == "__main__":
    main()
