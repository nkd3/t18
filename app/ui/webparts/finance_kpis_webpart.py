import streamlit as st
import sqlite3, pandas as pd
from app.t18_common.config import paths

def _con():
    return sqlite3.connect(paths()['db'])

def render_finance_kpis():
    with _con() as con:
        kpi = pd.read_sql_query('select * from kpi_daily order by d desc limit 1', con)
        pl = pd.read_sql_query('select d, realized_pl from kpi_daily order by d', con)

    c1,c2,c3,c4 = st.columns(4)
    if not kpi.empty:
        row = kpi.iloc[0]
        c1.metric("Today P/L", f"₹{int(row.realized_pl)}")
        c2.metric("Trades", int(row.trades))
        c3.metric("Win %", f"{row.win_pct:.0f}%")
        c4.metric("Max DD", f"₹{int(row.max_dd)}")
    else:
        c1.metric("Today P/L","₹0"); c2.metric("Trades","0"); c3.metric("Win %","0%"); c4.metric("Max DD","₹0")

    # Streamlit line_chart doesn't use use_container_width; no change needed
    st.line_chart(pl.set_index('d'))
