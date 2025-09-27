import streamlit as st
from app.ui.shell.app_shell import render_page

def _body():
    st.write('Market data placeholders (Tape, Depth20, Candles).')

if __name__ == '__main__':
    render_page('Market', _body)
