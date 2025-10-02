# C:\T18\app\ui\shell\base_page.py
# Two shell helpers:
# - use_login_shell(): for the login page (no avatar)
# - use_topbar(): for all post-login pages (shows avatar)

from __future__ import annotations
import streamlit as st
from app.ui.shell.avatar_menu import render_avatar_menu

APP_TITLE_DEFAULT = "Teevra18"

def _page_config(title: str) -> None:
    st.set_page_config(page_title=title, layout="wide", initial_sidebar_state="collapsed")

def use_login_shell(title: str = APP_TITLE_DEFAULT) -> None:
    _page_config(title)
    left, _ = st.columns([10, 2])
    with left:
        st.markdown(f"### {title}")
    st.markdown("<hr style='margin-top:0.4rem;margin-bottom:0.8rem;'>", unsafe_allow_html=True)

def use_topbar(title: str = APP_TITLE_DEFAULT) -> None:
    _page_config(title)
    left, right = st.columns([8, 2])
    with left:
        st.markdown(f"### {title}")
    with right:
        render_avatar_menu()
    st.markdown("<hr style='margin-top:0.4rem;margin-bottom:0.8rem;'>", unsafe_allow_html=True)
