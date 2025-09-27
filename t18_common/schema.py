# -*- coding: utf-8 -*-
from __future__ import annotations
from t18_common.db import exec_script

SCHEMA_SQL = r"""
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  username      TEXT NOT NULL UNIQUE,
  username_norm TEXT NOT NULL UNIQUE,
  full_name     TEXT NOT NULL,
  role          TEXT NOT NULL CHECK (role IN ('admin','trader','viewer')),
  password_hash TEXT NOT NULL,
  avatar_path   TEXT,
  is_active     INTEGER NOT NULL DEFAULT 1,
  is_deleted    INTEGER NOT NULL DEFAULT 0,
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  deleted_at    TEXT
);

CREATE INDEX IF NOT EXISTS idx_users_username_norm ON users(username_norm);
"""

def ensure_schema() -> None:
    exec_script(SCHEMA_SQL)
