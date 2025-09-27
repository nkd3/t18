# -*- coding: utf-8 -*-
# C:\T18\app\ui\pages\01_Dashboard.py
from __future__ import annotations
import streamlit as st
from t18_common.schema import ensure_schema

# Old mock webparts
from app.ui.shell.app_shell import render_page
from app.ui.webparts.finance_kpis_webpart import render_finance_kpis
from app.ui.webparts.signals_table_webpart import render_signals_table

# --------------------------------------------------------
# Streamlit Config — MUST be first
# --------------------------------------------------------
st.set_page_config(page_title="Teevra18 | Dashboard", page_icon="📊", layout="wide")

# Ensure schema (safe no-op if it already exists)
ensure_schema()

# --------------------------------------------------------
# Auth Guard — must be logged in
# --------------------------------------------------------
user = st.session_state.get("user")
if not user:
    st.warning("You’re not logged in. Redirecting to login…")
    try:
        st.switch_page("Home_Landing.py")
    except Exception:
        st.info("If you’re not redirected automatically, click below to go to Login.")
        st.page_link("Home_Landing.py", label="Go to Login", icon="🔒")
    st.stop()

# --------------------------------------------------------
# Top bar
# --------------------------------------------------------
left, mid, right = st.columns([2, 6, 2])
with left:
    st.markdown("### 📊 Dashboard")
with mid:
    st.markdown(f"Welcome, **{user['full_name']}**  ·  Role: `{user['role']}`")
with right:
    if st.button("Logout", use_container_width=True):
        st.session_state.clear()
        try:
            st.switch_page("Home_Landing.py")
        except Exception:
            st.info("Logged out. If you’re not redirected, click below to go to Login.")
            st.page_link("Home_Landing.py", label="Go to Login", icon="🔒")
        st.stop()

st.divider()

# --------------------------------------------------------
# Demo content — combine mock + metrics
# --------------------------------------------------------
# Quick metrics row
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Today P/L", "₹0", delta="0%")
with c2:
    st.metric("Open Positions", "0")
with c3:
    st.metric("System Status", "🟢 Healthy")

st.divider()

# Mock data preview (original webparts)
st.caption("Dashboard preview (mock data)")
render_finance_kpis()
st.subheader("Latest Signals")
render_signals_table()
