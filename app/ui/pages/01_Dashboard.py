# -*- coding: utf-8 -*-
# C:\T18\app\ui\pages\01_Dashboard.py

from __future__ import annotations

# --- PATH BOOTSTRAP (must be before any project imports)
import sys
from pathlib import Path
ROOT = Path(r"C:\T18").resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Core imports
import streamlit as st

# --------------------------------------------------------
# Streamlit Config — MUST be the first Streamlit command
# --------------------------------------------------------
st.set_page_config(page_title="Teevra18 | Dashboard", page_icon="📊", layout="wide")

# Now safely import anything that uses st.*
from t18_common.schema import ensure_schema
from app.ui.shell.topbar import topbar
from app.ui.webparts.finance_kpis_webpart import render_finance_kpis
from app.ui.webparts.signals_table_webpart import render_signals_table

# Ensure schema (safe no-op if it already exists)
ensure_schema()

# --------------------------------------------------------
# Auth Guard — must be logged in
# Uses st.session_state["user"] (adapt if your key differs)
# --------------------------------------------------------
user = st.session_state.get("user")
if not user:
    st.warning("You’re not logged in. Redirecting to login…")
    try:
        st.switch_page("Home_Landing.py")
    except Exception:
        st.page_link("Home_Landing.py", label="Go to Login", icon="🔒")
    st.stop()

# --------------------------------------------------------
# Slim Top bar (no big title, no welcome text)
# Avatar menu contains: My Profile, Sign out (Logout)
# --------------------------------------------------------
topbar("Dashboard")  # the title is not printed loudly; bar stays slim

# --------------------------------------------------------
# Content (keep it minimal for now)
# --------------------------------------------------------
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Today P/L", "₹0", delta="0%")
with c2:
    st.metric("Open Positions", "0")
with c3:
    st.metric("System Status", "🟢 Healthy")

st.divider()

st.caption("Dashboard preview")
render_finance_kpis()

st.subheader("Latest Signals")
render_signals_table()
