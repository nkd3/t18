# -*- coding: utf-8 -*-
from pathlib import Path
import sys
import streamlit as st

# Bootstrap root for imports
ROOT = Path(r"C:\T18").resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ---- Consistent Top Bar (minimal example) ----
st.set_page_config(page_title="Settings • Teevra18", page_icon="⚙️", layout="wide")

def render_topbar():
    cols = st.columns([4,2,2,2])
    with cols[0]:
        st.markdown("### ⚙️ Settings")
        st.caption("Configure everything from GUI • #t18set")
    with cols[1]:
        st.metric("Mode", st.session_state.get("mode", "Paper"))
    with cols[2]:
        st.metric("Breaker", st.session_state.get("breaker", "RUNNING"))
    with cols[3]:
        st.markdown("[#t18repo](https://github.com/nkd3/t18) · #t18sync")

render_topbar()
st.divider()

# ---- Cards Grid ----
# Helper: button that navigates to another page
def nav_button(label: str, target_page_path: str, key: str):
    # target_page_path is relative to app/ui/pages/ e.g. "Settings_Account_Roles.py"
    if st.button(label, key=key, use_container_width=True):
        # Streamlit 1.25+ supports switch_page with absolute-like path
        st.switch_page(f"pages/{target_page_path}")

# Layout the cards
c1, c2, c3 = st.columns(3)

with c1:
    st.subheader("Account & Roles")
    st.caption("Full UAM: users, roles, MFA, sessions, policies, audit")
    nav_button("Open Account & Roles →", "Settings_Account_Roles.py", key="open_uam")

with c2:
    st.subheader("Integrations")
    st.caption("DhanHQ, Telegram, GitHub, Notion • tokens, tests, bundles")
    nav_button("Open Integrations →", "Settings_Integrations.py", key="open_integrations")

with c3:
    st.subheader("Execution & Breaker")
    st.caption("Backtest / Paper / Live-Ready (auto-exec + alerts), breaker control")
    nav_button("Open Execution & Breaker →", "Settings_Exec_Breaker.py", key="open_exec")

st.divider()

c4, c5, c6 = st.columns(3)

with c4:
    st.subheader("Capital & Risk")
    st.caption("Capital mode, risk %, trades/day, SL cap, R:R min")
    nav_button("Open Capital & Risk →", "Settings_Capital_Risk.py", key="open_caprisk")

with c5:
    st.subheader("Market Filters")
    st.caption("Liquidity thresholds, spreads, expiry rules")
    nav_button("Open Market Filters →", "Settings_Market_Filters.py", key="open_mf")

with c6:
    st.subheader("Notifications & Reports")
    st.caption("Telegram verbosity, EOD summary, throttling")
    nav_button("Open Notifications →", "Settings_Notifications.py", key="open_notif")

st.divider()

c7, c8, c9 = st.columns(3)

with c7:
    st.subheader("Risk/Reward Profiles")
    st.caption("Profiles, overrides, preview")
    nav_button("Open RR Profiles →", "Settings_RR_Profiles.py", key="open_rr")

with c8:
    st.subheader("System & Environment")
    st.caption("Timezone, logs, UI theme")
    nav_button("Open System & Env →", "Settings_System_Env.py", key="open_sys")

with c9:
    st.subheader("About & Health")
    st.caption("Build, uptime, heartbeats")
    nav_button("Open About & Health →", "Settings_About_Health.py", key="open_about")
