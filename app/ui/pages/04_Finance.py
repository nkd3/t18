# Top of file (before 'import t18_common')
import sys
from pathlib import Path

ROOT = Path(r"C:\T18").resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from app.ui.shell.app_shell import render_page
from app.ui.webparts.finance_kpis_webpart import render_finance_kpis
from app.ui.webparts.trades_ledger_webpart import render_trades_ledger

def _body():
    st.caption('Finance (mock data)')
    render_finance_kpis()
    st.subheader('Trades Ledger')
    render_trades_ledger()

if __name__ == '__main__':
    render_page('Finance', _body)
