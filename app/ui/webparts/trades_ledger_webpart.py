import streamlit as st
import sqlite3, pandas as pd
from t18_common.config import paths

def _con():
    return sqlite3.connect(paths()['db'])

def render_trades_ledger():
    with _con() as con:
        df = pd.read_sql_query(
            'select id, signal_id, ts_utc, fill_price, pnl, state from paper_orders order by id desc limit 50', con)
    # New API: width="stretch" instead of use_container_width=True
    st.dataframe(df, width="stretch", hide_index=True)

