# C:\T18\app\ui\webparts\finance_kpis_webpart.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
import os, sqlite3, time, math
import pandas as pd
import streamlit as st

# -------------------------------------------------------------------
# DB location (ENV override supported)
DB_PATH = os.getenv("DB_PATH", r"C:\T18\data\t18.db")

# Schema used here is intentionally minimal & stable for KPIs:
#   d TEXT PRIMARY KEY (YYYY-MM-DD)
#   net_pnl REAL
#   gross_pnl REAL
#   fees REAL
#   trades INTEGER
#   win_rate REAL      (0..1)
#   sharpe REAL
#   max_dd REAL
#   exposure REAL      (0..1)
# Add more columns freely later; KPIs below only read these.
# -------------------------------------------------------------------

def _connect() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    return con

def _ensure_schema(con: sqlite3.Connection) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS kpi_daily (
            d TEXT PRIMARY KEY,
            net_pnl   REAL,
            gross_pnl REAL,
            fees      REAL,
            trades    INTEGER,
            win_rate  REAL,
            sharpe    REAL,
            max_dd    REAL,
            exposure  REAL
        )
    """)
    con.commit()

def _seed_if_empty(con: sqlite3.Connection) -> None:
    cur = con.cursor()
    row = cur.execute("SELECT COUNT(1) FROM kpi_daily").fetchone()
    if row and int(row[0]) == 0:
        # Insert a mock row for "today" so UI has something to render
        today = pd.Timestamp.utcnow().tz_localize("UTC").tz_convert("Europe/London").date().isoformat()
        cur.execute("""
            INSERT INTO kpi_daily (d, net_pnl, gross_pnl, fees, trades, win_rate, sharpe, max_dd, exposure)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (today, 12500.0, 13800.0, 1300.0, 42, 0.58, 1.42, -3500.0, 0.37))
        # Also insert a "yesterday" row for deltas
        yday = (pd.Timestamp(today) - pd.Timedelta(days=1)).date().isoformat()
        cur.execute("""
            INSERT INTO kpi_daily (d, net_pnl, gross_pnl, fees, trades, win_rate, sharpe, max_dd, exposure)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (yday, 9800.0, 10600.0, 800.0, 39, 0.54, 1.20, -4100.0, 0.33))
        con.commit()

def _load_latest(con: sqlite3.Connection) -> tuple[pd.Series | None, pd.Series | None]:
    df = pd.read_sql_query("SELECT * FROM kpi_daily ORDER BY d DESC LIMIT 2", con)
    if df.empty:
        return None, None
    latest = df.iloc[0]
    prev = df.iloc[1] if len(df) > 1 else None
    return latest, prev

def _fmt_pct(x: float | None) -> str:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return "—"
    return f"{x*100:.1f}%"

def _delta_str(curr: float | None, prev: float | None, as_pct: bool = False) -> str:
    if curr is None or prev is None:
        return "—"
    d = curr - prev
    if as_pct:
        return f"{(d*100):+.1f} pp"
    return f"{d:+,.0f}"

def render_finance_kpis() -> None:
    """Safe KPI header for Finance page. Auto-creates `kpi_daily` if missing."""
    try:
        with _connect() as con:
            _ensure_schema(con)
            _seed_if_empty(con)
            latest, prev = _load_latest(con)
    except Exception as e:
        st.error(f"Finance KPIs unavailable: {e}")
        return

    if latest is None:
        st.warning("No KPI data available yet.")
        return

    # Extract values with safe fallbacks
    d_str      = str(latest.get("d", "—"))
    net_pnl    = latest.get("net_pnl", None)
    gross_pnl  = latest.get("gross_pnl", None)
    fees       = latest.get("fees", None)
    trades     = latest.get("trades", None)
    win_rate   = latest.get("win_rate", None)
    sharpe     = latest.get("sharpe", None)
    max_dd     = latest.get("max_dd", None)
    exposure   = latest.get("exposure", None)

    prev_net   = prev.get("net_pnl", None)   if isinstance(prev, pd.Series) else None
    prev_wr    = prev.get("win_rate", None)  if isinstance(prev, pd.Series) else None
    prev_shar  = prev.get("sharpe", None)    if isinstance(prev, pd.Series) else None
    prev_dd    = prev.get("max_dd", None)    if isinstance(prev, pd.Series) else None
    prev_trd   = prev.get("trades", None)    if isinstance(prev, pd.Series) else None

    st.caption(f"KPIs for **{d_str}**  •  DB: `{DB_PATH}`")

    c1, c2, c3, c4, c5, c6 = st.columns([1.5, 1.2, 1.2, 1.2, 1.2, 1.2])
    with c1:
        st.metric("Net P&L", f"{(net_pnl or 0):,.0f}", _delta_str(net_pnl, prev_net))
    with c2:
        st.metric("Win Rate", _fmt_pct(win_rate), _delta_str(win_rate, prev_wr, as_pct=True))
    with c3:
        st.metric("Sharpe", f"{(sharpe or 0):.2f}", _delta_str(sharpe, prev_shar))
    with c4:
        st.metric("Max Drawdown", f"{(max_dd or 0):,.0f}", _delta_str(max_dd, prev_dd))
    with c5:
        st.metric("Trades", f"{int(trades or 0):,}", _delta_str(float(trades or 0), float(prev_trd or 0)))
    with c6:
        st.metric("Fees", f"{(fees or 0):,.0f}")

    # Optional: small secondary row
    st.progress(min(max(int((exposure or 0)*100), 0), 100), text=f"Exposure: {_fmt_pct(exposure)}")
