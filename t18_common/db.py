# -*- coding: utf-8 -*-
# C:\T18\t18_common\db.py
from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Optional, Any, Iterable, Tuple

DB_PATH = Path(r"C:\T18\data\t18.db")

def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    return con

def exec_script(sql: str) -> None:
    with get_conn() as con:
        con.executescript(sql)

def fetch_one(sql: str, params: Iterable[Any] = ()) -> Optional[sqlite3.Row]:
    with get_conn() as con:
        cur = con.execute(sql, params)
        return cur.fetchone()

def fetch_all(sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    with get_conn() as con:
        cur = con.execute(sql, params)
        return cur.fetchall()

def execute(sql: str, params: Iterable[Any] = ()) -> int:
    with get_conn() as con:
        cur = con.execute(sql, params)
        return cur.lastrowid
