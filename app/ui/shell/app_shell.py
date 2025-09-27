import streamlit as st
from app.ui.webparts.topbar_webpart import render_topbar

def render_page(title:str, body_renderer):
    st.set_page_config(page_title=f"Teevra18 | {title}", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")
    render_topbar()
    st.markdown(f"## {title}")
    body_renderer()
