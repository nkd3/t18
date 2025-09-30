# -*- coding: utf-8 -*-
# C:\T18\scripts\migrate_20250930_add_username_norm.py
# Purpose: add users.username_norm (lowercased username), backfill, and index it.

import sqlite3
from pathlib import Path

DB_PATH = Path(r"C:\T18\data\t18.db")  # adjust if your DB path differs

def column_exists(conn: sqlite3.Connection, table: str, col: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return any(row[1] == col for row in cur.fetchall())

def index_exists(conn: sqlite3.Connection, index_name: str) -> bool:
    cur = conn.execute("PRAGMA index_list(users)")
    return any(row[1] == index_name for row in cur.fetchall())

def main():
    if not DB_PATH.exists():
        raise SystemExit(f"DB not found: {DB_PATH}")

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")

        # 1) Add column if missing
        if not column_exists(conn, "users", "username_norm"):
            conn.execute("ALTER TABLE users ADD COLUMN username_norm TEXT;")

        # 2) Backfill (lowercase of username) where null/empty
        conn.execute("""
            UPDATE users
               SET username_norm = lower(username)
             WHERE username_norm IS NULL
                OR username_norm = '';
        """)

        # 3) Add helpful index (unique if your business logic requires uniqueness)
        # Use UNIQUE if you want to prevent case-insensitive duplicates:
        #   CREATE UNIQUE INDEX IF NOT EXISTS ux_users_username_norm ...
        # If you already have a unique index on username, keep this NON-UNIQUE:
        if not index_exists(conn, "ix_users_username_norm"):
            conn.execute("CREATE INDEX IF NOT EXISTS ix_users_username_norm ON users(username_norm);")

        conn.commit()

    print("Migration complete: users.username_norm added/backfilled/indexed.")

if __name__ == "__main__":
    main()
