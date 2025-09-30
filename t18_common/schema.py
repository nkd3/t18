# -*- coding: utf-8 -*-
# C:\T18\t18_common\schema.py
from __future__ import annotations
import sqlite3
from pathlib import Path
from t18_common.db import exec_script, get_conn

# --- Base schema ---
SCHEMA_SQL = r"""
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  username      TEXT NOT NULL UNIQUE,
  username_norm TEXT,
  full_name     TEXT NOT NULL,
  role          TEXT NOT NULL CHECK (role IN ('admin','trader','viewer')),
  password_hash TEXT,
  avatar_path   TEXT,
  is_active     INTEGER NOT NULL DEFAULT 1,
  is_deleted    INTEGER NOT NULL DEFAULT 0,
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  deleted_at    TEXT
);

CREATE INDEX IF NOT EXISTS idx_users_username_norm ON users(username_norm);
"""

def _migrate_users_username_norm() -> None:
    """Ensure username_norm column exists, backfill, and index it."""
    with get_conn() as conn:
        cur = conn.execute("PRAGMA table_info(users)")
        cols = [r[1] for r in cur.fetchall()]
        if "username_norm" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN username_norm TEXT;")
            conn.execute("UPDATE users SET username_norm = lower(username) WHERE username IS NOT NULL;")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username_norm ON users(username_norm);")
            conn.commit()
        else:
            # Backfill any missing values
            conn.execute("UPDATE users SET username_norm = lower(username) WHERE username_norm IS NULL OR username_norm = '';")
            conn.commit()

def ensure_schema() -> None:
    """Bootstrap schema and run migrations."""
    exec_script(SCHEMA_SQL)
    _migrate_users_username_norm()
