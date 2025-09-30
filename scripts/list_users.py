# -*- coding: utf-8 -*-
# C:\T18\scripts\list_users.py
import os, sqlite3
from pathlib import Path

DB_PATH = Path(os.getenv("DB_PATH", r"C:\T18\data\t18.db")).resolve()

with sqlite3.connect(DB_PATH) as conn:
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT user_id, username, username_norm, role, active, deleted_ts,
               CASE WHEN password_hash IS NULL THEN 0 ELSE 1 END AS has_hash
        FROM users
        ORDER BY username ASC
    """).fetchall()
    for r in rows:
        print(dict(r))
