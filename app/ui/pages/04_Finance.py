# C:\T18\app\ui\pages\04_Finance.py
# -*- coding: utf-8 -*-

from pathlib import Path
import sys
import streamlit as st  # NOTE: first Streamlit call will be inside render_page

# Ensure project root on sys.path
ROOT = Path(r"C:\T18").resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ui.shell.app_shell import render_page   # this sets set_page_config() first
from app.ui.shell.topbar import topbar           # render this inside _body(), not at module import time
from app.ui.webparts.finance_kpis_webpart import render_finance_kpis
from app.ui.webparts.trades_ledger_webpart import render_trades_ledger

def _body():
    # render_page() calls st.set_page_config() BEFORE running this function.
    # It's safe to render UI here.
    topbar("Finance")
    st.caption("Finance (mock data)")
    render_finance_kpis()
    st.subheader("Trades Ledger")
    render_trades_ledger()

if __name__ == "__main__":
    render_page("Finance", _body)
