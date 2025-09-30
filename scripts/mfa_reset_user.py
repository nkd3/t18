# -*- coding: utf-8 -*-
# C:\T18\scripts\mfa_reset_user.py
# Usage: python C:\T18\scripts\mfa_reset_user.py <USERNAME>
import sys, sqlite3
from pathlib import Path

ROOT = Path(r"C:\T18").resolve()
DB_PATH = ROOT / "data" / "t18.db"

def main():
    if len(sys.argv) < 2:
        print("Usage: mfa_reset_user.py <USERNAME>")
        return
    uname = sys.argv[1].strip()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        row = cur.execute("SELECT user_id, username FROM users WHERE (username=? OR lower(username)=lower(?)) AND deleted_ts IS NULL", (uname, uname)).fetchone()
        if not row:
            print(f"User not found: {uname}")
            return
        uid = row["user_id"]
        # remove secret & disable
        cur.execute("DELETE FROM mfa_secrets WHERE user_id=?", (uid,))
        cur.execute("UPDATE users SET mfa_enabled=0 WHERE user_id=?", (uid,))
        conn.commit()
        print(f"MFA reset for user '{row['username']}'. They can re-enroll TOTP now.")

if __name__ == "__main__":
    main()
