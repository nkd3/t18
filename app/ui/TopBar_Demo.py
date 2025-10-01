# C:\T18\app\ui\TopBar_Demo.py
from __future__ import annotations
import streamlit as st
from pathlib import Path
import os

# import the shared component
from app.ui.components.top_bar import render_top_bar

st.set_page_config(page_title="Top Bar Demo • Teevra18", page_icon="🧪", layout="wide")

# ----- Sidebar: route picker -----
st.sidebar.header("Top Bar — Route Preview")
route = st.sidebar.selectbox(
    "Pick a page/subpage to preview",
    [
        "01_Dashboard",
        "02_Market",
        "03_Strategies",
        "04_Finance",
        "05_Settings",
        "Settings_Account_Roles",
    ],
    index=0,
)

# ----- Sidebar: mock controls -----
st.sidebar.header("Mock Controls")
use_mock = st.sidebar.toggle("Use Mock Data", value=True, help="Off = original-ish placeholders")
trading_state = st.sidebar.selectbox("Trading State", ["RUNNING", "PAUSED", "PANIC"], index=0)
market_session = st.sidebar.selectbox("Market Session", ["PREOPEN", "LIVE", "HALTED", "CLOSED", "HOLIDAY"], index=1)
ping_ms = st.sidebar.slider("WS Ping (ms)", 5, 400, 42)
last_tick_s = st.sidebar.slider("Last Tick Age (s)", 0, 30, 1)
token_left_min = st.sidebar.slider("Token Left (min)", 0, 360, 245)
ing = st.sidebar.selectbox("Ingest Health", ["OK", "DEGRADED", "ERROR"], index=0)
dep = st.sidebar.selectbox("Depth Health",  ["OK", "DEGRADED", "ERROR"], index=0)
can = st.sidebar.selectbox("Candles Health",["OK", "DEGRADED", "ERROR"], index=0)
chn = st.sidebar.selectbox("Chain Health",  ["OK", "DEGRADED", "ERROR"], index=0)

mock = dict(
    trading_state=trading_state,
    market_session=market_session,
    ping_ms=ping_ms,
    last_tick_s=float(last_tick_s),
    token_left_min=int(token_left_min),
    ingest_health=ing,
    depth_health=dep,
    candles_health=can,
    chain_health=chn,
)

# ----- Page title + breadcrumb mapping -----
page_map = {
    "01_Dashboard": ("Dashboard", None),
    "02_Market": ("Market", None),
    "03_Strategies": ("Strategies", None),
    "04_Finance": ("Finance", None),
    "05_Settings": ("Settings", None),
    "Settings_Account_Roles": ("Settings", "Account & Roles"),
}
page_title, breadcrumb = page_map.get(route, ("Dashboard", None))

# ----- Render the Top Bar (ALWAYS FIRST) -----
render_top_bar(page_title=page_title, breadcrumb=breadcrumb, use_mock=use_mock, mock=mock)

# ----- Sub-navigation (AFTER Top Bar) -----
# For Settings and its subpages, show settings-level tabs BELOW the top bar.
if route in ("05_Settings", "Settings_Account_Roles"):
    st.markdown("#### Settings")
    tabs = st.tabs(["Account", "Roles", "Permissions", "Audit"])
    with tabs[0]:
        st.info("Account — placeholder content (below Top Bar).")
    with tabs[1]:
        st.warning("Roles — placeholder content (below Top Bar).")
    with tabs[2]:
        st.success("Permissions — placeholder content (below Top Bar).")
    with tabs[3]:
        st.error("Audit — placeholder content (below Top Bar).")

# ----- Page Content (ALWAYS BELOW sub-nav area) -----
st.markdown(f"### {page_title}{' › ' + breadcrumb if breadcrumb else ''} — Content")
st.write("""
This is placeholder content to confirm the stacking order:
**Top Bar → (Sub-nav for subpages) → Page Content**.
""")

# Small visual fillers to test scrolling and stickiness
for i in range(3):
    st.write(f"Lorem content block {i+1}: " + "… " * 50)

st.caption("Tip: Toggle 'Use Mock Data' in the sidebar to switch between fake and original-ish values.")
