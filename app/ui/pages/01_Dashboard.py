# -*- coding: utf-8 -*-
# C:\T18\app\ui\pages\01_Dashboard.py
from __future__ import annotations
from app.ui.shell.topbar import topbar
topbar("Dashboard")

# --- PATH BOOTSTRAP (must be before any project imports)
import sys
from pathlib import Path
ROOT = Path(r"C:\T18").resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from t18_common.schema import ensure_schema

# Existing app package imports (these live under C:\T18\app\ui\...)
from app.ui.shell.app_shell import render_page  # if you use it elsewhere
from app.ui.webparts.finance_kpis_webpart import render_finance_kpis
from app.ui.webparts.signals_table_webpart import render_signals_table

# --------------------------------------------------------
# Streamlit Config — MUST be first UI call
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
    st.markdown(f"Welcome, **{user.get('full_name', user.get('username', ''))}**  ·  Role: `{user.get('role','')}`")
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
# Quick metrics row (placeholder)
# --------------------------------------------------------
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Today P/L", "₹0", delta="0%")
with c2:
    st.metric("Open Positions", "0")
with c3:
    st.metric("System Status", "🟢 Healthy")

st.divider()

# --------------------------------------------------------
# Webparts
# --------------------------------------------------------
st.caption("Dashboard preview")
render_finance_kpis()

st.subheader("Latest Signals")
render_signals_table()
