import streamlit as st
import sqlite3
import pandas as pd
from t18_common.config import paths

def _con():
    return sqlite3.connect(paths()['db'])

def render_signals_table():
    con = _con()
    try:
        df = pd.read_sql_query(
            'select id, ts_utc, symbol, side, entry, sl, tp, state from signals order by id desc limit 20', con)
    finally:
        con.close()
    # New API: width="stretch" instead of use_container_width=True
    st.dataframe(df, width="stretch", hide_index=True)

