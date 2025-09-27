import streamlit as st
from app.ui.shell.app_shell import render_page

def _body():
    st.write('Settings: Profile, Admin Config, Logs & Health.')

if __name__ == '__main__':
    render_page('Settings', _body)
