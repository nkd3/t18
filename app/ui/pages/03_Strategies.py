import streamlit as st
from app.ui.shell.app_shell import render_page

def _body():
    st.write('Strategies + RR Profiles placeholders.')

if __name__ == '__main__':
    render_page('Strategies', _body)
