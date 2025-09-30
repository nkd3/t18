# -*- coding: utf-8 -*-
# C:\T18\app\ui\webparts\finance_kpis_webpart.py

# --- PATH BOOTSTRAP (must be before project imports)
import sys
from pathlib import Path
ROOT = Path(r"C:\T18").resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import sqlite3
import pandas as pd
import streamlit as st

# ✅ Use the canonical module (no app.t18_common)
from t18_common.config import paths


def _db_path() -> str:
    """
    Resolve DB path from t18_common.config.paths.
    Supports both dict-like (paths()['db']) and attr-like (paths.db).
    Falls back to C:\T18\data\t18.db if not available.
    """
    try:
        # callable that returns a dict
        p = paths()
        if isinstance(p, dict) and "db" in p:
            return str(p["db"])
    except TypeError:
        # not callable, maybe a module/object with attribute
        pass
    try:
        return str(getattr(paths, "db"))
    except Exception:
        return str(ROOT / "data" / "t18.db")


def _con():
    return sqlite3.connect(_db_path())


def render_finance_kpis():
    with _con() as con:
        kpi = pd.read_sql_query(
            "SELECT * FROM kpi_daily ORDER BY d DESC LIMIT 1",
            con
        )
        pl = pd.read_sql_query(
            "SELECT d, realized_pl FROM kpi_daily ORDER BY d",
            con
        )

    c1, c2, c3, c4 = st.columns(4)
    if not kpi.empty:
        row = kpi.iloc[0]
        c1.metric("Today P/L", f"₹{int(row['realized_pl'])}")
        c2.metric("Trades", int(row.get("trades", 0)))
        c3.metric("Win %", f"{float(row.get('win_pct', 0.0)):.0f}%")
        c4.metric("Max DD", f"₹{int(row.get('max_dd', 0))}")
    else:
        c1.metric("Today P/L", "₹0")
        c2.metric("Trades", "0")
        c3.metric("Win %", "0%")
        c4.metric("Max DD", "₹0")

    if not pl.empty:
        # Ensure 'd' is datetime index for a nicer chart (optional)
        try:
            pl = pl.copy()
            pl["d"] = pd.to_datetime(pl["d"])
            pl = pl.set_index("d")
        except Exception:
            pl = pl.set_index("d")
        st.line_chart(pl)
    else:
        st.caption("No KPI data found yet.")
