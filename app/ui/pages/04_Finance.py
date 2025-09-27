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
